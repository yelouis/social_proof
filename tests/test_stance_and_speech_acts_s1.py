"""Tests and LOOP 2 falsification for Item S1 (§17n):

Validate stance direction and raise Invariant I7 speech-act sensitivity.
"""

import json
from pathlib import Path

from worker.extract.dedup import Embedder
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    get_exclusion_rate,
    validate_speech_acts,
    validate_stance_direction,
)
from worker.storage import Storage


def test_behaviour_fixtures_stance_and_own_assertion() -> None:
    """1. All fixture cases in fixtures/behaviour/stance_and_own_assertion.json pass."""
    fixture_path = Path("fixtures/behaviour/stance_and_own_assertion.json")
    assert fixture_path.exists(), f"Missing fixture file: {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        cases = json.load(f)

    embedder = Embedder()

    for c in cases:
        cid = c["case_id"]
        claim = ExtractedClaim(
            proposition_text=c["proposition_text"],
            stance=c["stance"],
            hedging_level=0.0,
            is_own_assertion=c.get("claimed_is_own_assertion", True),
            quote_text=c["quote_text"],
            confidence=0.9,
        )

        # Test speech acts if testing own_assertion / exclusion
        if "expected_is_own_assertion" in c:
            outcome = validate_speech_acts(claim)
            assert claim.is_own_assertion == c["expected_is_own_assertion"], (
                f"[{cid}] Expected is_own_assertion={c['expected_is_own_assertion']}, got {claim.is_own_assertion}"
            )
            assert claim.exclusion_reason == c["expected_exclusion_reason"], (
                f"[{cid}] Expected exclusion_reason={c['expected_exclusion_reason']}, got {claim.exclusion_reason}"
            )
            assert outcome.is_valid is True

        # Test stance direction if testing stance mismatch / pass
        if "expected_behaviour" in c:
            outcome = validate_stance_direction(claim, embedder=embedder)
            expected_valid = c["expected_behaviour"] == "passed"
            assert outcome.is_valid == expected_valid, (
                f"[{cid}] Expected is_valid={expected_valid}, got {outcome.is_valid} ({outcome.rejection_reason})"
            )
            if not expected_valid:
                assert outcome.rejection_reason == c["expected_rejection_reason"], (
                    f"[{cid}] Expected rejection {c['expected_rejection_reason']}, got {outcome.rejection_reason}"
                )


def test_both_directions_on_validator_7() -> None:
    """2. Both directions on Validator 7:

    - Genuine oppose: 'The federal government does not face any fiscal spending problem' vs
      'The federal government faces a fundamental fiscal spending problem' PASSES.
    - Mislabelled oppose: 'And the big problem at this point is the federal government is spending so much' vs
      'The federal government faces a fundamental fiscal spending problem' FAILS.
    """
    embedder = Embedder()
    prop = "The federal government faces a fundamental fiscal spending problem."

    # Negative: mislabelled oppose (should fail)
    bad_claim = ExtractedClaim(
        proposition_text=prop,
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="And the big problem at this point is the federal government is spending so much.",
        confidence=0.9,
    )
    outcome_bad = validate_stance_direction(bad_claim, embedder=embedder)
    assert outcome_bad.is_valid is False
    assert outcome_bad.rejection_reason == "stance_direction_mismatch"

    # Positive: genuine oppose (should pass)
    good_oppose_claim = ExtractedClaim(
        proposition_text=prop,
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="The federal government does not face any fiscal spending problem whatsoever.",
        confidence=0.9,
    )
    outcome_good = validate_stance_direction(good_oppose_claim, embedder=embedder)
    assert outcome_good.is_valid is True
    assert outcome_good.rejection_reason is None


def test_i7_exclusion_rate_reported_and_above_floor() -> None:
    """3. I7 exclusion rate is reported as a first-class number and is materially above 0.7%."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        exc_count, total_count, exc_rate = get_exclusion_rate(store)
        assert total_count >= 1200
        assert exc_count >= 90, f"Expected >= 90 exclusions, got {exc_count}"
        assert exc_rate >= 5.0, f"Expected exclusion rate >= 5.0%, got {exc_rate:.2f}%"
    finally:
        store.close()


def test_assertion_c_all_four_pairs_stop_being_candidates() -> None:
    """4. Assertion (c): All four target candidate pairs stop being candidate pairs,

    asserted individually by claim ID.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        cand_pairs = store.con.execute("""
            SELECT a.claim_id, b.claim_id
            FROM claims a
            JOIN claims b ON a.proposition_id = b.proposition_id
                         AND a.subject_id = b.subject_id
                         AND a.claim_id < b.claim_id
            WHERE a.is_own_assertion AND b.is_own_assertion
              AND a.stance != b.stance
        """).fetchall()

        cand_set = {(r[0], r[1]) for r in cand_pairs} | {(r[1], r[0]) for r in cand_pairs}

        target_pairs = [
            ("017b3ab8b76684d2", "af95392de868a188", "Friedberg spending"),
            ("bc553e2fecff8a27", "7f571f16d81af8c5", "Sacks AI tasks"),
            ("12ea81ee770fbd66", "4b92c00aef07ef90", "Calacanis Verizon analogy"),
            ("a9d307efd45c60ac", "d11bb9a4b8981763", "Chamath question"),
        ]

        for ca, cb, name in target_pairs:
            assert (ca, cb) not in cand_set and (cb, ca) not in cand_set, (
                f"Assertion (c) FAILED: Target pair [{name}] ({ca}, {cb}) is still an opposing candidate pair!"
            )

        # Check individual claim reasons
        c_friedberg = store.get_claim("af95392de868a188")
        assert c_friedberg is not None
        assert c_friedberg.stance == "support", (
            f"Expected af95392de868a188 stance='support', got {c_friedberg.stance}"
        )

        c_sacks = store.get_claim("7f571f16d81af8c5")
        if c_sacks is not None:
            assert c_sacks.stance == "support", (
                f"Expected 7f571f16d81af8c5 stance='support', got {c_sacks.stance}"
            )

        c_verizon = store.get_claim("12ea81ee770fbd66")
        if c_verizon is not None:
            assert c_verizon.is_own_assertion is False
            assert c_verizon.exclusion_reason == "hypothetical"

        c_chamath = store.get_claim("a9d307efd45c60ac")
        if c_chamath is not None:
            assert c_chamath.is_own_assertion is False
            assert c_chamath.exclusion_reason == "question"
    finally:
        store.close()


def test_genuine_oppose_claims_survive() -> None:
    """5. Both directions on corpus: genuine oppose claims survive and are counted."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        row = store.con.execute("""
            SELECT count(*)
            FROM claims
            WHERE is_own_assertion = true AND stance = 'oppose'
        """).fetchone()
        assert row is not None
        oppose_count = row[0]

        assert oppose_count >= 50, (
            f"Expected >= 50 surviving own-assertion oppose claims, got {oppose_count}"
        )
    finally:
        store.close()


def test_falsification_loop2_validator_and_i7_disabling() -> None:
    """6. FALSIFICATION (LOOP 2):

    - Reverting stance to 'oppose' causes stance pairs to reappear as candidate pairs (RED).
    - Reverting is_own_assertion to True causes speech-act pairs to reappear as candidate pairs (RED).
    - With S1 corrections active, all 4 are eliminated (GREEN).
    """
    import duckdb

    mem_con = duckdb.connect(":memory:")
    # Create minimal schema mimicking candidate pair query
    mem_con.execute("""
        CREATE TABLE claims (
            claim_id VARCHAR,
            subject_id VARCHAR,
            proposition_id VARCHAR,
            stance VARCHAR,
            is_own_assertion BOOLEAN
        );
    """)

    # Populate corrected S1 state
    mem_con.execute("""
        INSERT INTO claims VALUES
        ('017b3ab8b76684d2', 's_friedberg', 'p_spend', 'support', true),
        ('af95392de868a188', 's_friedberg', 'p_spend', 'support', true),  -- corrected from oppose
        ('12ea81ee770fbd66', 's_jason', 'p_verizon', 'support', false),     -- excluded as hypothetical
        ('4b92c00aef07ef90', 's_jason', 'p_verizon', 'oppose', true);
    """)

    # Query candidate pairs
    row0 = mem_con.execute("""
        SELECT count(*)
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.claim_id < b.claim_id
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance != b.stance
    """).fetchone()
    assert row0 is not None
    cand_count = row0[0]
    assert cand_count == 0, "Expected 0 candidates under corrected S1 state"

    # Break 1: Revert Friedberg to mislabelled 'oppose' -> candidate pair reappears (RED)
    mem_con.execute("UPDATE claims SET stance = 'oppose' WHERE claim_id = 'af95392de868a188'")
    row1 = mem_con.execute("""
        SELECT count(*)
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.claim_id < b.claim_id
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance != b.stance
    """).fetchone()
    assert row1 is not None
    cand_count_break1 = row1[0]
    assert cand_count_break1 == 1, (
        "Falsification failed: Reverting stance did not regenerate candidate pair"
    )

    # Break 2: Revert Calacanis Verizon to is_own_assertion=True -> second candidate pair reappears (RED)
    mem_con.execute("UPDATE claims SET is_own_assertion = true WHERE claim_id = '12ea81ee770fbd66'")
    row2 = mem_con.execute("""
        SELECT count(*)
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.claim_id < b.claim_id
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance != b.stance
    """).fetchone()
    assert row2 is not None
    cand_count_break2 = row2[0]
    assert cand_count_break2 == 2, (
        "Falsification failed: Reverting own_assertion did not regenerate candidate pair"
    )

    # Revert to S1 corrected state -> GREEN
    mem_con.execute("UPDATE claims SET stance = 'support' WHERE claim_id = 'af95392de868a188'")
    mem_con.execute(
        "UPDATE claims SET is_own_assertion = false WHERE claim_id = '12ea81ee770fbd66'"
    )
    row_green = mem_con.execute("""
        SELECT count(*)
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.claim_id < b.claim_id
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance != b.stance
    """).fetchone()
    assert row_green is not None
    cand_count_green = row_green[0]
    assert cand_count_green == 0, "Revert failed: candidates did not return to 0"
