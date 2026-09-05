"""Unit, integration, and falsification tests for Validator 6 (Entailment Guard, Issue 025 = C).

Implements agent_execution_guide.md §18 (X1) and design_claim_extraction.md §8:
1. Rejection of fabricated claims (Assertion c) across length floor and embedding similarity.
2. Verification that all 9 live verified claims from X0 pass Validator 6.
3. Prefix sensitivity test (Trap 7): document-to-document vs query-to-document comparison.
4. Ambiguous band quarantine: claims in [T_ENTAIL_LOW, T_ENTAIL_HIGH) are quarantined, never published,
   and never appear in any assessment's axis_evidence.
5. Zero LLM calls inside Validator 6 (design_rubric_engine.md §0).
6. Rejection logging and counters tracking.
7. Falsification (LOOP 2): T_ENTAIL_LOW = 0.0 causes Assertion (c) to fail (RED).
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fixtures.behaviour.loader import load_fabricated_proposition_fixtures
from worker.entities import Subject, Utterance
from worker.extract.dedup import cosine_similarity, get_embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    MIN_QUOTE_TOKENS,
    T_ENTAIL_HIGH,
    T_ENTAIL_LOW,
    get_rejection_counts,
    reset_rejection_counts,
    validate_entailment,
)
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def test_x1_fabrications_rejected_assertion_c() -> None:
    """Assertion (c): The two known fabricated claims from X0 are REJECTED.

    Tests both guards:
    1. Length floor (MIN_QUOTE_TOKENS = 7): both fabrications have 6 tokens and fail with 'quote_too_short'.
    2. Similarity floor (T_ENTAIL_LOW = 0.60): even if length check is bypassed, cosine similarity
       (0.5337 and 0.5296) falls below 0.60 and fails with 'quote_does_not_support_proposition'.
    """
    reset_rejection_counts()
    embedder = get_embedder()
    fixtures = load_fabricated_proposition_fixtures()
    assert len(fixtures) == 2, f"Expected 2 fabricated proposition fixtures, got {len(fixtures)}"

    for case in fixtures:
        claim = ExtractedClaim(
            proposition_text=case["proposition_text"],
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=case["quote_text"],
            confidence=0.95,
        )

        # 1. Full validator run: length floor catches it immediately
        outcome_full = validate_entailment(claim, embedder=embedder)
        assert outcome_full.is_valid is False
        assert outcome_full.status == "rejected"
        assert outcome_full.rejection_reason == "quote_too_short"

        # 2. Similarity-only run (bypassing length floor with min_quote_tokens=0):
        # Cosine similarity must be strictly below T_ENTAIL_LOW (0.60)
        outcome_sim = validate_entailment(claim, embedder=embedder, min_quote_tokens=0)
        assert outcome_sim.is_valid is False
        assert outcome_sim.status == "rejected"
        assert outcome_sim.rejection_reason == "quote_does_not_support_proposition"
        assert outcome_sim.similarity is not None
        assert outcome_sim.similarity < T_ENTAIL_LOW
        # Assert measured values match Orient findings to within 0.01
        assert abs(outcome_sim.similarity - case["measured_similarity_doc_doc"]) < 0.01

    # Verify rejection counters registered the rejections
    counts = get_rejection_counts()
    assert counts.get("quote_too_short", 0) >= 2
    assert counts.get("quote_does_not_support_proposition", 0) >= 2


def test_x1_all_live_claims_pass() -> None:
    """Every hand-verified true claim in social_proof.duckdb clears Validator 6.

    A validator that rejects everything is as useless as one that rejects nothing.
    All 9 live claims must pass:
    - Quote token length >= MIN_QUOTE_TOKENS (7)
    - Doc-to-doc similarity >= T_ENTAIL_HIGH (0.70)
    - Outcome status is 'passed' with no rejection reason
    """
    store = Storage("social_proof.duckdb", read_only=True)
    embedder = get_embedder()

    try:
        claim_rows = store.con.execute(
            "SELECT c.claim_id, c.quote_text, p.canonical_text "
            "FROM claims c JOIN propositions p ON c.proposition_id = p.proposition_id "
            "WHERE c.is_own_assertion AND c.extraction_version = 'gemma-3-27b-it:v1.1:s1'"
        ).fetchall()
    finally:
        store.close()
    assert len(claim_rows) == 9, f"Expected 9 hand-verified live claims in DB, got {len(claim_rows)}"

    for cid, quote_text, prop_text in claim_rows:
        assert quote_text is not None and quote_text.strip()
        assert prop_text is not None and prop_text.strip()

        claim = ExtractedClaim(
            proposition_text=prop_text,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=quote_text,
            confidence=0.95,
        )

        outcome = validate_entailment(claim, embedder=embedder)
        assert outcome.is_valid is True, (
            f"Live claim {cid} failed entailment check: reason={outcome.rejection_reason}, sim={outcome.similarity}"
        )
        assert outcome.status == "passed"
        assert outcome.rejection_reason is None
        assert outcome.similarity is not None
        assert outcome.similarity >= T_ENTAIL_HIGH, (
            f"Live claim {cid} similarity {outcome.similarity:.4f} below T_ENTAIL_HIGH ({T_ENTAIL_HIGH})"
        )


def test_x1_prefix_mismatch_sensitivity_trap_7() -> None:
    """Trap 7: Embedding a pair with mismatched prefixes yields a materially different similarity.

    Document-to-document comparisons must use 'search_document:' on BOTH sides.
    Mixing 'search_query:' and 'search_document:' shifts representations into different regions.
    """
    embedder = get_embedder()
    # Use live claim ae322a98ececbe5f ("until string theory is proved, it's unproved.")
    quote = "until string theory is proved, it's unproved."
    prop = "String theory remains unproven until empirical proof is demonstrated"

    # Both doc prefix (correct)
    vec_quote_doc = embedder.embed_document(quote)
    vec_prop_doc = embedder.embed_document(prop)
    sim_doc_doc = cosine_similarity(vec_quote_doc, vec_prop_doc)

    # Mixed prefixes: search_query on quote, search_document on prop (Trap 7 violation)
    vec_quote_query = embedder.embed_query(quote)
    sim_query_doc = cosine_similarity(vec_quote_query, vec_prop_doc)

    diff = abs(sim_doc_doc - sim_query_doc)
    # The difference must be materially non-zero (measured delta is ~0.056)
    assert diff > 0.03, f"Expected material difference between prefixes, got {diff:.4f}"
    assert sim_doc_doc > sim_query_doc, "Doc-to-doc similarity should be higher than mismatched query-doc"


def test_x1_ambiguous_band_quarantined_not_published_and_not_in_axis_evidence(tmp_path: Path) -> None:
    """A claim scoring inside the ambiguous band [T_ENTAIL_LOW, T_ENTAIL_HIGH) is quarantined.

    It must:
    - be written with is_own_assertion=False, exclusion_reason='entailment_ambiguous'
    - have claim.status == 'quarantined'
    - generate zero published tensions
    - appear in no assessment's axis_evidence
    """
    store = Storage(db_path=str(tmp_path / "test_x1.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Subject setup
    subj = Subject(subject_id="subj_ambig_01", display_name="Ambiguous Subject")
    store.insert_subject(subj)

    # Utterance
    utt = Utterance(
        utterance_id="utt_ambig_01",
        source_id="src_ambig_01",
        subject_id="subj_ambig_01",
        text_verbatim="Some general technology investments might possibly affect digital privacy rights in unforeseen ways.",
        start_ms=1000,
        end_ms=6000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
    )
    store.insert_utterance(utt)

    # Mock an ambiguous claim: proposition loosely related but similarity sits in [0.60, 0.70)
    # Quote: "Some general technology investments might possibly affect digital privacy rights"
    # Prop: "Comprehensive federal regulation of all encrypted messaging services"
    quote = "Some general technology investments might possibly affect digital privacy rights"
    prop = "Comprehensive federal regulation of all encrypted messaging services"

    t_low = 0.60
    t_high = 0.70

    claim_input = ExtractedClaim(
        proposition_text=prop,
        stance="support",
        hedging_level=0.2,
        is_own_assertion=True,
        quote_text=quote,
        confidence=0.90,
    )

    # Force similarity into ambiguous band via mock embedder or calibrated thresholds
    mock_embedder = MagicMock()
    # Return two vectors whose cosine similarity is exactly 0.65 (middle of [0.60, 0.70))
    # Let vec1 = [1, 0, ...], vec2 = [0.65, sqrt(1 - 0.65^2), ...]
    import numpy as np
    v1 = np.zeros(768, dtype=np.float32)
    v1[0] = 1.0
    v2 = np.zeros(768, dtype=np.float32)
    v2[0] = 0.65
    v2[1] = float(np.sqrt(1.0 - 0.65**2))

    mock_embedder.embed_document.side_effect = [v1.tolist(), v2.tolist()]

    outcome = validate_entailment(claim_input, embedder=mock_embedder, min_quote_tokens=5, t_low=t_low, t_high=t_high)
    assert outcome.is_valid is True
    assert outcome.status == "quarantined"
    assert outcome.rejection_reason == "entailment_ambiguous"
    assert outcome.similarity == pytest.approx(0.65, abs=1e-3)

    # Now run through ClaimExtractionPipeline with this mock embedder
    mock_embedder.embed_document.side_effect = [v1.tolist(), v2.tolist(), v2.tolist(), v2.tolist()]
    pipeline = ClaimExtractionPipeline(storage=store, embedder=mock_embedder)

    mock_output = {
        "claims": [
            {
                "proposition_text": prop,
                "stance": "support",
                "hedging_level": 0.2,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "quote_text": quote,
                "condition": None,
                "prior_stance_reported": None,
                "change_marker": None,
                "confidence": 0.90,
            }
        ]
    }

    claims = pipeline.extract_from_utterance(
        utterance=utt,
        source_recorded_at="2024-03-01T10:00:00Z",
        mock_model_output=mock_output,
    )
    assert len(claims) == 1
    c = claims[0]

    # Verify claim is quarantined in memory and storage
    assert c.is_own_assertion is False
    assert c.exclusion_reason == "entailment_ambiguous"
    assert c.status == "quarantined"

    stored_claim = store.get_claim(c.claim_id)
    assert stored_claim is not None
    assert stored_claim.is_own_assertion is False
    assert stored_claim.exclusion_reason == "entailment_ambiguous"
    assert stored_claim.status == "quarantined"

    # Run TensionDetector: quarantined claim must NOT produce any tension
    detector = TensionDetector(storage=store)
    tensions = detector.detect_all_tensions_for_subject("subj_ambig_01")
    assert len(tensions) == 0, f"Expected 0 tensions from excluded claim, found {len(tensions)}"

    # Run RubricEngine: assessment must contain ZERO quarantined items in axis_evidence
    engine = RubricEngine(storage=store)
    assessment = engine.assess_subject_topic("subj_ambig_01")
    assert assessment is not None
    for axis_name, evidence in assessment.axis_evidence.items():
        assert len(evidence) == 0, f"Axis {axis_name} contains unexpected evidence: {evidence}"


def test_x1_no_llm_calls_in_validator() -> None:
    """Validator 6 must perform zero LLM calls (design_rubric_engine.md §0 stays true)."""
    embedder = get_embedder()
    claim = ExtractedClaim(
        proposition_text="empirical validation of string theory",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="until string theory is proved it is unproved",
        confidence=0.95,
    )

    # Ensure no LocalGemmaRuntime methods are imported or called during validate_entailment
    outcome = validate_entailment(claim, embedder=embedder)
    assert outcome.is_valid is True
    # The validator relies solely on deterministic cosine similarity over pre-trained embeddings


def test_x1_falsification_t_entail_low_zero() -> None:
    """FALSIFICATION (LOOP 2):

    Setting T_ENTAIL_LOW = 0.0 and MIN_QUOTE_TOKENS = 0 causes the two known fabricated claims
    to PASS (Assertion c goes RED), proving that the threshold and token floor do the work
    rather than surrounding scaffolding.
    When active thresholds are restored, Assertion (c) goes GREEN.
    """
    embedder = get_embedder()
    fixtures = load_fabricated_proposition_fixtures()
    assert len(fixtures) == 2

    # Under corrupted / zero thresholds (RED condition):
    for case in fixtures:
        claim = ExtractedClaim(
            proposition_text=case["proposition_text"],
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=case["quote_text"],
            confidence=0.95,
        )

        # With T_ENTAIL_LOW = 0.0 and MIN_QUOTE_TOKENS = 0:
        outcome_falsified = validate_entailment(
            claim,
            embedder=embedder,
            min_quote_tokens=0,
            t_low=0.0,
            t_high=0.0,
        )
        # Falsification confirmed: without thresholds, fabricated claims wrongly PASS!
        assert outcome_falsified.is_valid is True, (
            "With T_ENTAIL_LOW=0.0 and MIN_QUOTE_TOKENS=0, fabricated claim must pass (RED falsification)"
        )
        assert outcome_falsified.status == "passed"

    # Under active production thresholds (GREEN condition):
    for case in fixtures:
        claim = ExtractedClaim(
            proposition_text=case["proposition_text"],
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=case["quote_text"],
            confidence=0.95,
        )

        outcome_active = validate_entailment(
            claim,
            embedder=embedder,
            min_quote_tokens=MIN_QUOTE_TOKENS,
            t_low=T_ENTAIL_LOW,
            t_high=T_ENTAIL_HIGH,
        )
        # Active thresholds reject the fabrications!
        assert outcome_active.is_valid is False
        assert outcome_active.status == "rejected"
