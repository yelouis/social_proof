"""The six post-extraction validators enforcing data contracts and Invariant I7.

Implements design_claim_extraction.md §3-§5, §8 (Validator 6) and agent_execution_guide.md §18 (X1).
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from worker.entities import Utterance
from worker.extract.schema import ExtractedClaim

logger = logging.getLogger(__name__)

# Parameter 026: Entailment guard thresholds (provisional, measured against live corpus & X0 fabrications)
# Measured in Issue 025/X1:
# - Known fabrications: 6 tokens, similarities 0.5296 and 0.5337
# - Live verified claims: 7 to 41 tokens (min 7 on string theory claim), similarities 0.7091 to 0.9311
MIN_QUOTE_TOKENS: int = 7
T_ENTAIL_LOW: float = 0.60
T_ENTAIL_HIGH: float = 0.70

# Rejection counters for observability / regression detection
VALIDATOR_REJECTION_COUNTERS: Counter[str] = Counter()


def get_rejection_counts() -> dict[str, int]:
    """Returns a snapshot of validation rejections and quarantines."""
    return dict(VALIDATOR_REJECTION_COUNTERS)


def reset_rejection_counts() -> None:
    """Resets validation counters (useful for test isolation)."""
    VALIDATOR_REJECTION_COUNTERS.clear()


# Banned polarity tokens in proposition_text (must live exclusively in stance)
POLARITY_BANNED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:should not|shouldn't|must not|mustn't|cannot|can't)\b", re.IGNORECASE),
    re.compile(r"\b(?:never|oppose|opposing|against|prohibit|prohibiting|illegal)\b", re.IGNORECASE),
    re.compile(r"\b(?:is bad|is harmful|is evil|is wrong)\b", re.IGNORECASE),
]

VALID_STANCES: set[str] = {"support", "oppose", "mixed", "hedge"}
VALID_EXCLUSIONS: set[str] = {
    "reported_speech",
    "hypothetical",
    "sarcasm",
    "steelman",
    "joke",
    "question",
    "quote_agreement_unclear",
    "entailment_ambiguous",
}


@dataclass
class ValidationOutcome:
    is_valid: bool
    rejection_reason: str | None = None
    resolved_quote_span: tuple[int, int] | None = None
    status: Literal["passed", "rejected", "quarantined"] = "passed"
    similarity: float | None = None
    prop_embedding: list[float] | None = None

    def __iter__(self) -> Any:
        """Allows 3-element tuple unpacking (is_valid, rejection_reason, span) for backward compatibility."""
        return iter((self.is_valid, self.rejection_reason, self.resolved_quote_span))


def validate_quote_verbatim(claim: ExtractedClaim, utterance_text: str) -> ValidationOutcome:
    """Validator 1: Exact verbatim substring check acting as evidence.

    quote_text must resolve in text_verbatim.
    """
    quote = claim.quote_text.strip()
    if not quote:
        return ValidationOutcome(False, "quote_verbatim_empty", status="rejected")

    idx = utterance_text.find(quote)
    if idx == -1:
        # Fallback: case-insensitive match
        idx_lower = utterance_text.lower().find(quote.lower())
        if idx_lower == -1:
            return ValidationOutcome(
                False, "quote_verbatim_not_found_in_utterance", status="rejected"
            )
        idx = idx_lower

    span = (idx, idx + len(quote))
    return ValidationOutcome(True, resolved_quote_span=span, status="passed")


def validate_entailment(
    claim: ExtractedClaim,
    embedder: Any | None = None,
    min_quote_tokens: int = MIN_QUOTE_TOKENS,
    t_low: float = T_ENTAIL_LOW,
    t_high: float = T_ENTAIL_HIGH,
) -> ValidationOutcome:
    """Validator 6: Entailment guard (Issue 025 = C, Parameter 026).

    Enforces that a quote actually supports the proposition attached to it.
    1. Length floor check (MIN_QUOTE_TOKENS). Rejects short arbitrary fragments (both X0 fabrications were 6 tokens).
    2. Document-to-document embedding similarity with 'search_document:' prefix on both sides (Trap 7).
    3. Three outcomes:
       - sim < t_low: reject ("quote_does_not_support_proposition")
       - t_low <= sim < t_high: quarantine ("entailment_ambiguous")
       - sim >= t_high: pass
    """
    quote = (claim.quote_text or "").strip()
    token_count = len(quote.split())
    if token_count < min_quote_tokens:
        VALIDATOR_REJECTION_COUNTERS["quote_too_short"] += 1
        logger.info(
            "Validator 6 rejected claim (quote_too_short): %d < %d tokens. Quote: '%s'",
            token_count,
            min_quote_tokens,
            quote,
        )
        return ValidationOutcome(
            is_valid=False,
            rejection_reason="quote_too_short",
            status="rejected",
        )

    if embedder is None:
        from worker.extract.dedup import get_embedder

        embedder = get_embedder()

    # Document-to-document similarity with "search_document:" prefix on both sides (Trap 7)
    vec_quote = embedder.embed_document(quote)
    vec_prop = embedder.embed_document(claim.proposition_text.strip())
    from worker.extract.dedup import cosine_similarity

    sim = cosine_similarity(vec_quote, vec_prop)

    if sim < t_low:
        VALIDATOR_REJECTION_COUNTERS["quote_does_not_support_proposition"] += 1
        logger.info(
            "Validator 6 rejected claim (quote_does_not_support_proposition): sim=%.4f < %.4f. Prop: '%s', Quote: '%s'",
            sim,
            t_low,
            claim.proposition_text,
            quote,
        )
        return ValidationOutcome(
            is_valid=False,
            rejection_reason="quote_does_not_support_proposition",
            status="rejected",
            similarity=sim,
            prop_embedding=vec_prop,
        )
    elif sim < t_high:
        VALIDATOR_REJECTION_COUNTERS["entailment_ambiguous"] += 1
        logger.info(
            "Validator 6 quarantined claim (entailment_ambiguous): %.4f <= sim=%.4f < %.4f. Prop: '%s', Quote: '%s'",
            t_low,
            sim,
            t_high,
            claim.proposition_text,
            quote,
        )
        return ValidationOutcome(
            is_valid=True,
            rejection_reason="entailment_ambiguous",
            status="quarantined",
            similarity=sim,
            prop_embedding=vec_prop,
        )

    return ValidationOutcome(
        is_valid=True,
        rejection_reason=None,
        status="passed",
        similarity=sim,
        prop_embedding=vec_prop,
    )


def validate_polarity(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 2: Proposition text must be stance-neutral and contain no polarity words."""
    prop_text = claim.proposition_text
    for pat in POLARITY_BANNED_PATTERNS:
        if pat.search(prop_text):
            return ValidationOutcome(
                False, f"polarity_violation_in_proposition: {pat.pattern}", status="rejected"
            )
    return ValidationOutcome(True, status="passed")


def validate_speech_acts(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 3: Invariant I7 speech-act validation."""
    if not claim.is_own_assertion:
        if not claim.exclusion_reason or claim.exclusion_reason not in VALID_EXCLUSIONS:
            return ValidationOutcome(
                False, "excluded_claim_missing_valid_exclusion_reason", status="rejected"
            )
    elif claim.exclusion_reason is not None:
        return ValidationOutcome(
            False, "own_assertion_cannot_have_exclusion_reason", status="rejected"
        )
    return ValidationOutcome(True, status="passed")


def validate_confidence_floor(claim: ExtractedClaim, floor: float = 0.70) -> ValidationOutcome:
    """Validator 4: Confidence floor check."""
    if claim.confidence < floor:
        return ValidationOutcome(
            False,
            f"confidence_below_floor: {claim.confidence:.2f} < {floor:.2f}",
            status="rejected",
        )
    return ValidationOutcome(True, status="passed")


def validate_schema(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 5: Schema conformity (stance enum, hedging bounds)."""
    if claim.stance not in VALID_STANCES:
        return ValidationOutcome(False, f"invalid_stance: {claim.stance}", status="rejected")
    if not (0.0 <= claim.hedging_level <= 1.0):
        return ValidationOutcome(
            False, f"hedging_level_out_of_bounds: {claim.hedging_level}", status="rejected"
        )
    return ValidationOutcome(True, status="passed")


def validate_extracted_claim(
    claim: ExtractedClaim,
    utterance: Utterance,
    confidence_floor: float = 0.70,
    embedder: Any | None = None,
    min_quote_tokens: int = MIN_QUOTE_TOKENS,
    t_low: float = T_ENTAIL_LOW,
    t_high: float = T_ENTAIL_HIGH,
) -> ValidationOutcome:
    """Runs all 6 validators in sequence.

    1. Quote Verbatim (substring in utterance)
    2. Entailment (Validator 6: length floor, document-to-document embedding similarity)
    3. Polarity (neutral proposition text)
    4. Speech Acts (Invariant I7: exclusions vs own assertions)
    5. Confidence Floor (confidence >= floor)
    6. Schema (valid stance, hedging level in [0, 1])
    """
    # 1. Quote Verbatim
    res_quote = validate_quote_verbatim(claim, utterance.text_verbatim)
    if not res_quote.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_quote.rejection_reason or "quote_verbatim_failed"] += 1
        return res_quote

    # 2. Entailment (Validator 6) runs immediately after quote resolution
    res_entail = validate_entailment(
        claim=claim,
        embedder=embedder,
        min_quote_tokens=min_quote_tokens,
        t_low=t_low,
        t_high=t_high,
    )
    if not res_entail.is_valid:
        return res_entail

    # If ambiguous, mark claim as excluded/quarantined so speech acts validation succeeds
    if res_entail.status == "quarantined":
        claim.is_own_assertion = False
        claim.exclusion_reason = "entailment_ambiguous"

    # 3. Polarity
    res_pol = validate_polarity(claim)
    if not res_pol.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_pol.rejection_reason or "polarity_failed"] += 1
        return res_pol

    # 4. Speech Acts
    res_sa = validate_speech_acts(claim)
    if not res_sa.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_sa.rejection_reason or "speech_acts_failed"] += 1
        return res_sa

    # 5. Confidence Floor
    res_conf = validate_confidence_floor(claim, confidence_floor)
    if not res_conf.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_conf.rejection_reason or "confidence_floor_failed"] += 1
        return res_conf

    # 6. Schema
    res_schema = validate_schema(claim)
    if not res_schema.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_schema.rejection_reason or "schema_failed"] += 1
        return res_schema

    return ValidationOutcome(
        is_valid=True,
        rejection_reason=res_entail.rejection_reason,
        resolved_quote_span=res_quote.resolved_quote_span,
        status=res_entail.status,
        similarity=res_entail.similarity,
        prop_embedding=res_entail.prop_embedding,
    )
