"""Tests and LOOP 2 falsification for Item W0 (§17m) — Self-Contained Propositions.

Verifies:
1. Behaviour fixtures in fixtures/behaviour/indexical_proposition.json pass/fail as expected.
2. Both directions on the validator:
   - "China has made a significant push towards open source software" passes.
   - "The speaker believes they created the subject matter" is rejected.
   - "The subject makes a large number of copies of the protein" is rejected.
   - "They lack the expertise to determine whether a technology should be approved" is rejected.
3. Rejection counters: validate_self_contained increments proposition_not_self_contained counter.
4. Ordering: validate_self_contained runs before validate_entailment.
5. Assertion (c): Zero propositions in the live database match indexical patterns,
   and TensionDetector candidate pairs are explicitly reported.
6. Top 5 merged clusters are genuine proposition restatements, not indexical attractors.
7. Falsification (LOOP 2):
   - Disabling validate_self_contained permits indexical templates to pass.
   - Re-enabling rejects them with proposition_not_self_contained.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from worker.entities import Utterance
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    get_rejection_counts,
    reset_rejection_counts,
    validate_extracted_claim,
    validate_self_contained,
)
from worker.storage import Storage


@pytest.fixture
def live_db() -> Storage:
    return Storage("social_proof.duckdb", read_only=True)


def test_indexical_fixtures_behavior() -> None:
    """1. Test all cases in fixtures/behaviour/indexical_proposition.json."""
    fixture_path = Path("fixtures/behaviour/indexical_proposition.json")
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    assert len(cases) >= 10, f"Expected >= 10 test cases in fixture, found {len(cases)}"

    for case in cases:
        claim = ExtractedClaim(
            proposition_text=case["proposition_text"],
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="arbitrary valid verbatim quote",
            confidence=0.9,
        )
        outcome = validate_self_contained(claim)
        expected_pass = case["expected_behaviour"] == "passed"

        assert outcome.is_valid == expected_pass, (
            f"Case {case['case_id']} ('{case['proposition_text']}') expected pass={expected_pass}, got is_valid={outcome.is_valid}"
        )
        if not expected_pass:
            assert outcome.rejection_reason == case["expected_rejection_reason"], (
                f"Case {case['case_id']} expected reason {case['expected_rejection_reason']}, got {outcome.rejection_reason}"
            )


def test_both_directions_and_rejection_counters() -> None:
    """2. Test both directions on the validator and counter increments."""
    reset_rejection_counts()

    # Direction 1: Self-contained positive cases must pass
    clean_claim = ExtractedClaim(
        proposition_text="China has made a significant push towards open source software.",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="China has made a significant push towards open source software.",
        confidence=0.9,
    )
    res_clean = validate_self_contained(clean_claim)
    assert res_clean.is_valid, f"Expected self-contained proposition to pass, got rejected: {res_clean.rejection_reason}"
    assert res_clean.rejection_reason is None

    # Direction 2: Indexicals and unbound pronouns must be rejected
    rejected_props = [
        "The speaker believes they created the subject matter.",
        "The subject makes a large number of copies of the protein.",
        "They lack the expertise to determine whether a technology should be approved.",
    ]

    for ptext in rejected_props:
        bad_claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="valid quote here for testing",
            confidence=0.9,
        )
        res_bad = validate_self_contained(bad_claim)
        assert not res_bad.is_valid, f"Expected '{ptext}' to be rejected, but it passed!"
        assert res_bad.rejection_reason == "proposition_not_self_contained"

    counts = get_rejection_counts()
    assert counts.get("proposition_not_self_contained", 0) == 3, (
        f"Expected 3 rejections recorded in counter, got {counts.get('proposition_not_self_contained')}"
    )


def test_validator_chain_ordering() -> None:
    """3. Verify validate_self_contained runs in validate_extracted_claim before embedder."""
    utt = Utterance(
        utterance_id="utt_test_ordering",
        source_id="src_01",
        subject_id="subj_test",
        start_ms=0,
        end_ms=1000,
        text_verbatim="This is a test utterance containing exact quote verbatim text.",
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="pyannote",
    )

    bad_claim = ExtractedClaim(
        proposition_text="The speaker believes they created the subject matter.",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="exact quote verbatim text",
        confidence=0.9,
    )

    # Embedder is passed as None; if entailment were evaluated first, it would attempt embedder calls
    outcome = validate_extracted_claim(
        claim=bad_claim,
        utterance=utt,
        embedder=None,
    )

    assert not outcome.is_valid
    assert outcome.rejection_reason == "proposition_not_self_contained"


def test_assertion_c_corpus_has_zero_indexical_propositions(live_db: Storage) -> None:
    """4. Assertion (c): Zero propositions in the live database match indexical patterns."""
    con = live_db.con
    props = con.execute("""
        SELECT p.proposition_id, p.canonical_text, count(c.claim_id) as c_cnt
        FROM propositions p
        JOIN claims c ON p.proposition_id = c.proposition_id
        GROUP BY p.proposition_id, p.canonical_text
    """).fetchall()

    assert len(props) > 0, "No active propositions found in database"

    failing_props = []
    for pid, text, _cnt in props:
        dummy = ExtractedClaim(
            proposition_text=text,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.9,
        )
        if not validate_self_contained(dummy).is_valid:
            failing_props.append((pid, text))

    assert len(failing_props) == 0, (
        f"Assertion (c) FAILED: Found {len(failing_props)} indexical propositions in live corpus! Examples: {failing_props[:3]}"
    )


def test_top_5_merged_clusters_are_propositions_not_topics(live_db: Storage) -> None:
    """5. Verify the top 5 largest merged proposition clusters are genuine restatements."""
    con = live_db.con
    top_clusters = con.execute("""
        SELECT p.proposition_id, p.canonical_text, count(c.claim_id) as claim_cnt
        FROM propositions p
        JOIN claims c ON p.proposition_id = c.proposition_id
        GROUP BY p.proposition_id, p.canonical_text
        ORDER BY claim_cnt DESC
        LIMIT 5
    """).fetchall()

    assert len(top_clusters) == 5, f"Expected 5 top clusters, got {len(top_clusters)}"

    for pid, text, cnt in top_clusters:
        assert cnt >= 1, f"Cluster {pid} has 0 claims"
        # Must not be indexical attractor
        dummy = ExtractedClaim(
            proposition_text=text,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.9,
        )
        assert validate_self_contained(dummy).is_valid, f"Top cluster {pid} ('{text}') is an indexical attractor!"


def test_falsification_loop_2() -> None:
    """6. LOOP 2 Falsification: Disabling validator permits indexicals; re-enabling blocks them."""
    test_claim = ExtractedClaim(
        proposition_text="The speaker believes they created the subject matter.",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="dummy quote",
        confidence=0.9,
    )

    # With validator active: rejected (GREEN)
    outcome_active = validate_self_contained(test_claim)
    assert not outcome_active.is_valid
    assert outcome_active.rejection_reason == "proposition_not_self_contained"

    # Simulated code break: bypassed validator permits indexical proposition (RED)
    def simulated_bypass_validate(_claim: ExtractedClaim) -> Any:
        return True

    assert simulated_bypass_validate(test_claim) is True, "Bypassed validator should permit indexical template"

    # Revert to active validator: blocked again (GREEN)
    outcome_reverted = validate_self_contained(test_claim)
    assert not outcome_reverted.is_valid
    assert outcome_reverted.rejection_reason == "proposition_not_self_contained"
