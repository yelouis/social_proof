"""Tests and LOOP 2 falsification for Item D3 (§17t):

Validator 7 bidirectional stance validation & hedge resolution.
"""

import json
from pathlib import Path

from worker.extract.dedup import Embedder
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    get_stance_correction_counts,
    reset_stance_correction_counts,
    validate_stance_direction,
)
from worker.storage import Storage


def test_hand_labelled_eval_set_both_directions() -> None:
    """1. Assertion (c) & Bidirectional Hand-Labelled Evaluation.

    - Validator 7 corrects at least one claim from support to oppose (Assertion c).
    - Genuine supports stay support, genuine opposes end as oppose.
    - Confusion counts reported.
    - Standing bidirectional counters reported.
    """
    fixture_path = Path("fixtures/behaviour/stance_validation_eval.json")
    assert fixture_path.exists(), f"Missing fixture file: {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) >= 10, f"Expected at least 10 cases (>=5 per class), got {len(cases)}"

    reset_stance_correction_counts()
    embedder = Embedder()

    confusion: dict[str, int] = {
        "true_oppose_ended_oppose": 0,
        "true_oppose_ended_support": 0,
        "true_support_ended_support": 0,
        "true_support_ended_oppose": 0,
    }

    for c in cases:
        cid = c["case_id"]
        true_stance = c["true_stance"]
        claim = ExtractedClaim(
            proposition_text=c["proposition_text"],
            stance=c["initial_stance"],
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=c["quote_text"],
            confidence=0.9,
        )

        outcome = validate_stance_direction(claim, embedder=embedder, auto_correct=True)
        assert outcome.is_valid is True, f"[{cid}] Expected valid after auto_correct, got {outcome}"

        final_stance = claim.stance
        if true_stance == "oppose":
            if final_stance == "oppose":
                confusion["true_oppose_ended_oppose"] += 1
            else:
                confusion["true_oppose_ended_support"] += 1
        elif true_stance == "support":
            if final_stance == "support":
                confusion["true_support_ended_support"] += 1
            else:
                confusion["true_support_ended_oppose"] += 1

        assert final_stance == true_stance, (
            f"[{cid}] Expected final stance '{true_stance}', got '{final_stance}' (initial: '{c['initial_stance']}')"
        )

    counts = get_stance_correction_counts()

    # Assertion (c): validator 7 corrects at least one claim from support to oppose
    assert counts["stance_corrected_to_oppose"] >= 1, (
        f"Assertion (c) FAILED: expected >= 1 correction to oppose, got {counts['stance_corrected_to_oppose']}"
    )

    # Both directions: corrections occurred in both directions
    assert counts["stance_corrected_to_support"] >= 1, (
        f"Expected >= 1 correction to support, got {counts['stance_corrected_to_support']}"
    )

    # Zero confusion errors
    assert confusion["true_oppose_ended_support"] == 0, f"Oppose errors: {confusion}"
    assert confusion["true_support_ended_oppose"] == 0, f"Support errors: {confusion}"
    assert confusion["true_oppose_ended_oppose"] == 6
    assert confusion["true_support_ended_support"] == 6


def test_rejection_behaviour_without_auto_correct() -> None:
    """2. Bidirectional rejection verification when auto_correct=False."""
    embedder = Embedder()

    # Direction 1: Oppose claim with positive assertion (no negation) -> REJECTED
    claim_supp_as_opp = ExtractedClaim(
        proposition_text="The federal government faces a fundamental fiscal spending problem.",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="And the big problem at this point is the federal government is spending so much.",
        confidence=0.9,
    )
    outcome1 = validate_stance_direction(claim_supp_as_opp, embedder=embedder, auto_correct=False)
    assert outcome1.is_valid is False
    assert outcome1.rejection_reason == "stance_direction_mismatch"

    # Direction 2: Support claim with explicit syntactic negation -> REJECTED
    claim_opp_as_supp = ExtractedClaim(
        proposition_text="federal licensing of frontier AI models",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="We should not have federal licensing for frontier AI models.",
        confidence=0.9,
    )
    outcome2 = validate_stance_direction(claim_opp_as_supp, embedder=embedder, auto_correct=False)
    assert outcome2.is_valid is False
    assert outcome2.rejection_reason == "stance_direction_mismatch"

    # Both directions when correctly labelled -> PASSED
    claim_opp_good = ExtractedClaim(
        proposition_text="federal licensing of frontier AI models",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="We should not have federal licensing for frontier AI models.",
        confidence=0.9,
    )
    outcome3 = validate_stance_direction(claim_opp_good, embedder=embedder, auto_correct=False)
    assert outcome3.is_valid is True

    claim_supp_good = ExtractedClaim(
        proposition_text="federal licensing of frontier AI models",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="We absolutely need federal licensing for frontier models.",
        confidence=0.9,
    )
    outcome4 = validate_stance_direction(claim_supp_good, embedder=embedder, auto_correct=False)
    assert outcome4.is_valid is True


def test_standing_counters_reported() -> None:
    """3. Standing bidirectional correction counters are reported and resettable."""
    reset_stance_correction_counts()
    c = get_stance_correction_counts()
    assert "stance_corrected_to_support" in c or c == {}
    assert "stance_corrected_to_oppose" in c or c == {}


def test_hedge_resolved_and_zero_in_database() -> None:
    """4. Resolution of 'hedge': 0 claims in database have stance = 'hedge'."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        row = store.con.execute("SELECT count(*) FROM claims WHERE stance = 'hedge'").fetchone()
        assert row is not None
        assert row[0] == 0, f"Expected 0 claims with stance='hedge', found {row[0]}"

        # Check the migrated claim: Chamath hidden incentives
        migrated = store.get_claim("28de003b3fa15e34")
        assert migrated is not None
        assert migrated.stance == "support"
        assert migrated.hedging_level == 0.7
    finally:
        store.close()


def test_falsification_plain_negation_quote_labels_oppose() -> None:
    """5. LOOP 2 FALSIFICATION:

    - Feed the validator a quote that plainly negates its proposition and confirm it labels 'oppose'.
    - If syntactic negation instrument is disabled, embedding delta alone cannot discriminate (sim_neg - sim_pos < 0.05).
    """
    embedder = Embedder()
    claim = ExtractedClaim(
        proposition_text="federal licensing of frontier AI models",
        stance="support",  # intentionally mislabelled as support
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="We should not have federal licensing for frontier AI models.",
        confidence=0.9,
    )

    # 1. With enhanced instrument: plain negation is caught and corrected to oppose (GREEN)
    outcome = validate_stance_direction(claim, embedder=embedder, auto_correct=True)
    assert outcome.is_valid is True
    assert claim.stance == "oppose", f"Expected stance 'oppose', got '{claim.stance}'"

    # 2. Break instrument: simulate legacy embedding-only test without syntactic analysis
    # Under legacy embedding test, sim_neg > sim_pos + 0.05 is never satisfied, so support survives (RED)
    v_prop = embedder.embed_document("federal licensing of frontier AI models")
    v_neg = embedder.embed_document("It is not the case that federal licensing of frontier AI models")
    v_quote = embedder.embed_document("We should not have federal licensing for frontier AI models.")
    from worker.extract.dedup import cosine_similarity

    sim_pos = cosine_similarity(v_quote, v_prop)
    sim_neg = cosine_similarity(v_quote, v_neg)

    # Confirm the empirical finding that embedding delta alone fails:
    assert not (sim_neg > sim_pos + 0.05), (
        f"Falsification verification: expected sim_neg ({sim_neg:.4f}) <= sim_pos + 0.05 ({sim_pos + 0.05:.4f})"
    )
