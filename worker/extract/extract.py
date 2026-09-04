"""End-to-end claim extraction pipeline integrating Gate, Runtime, Validators, and Storage.

Implements design_claim_extraction.md §1-§8 and agent_execution_guide.md §11 (U11).
"""

from typing import Any

from worker.entities import Claim, Proposition, Utterance
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import validate_extracted_claim
from worker.storage import Storage, compute_claim_id, compute_proposition_id


class ClaimExtractionPipeline:
    """Extraction pipeline applying gate pre-filter, LLM runtime, validators, and storage persistence."""

    def __init__(
        self,
        storage: Storage,
        runtime: LocalGemmaRuntime | None = None,
        gate: ExtractionGate | None = None,
        confidence_floor: float = 0.70,
        embedder: Any | None = None,
    ) -> None:
        self.storage = storage
        self.runtime = runtime or LocalGemmaRuntime()
        self.gate = gate or ExtractionGate()
        self.confidence_floor = confidence_floor
        self.embedder = embedder

    def extract_from_utterance(
        self,
        utterance: Utterance,
        source_recorded_at: str,
        subject_context: str = "",
        mock_model_output: dict[str, Any] | None = None,
    ) -> list[Claim]:
        """Extracts validated Claim records from an utterance."""
        # 1. Gate Stage pre-filter
        decision = self.gate.evaluate_utterance(utterance)
        if not decision.should_extract:
            return []

        # 2. Local LLM Runtime constrained decoding
        stats = self.runtime.generate_constrained(
            utterance_text=utterance.text_verbatim,
            subject_context=subject_context,
            enforce_grammar=True,
            mock_output=mock_model_output,
        )

        extracted_claims = stats.parsed_result.claims
        valid_claims: list[Claim] = []

        # 3. Apply Validators sequentially (1 to 6)
        for ec in extracted_claims:
            outcome = validate_extracted_claim(
                claim=ec,
                utterance=utterance,
                confidence_floor=self.confidence_floor,
                embedder=self.embedder,
            )

            if not outcome.is_valid or outcome.resolved_quote_span is None:
                # Discard rejected extraction
                continue

            span = outcome.resolved_quote_span
            is_quarantined = outcome.status == "quarantined"

            # 4. Resolve or create Proposition entity
            prop_id = compute_proposition_id(ec.proposition_text)
            existing_prop = self.storage.get_proposition(prop_id)
            if not existing_prop:
                prop = Proposition(
                    proposition_id=prop_id,
                    canonical_text=ec.proposition_text,
                    subject_ids=[utterance.subject_id],
                    claim_count=1,
                    status="quarantined" if is_quarantined else "active",
                    quarantine_reason=outcome.rejection_reason if is_quarantined else None,
                )
                self.storage.insert_proposition(prop)
                if self.embedder is not None:
                    emb = self.embedder.embed_document(prop.canonical_text)
                else:
                    emb = [0.0] * 768
                self.storage.insert_proposition_embedding(prop_id, emb)

            # 5. Build deterministic Claim record
            claim_id = compute_claim_id(
                utterance_id=utterance.utterance_id,
                proposition_id=prop_id,
                stance=ec.stance,
                extraction_version=self.runtime.extraction_version,
            )

            claim = Claim(
                claim_id=claim_id,
                subject_id=utterance.subject_id,
                utterance_id=utterance.utterance_id,
                proposition_id=prop_id,
                stance=ec.stance,
                hedging_level=ec.hedging_level,
                is_own_assertion=False if is_quarantined else ec.is_own_assertion,
                exclusion_reason=outcome.rejection_reason if is_quarantined else ec.exclusion_reason,
                confidence=ec.confidence,
                quote_span=span,
                extraction_model=self.runtime.model_id,
                prompt_version=self.runtime.prompt_version,
                extraction_version=self.runtime.extraction_version,
                recorded_at=source_recorded_at,
                quote_text=ec.quote_text,
            )

            self.storage.insert_claim(claim)
            valid_claims.append(claim)

        return valid_claims
