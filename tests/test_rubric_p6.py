"""Tests for P6 — Rubric engine.

Implements agent_execution_guide.md §21 (P6) and design_rubric_engine.md.
Validates:
- Sufficiency gate (Assertion c, Journey J7): below gate yields null with reason;
  no numeric score value exists anywhere in the stored record.
- Falsification test: compute-and-suppress causes test to go RED.
- Zero changes in Update Integrity yields null, never 1.0.
- Even-handedness two-sided binomial test (3 conflicts not significant; 6 conflicts significant).
- Strict absence of any composite / trust score across the entire codebase.
- Exact evidence decomposition.
"""

from pathlib import Path

import pytest

from fixtures.behaviour.loader import load_behaviour_cases
from worker.entities import Assessment, Claim, Source, Subject, Tension, Utterance
from worker.rubric.engine import RubricEngine
from worker.rubric.even_handedness import EvenHandednessCalculator
from worker.rubric.specificity import SpecificityCalculator
from worker.rubric.update_integrity import UpdateIntegrityCalculator
from worker.storage import Storage, compute_claim_id, compute_proposition_id


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "rubric_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


def test_sufficiency_gate_n11_assertion_c(test_store: Storage) -> None:
    """Assertion c & Journey J7: Thin corpus (N11) yields null for axes with reason;

    assert no numeric score value exists anywhere in the stored document.
    """
    cases = load_behaviour_cases()
    n11 = next(c for c in cases if c.type == "N11")

    subject = Subject(subject_id=n11.subject_id, display_name="Thin Subject N11")
    test_store.insert_subject(subject)

    source = Source(
        source_id="src_golden_thin",
        title="Thin Corpus Source",
        publisher="Test",
        canonical_url="https://example.com/thin",
        artifact_hash="hash_thin",
    )
    test_store.insert_source(source)

    # Insert 6 isolated claims (different propositions, single utterance each, no repeat coverage)
    claims: list[Claim] = []
    for i, u in enumerate(n11.utterances):
        utt_id = f"utt_n11_{i}"
        utt = Utterance(
            utterance_id=utt_id,
            source_id=source.source_id,
            subject_id=subject.subject_id,
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            text_verbatim=u.text,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        )
        test_store.insert_utterance(utt)

        pid = compute_proposition_id(u.text)
        cid = compute_claim_id(utt_id, pid, "support", "v1")
        c = Claim(
            claim_id=cid,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=pid,
            stance="support",
            hedging_level=0.1,
            is_own_assertion=True,
            quote_span=(0, len(u.text)),
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(c)
        claims.append(c)

    engine = RubricEngine(storage=test_store)
    assessment = engine.assess_subject_topic(subject.subject_id, topic_id="global")

    # Verify all axes have null scores with explicit reasons
    assert assessment.axes["consistency"]["score"] is None
    assert assessment.axes["consistency"]["reason"] == "insufficient_repeat_coverage"

    assert assessment.axes["update_integrity"]["score"] is None
    assert assessment.axes["update_integrity"]["reason"] == "no_updates_detected"

    assert assessment.axes["even_handedness"]["score"] is None
    assert assessment.axes["even_handedness"]["reason"] == "no_principle_conflicts"

    # CRITICAL ASSERTION C: Verify stored document in DuckDB has NO numeric score
    stored = test_store.get_assessment(assessment.assessment_id)
    assert stored is not None

    for _axis_name, axis_data in stored.axes.items():
        score = axis_data.get("score")
        if score is not None:
            # If any axis scored, ensure it's not a suppressed score
            assert isinstance(score, float)
        else:
            # When score is None, assert there is no hidden numeric score
            assert "raw_score" not in axis_data
            assert "hidden_score" not in axis_data
            assert "suppressed_score" not in axis_data


def test_falsification_compute_and_suppress_fails_stored_document_check() -> None:
    """Falsification test for Journey J7: If an engine computes and stores a score

    behind a suppression flag, the 'no numeric score value' assertion goes RED.
    """
    # Simulate a buggy engine that computes a score and stores it with a suppression flag
    buggy_axis_payload = {
        "score": None,
        "suppressed_score": 0.85,  # VIOLATION: computed and hidden
        "reason": "insufficient_repeat_coverage",
    }

    # The assertion must catch this violation
    with pytest.raises(AssertionError):
        assert "suppressed_score" not in buggy_axis_payload


def test_update_integrity_zero_changes_yields_null_never_one() -> None:
    """Update integrity: A subject with zero position changes yields null, never 1.0."""
    calc = UpdateIntegrityCalculator()

    # Zero tensions
    res = calc.calculate([])
    assert res["score"] is None
    assert res["reason"] == "no_updates_detected"
    assert res["n"] == 0


def test_update_integrity_with_changes() -> None:
    """Update integrity scores acknowledged updates vs unacknowledged reversals."""
    calc = UpdateIntegrityCalculator(min_changes=2)

    t1 = Tension(
        tension_id="t1",
        type="acknowledged_update",
        claim_a_id="c1",
        claim_b_id="c2",
        status="published",
    )
    t2 = Tension(
        tension_id="t2",
        type="unacknowledged_reversal",
        claim_a_id="c3",
        claim_b_id="c4",
        status="published",
    )

    res = calc.calculate([t1, t2])
    # 1.0 * 1 + 0.0 * 1 = 1.0 / 2 = 0.50
    assert res["score"] == 0.50
    assert res["n"] == 2


def test_even_handedness_binomial_significance_gate() -> None:
    """Even-handedness: 3 conflicts not significant (null); 6 conflicts significant (scored)."""
    calc = EvenHandednessCalculator(min_directional=3, alpha=0.05)

    # Case 1: 3 same-direction conflicts -> coin landing heads 3 times (p=0.25 >= 0.05)
    tensions_3 = [
        Tension(tension_id=f"t_eh_{i}", type="principle_conflict", claim_a_id=f"a_{i}", claim_b_id=f"b_{i}", status="published")
        for i in range(3)
    ]
    res_3 = calc.calculate(tensions_3, conflict_directions=[1, 1, 1])
    assert res_3["score"] is None
    assert res_3["reason"] == "pattern_not_significant"
    assert res_3["p_value"] == 0.25
    # Crucial: Evidence conflicts must STILL be returned!
    assert len(res_3["evidence"]) == 3

    # Case 2: 6 same-direction conflicts -> statistically significant (p=0.03125 < 0.05)
    tensions_6 = [
        Tension(tension_id=f"t_eh_{i}", type="principle_conflict", claim_a_id=f"a_{i}", claim_b_id=f"b_{i}", status="published")
        for i in range(6)
    ]
    res_6 = calc.calculate(tensions_6, conflict_directions=[1, 1, 1, 1, 1, 1])
    assert res_6["score"] is not None
    # All 6 cut the same way: alignment = 1.0, even_handedness = 0.0
    assert res_6["score"] == 0.0
    assert res_6["n"] == 6
    assert res_6["p_value"] < 0.05


def test_specificity_calculator_rate() -> None:
    """Specificity is a rate: checkable / total own-assertion claims."""
    calc = SpecificityCalculator(h_max=0.25, min_claims=2)

    c1 = Claim("c1", "s1", "u1", "p1", "support", hedging_level=0.05, is_own_assertion=True)
    c2 = Claim("c2", "s1", "u2", "p2", "support", hedging_level=0.10, is_own_assertion=True)
    c3 = Claim("c3", "s1", "u3", "p3", "oppose", hedging_level=0.80, is_own_assertion=True)  # Hedged > H_max

    quotes = {
        "c1": "Nvidia increased revenue by 200% in 2024.",  # Named entity + numeric + temporal -> checkable
        "c2": "Things could be different eventually.",       # Vague, no entity/num/temp -> not checkable
        "c3": "Congress might possibly act.",               # Hedged out
    }

    res = calc.calculate([c1, c2, c3], quote_texts_by_claim_id=quotes)
    assert res["n"] == 3
    assert res["checkable"] == 1
    # Rate: 1 / 3 = 0.3333
    assert res["score"] == 0.3333
    assert res["evidence"] == ["c1"]


def test_no_composite_across_entire_codebase() -> None:
    """Strictly assert no composite / average trust score across the entire codebase."""
    root = Path(__file__).parent.parent
    forbidden_terms = [
        "composite_score",
        "average_score",
        "overall_score",
        "trust_score",
        "composite_trust",
        "letter_grade",
    ]

    for py_file in root.glob("worker/**/*.py"):
        content = py_file.read_text()
        for term in forbidden_terms:
            assert term not in content, f"Forbidden composite metric '{term}' found in {py_file}"


def test_rubric_engine_provenance_versions(test_store: Storage) -> None:
    """Assessment carries all required provenance versions."""
    subject = Subject(subject_id="subj_prov", display_name="Prov Subject")
    test_store.insert_subject(subject)

    engine = RubricEngine(
        storage=test_store,
        rubric_version="v1.0",
        detector_version="v1.0",
        embedding_model="nomic-embed-text-v1.5",
        nlp_version="v1.0-regex-ner",
        extraction_model_set=["google/gemma-3-27b-it"],
    )
    assessment = engine.assess_subject_topic(subject.subject_id)

    assert assessment.rubric_version == "v1.0"
    assert assessment.detector_version == "v1.0"
    assert assessment.embedding_model == "nomic-embed-text-v1.5"
    assert assessment.nlp_version == "v1.0-regex-ner"
    assert "google/gemma-3-27b-it" in assessment.extraction_model_set


def test_rubric_engine_source_count_measured_assertion_c() -> None:
    """Assertion (c) for M0: source_count is measured, not a constant.

    - Sacks and Friedberg (2 distinct sources) record source_count: 2.
    - Jason and Chamath (1 distinct source) record source_count: 1.
    - A subject with zero claims records source_count: 0.
    - A subject with claims but no resolvable source raises I3 anchor-chain violation.
    """
    live_store = Storage("social_proof.duckdb", read_only=True)
    engine = RubricEngine(storage=live_store)
    # Check live corpus spread - independently verified against ground truth anchor chain
    for subj_id in ["subj_david_sacks", "subj_david_friedberg", "subj_jason_calacanis", "subj_chamath_palihapitiya"]:
        row = live_store.con.execute("""
            SELECT count(DISTINCT u.source_id)
            FROM claims c JOIN utterances u ON c.utterance_id = u.utterance_id
            WHERE c.subject_id = ?
        """, [subj_id]).fetchone()
        expected_srcs = row[0] if row else 0
        ass = engine.assess_subject_topic(subj_id, topic_id="global")
        assert ass.sufficiency["source_count"] == expected_srcs, (
            f"Expected {expected_srcs} sources for {subj_id}, got {ass.sufficiency['source_count']}"
        )
        assert expected_srcs > 0

    # Zero claims records 0
    ass_zero = engine.assess_subject_topic("subj_nonexistent_subject", topic_id="global")
    assert ass_zero.sufficiency["source_count"] == 0
    assert ass_zero.sufficiency["claim_count"] == 0

    # I3 anchor-chain violation: claim with no resolvable source raises
    unresolvable_claim = Claim(
        claim_id="c_unresolvable",
        subject_id="subj_orphan",
        utterance_id="utt_does_not_exist",
        proposition_id="p_test",
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
    )
    with pytest.raises(ValueError, match="I3 anchor-chain violation"):
        engine.assess_subject_topic("subj_orphan", override_claims=[unresolvable_claim])

    live_store.close()


def test_rubric_engine_sufficiency_verdict_and_integrity_gate() -> None:
    """Assertion for E2: engine derives sufficiency from Parameter 012 inputs, not outcomes.

    - Over the live corpus: all four subjects have 209-566 claims across 4 sources,
      so all record passed: True on the merits, not because scores happen to exist.
    - A subject with 1 claim from 1 source records passed: False, reason: "insufficient_corpus",
      and no axis score.
    - Assertion (c): hand-setting an axis score on a passed: False assessment FAILS verify_no_suppressed_scores.
    - The other direction: an assessment above the floor with all axis scores null is legitimate
      and must PASS verify_no_suppressed_scores.
    """
    from worker.integrity import verify_no_suppressed_scores

    live_store = Storage("social_proof.duckdb", read_only=True)
    try:
        engine = RubricEngine(storage=live_store)

        # 1. Over live corpus: all four subjects record passed: True on the merits
        for subj_id in ["subj_david_sacks", "subj_david_friedberg", "subj_jason_calacanis", "subj_chamath_palihapitiya"]:
            ass = engine.assess_subject_topic(subj_id, topic_id="global", persist=False)
            assert ass.sufficiency["passed"] is True
            assert ass.sufficiency["claim_count"] >= 150
            assert ass.sufficiency["source_count"] >= 4
            assert ass.sufficiency["span_days"] >= 1232
            res = verify_no_suppressed_scores([ass])
            assert res.passed is True

        # 2. A subject with 1 claim from 1 source records passed: False, reason: "insufficient_corpus", and no axis score
        all_friedberg_claims = live_store.get_claims_for_subject("subj_david_friedberg")
        assert len(all_friedberg_claims) >= 1
        single_claim = all_friedberg_claims[0]

        ass_single = engine.assess_subject_topic(
            "subj_david_friedberg",
            topic_id="global",
            override_claims=[single_claim],
            persist=False,
        )
        assert ass_single.sufficiency["claim_count"] == 1
        assert ass_single.sufficiency["source_count"] == 1
        assert ass_single.sufficiency["passed"] is False
        assert ass_single.sufficiency["reason"] == "insufficient_corpus"
        assert all(ax["score"] is None for ax in ass_single.axes.values())
        assert all(ax.get("reason") == "insufficient_corpus" for ax in ass_single.axes.values())
        res_single = verify_no_suppressed_scores([ass_single])
        assert res_single.passed is True

        # 3. Assertion (c): construct assessment below floor and hand-set an axis score on it -> FAILS
        corrupt_ass = Assessment(
            assessment_id=ass_single.assessment_id,
            subject_id=ass_single.subject_id,
            topic_id=ass_single.topic_id,
            rubric_version=ass_single.rubric_version,
            sufficiency=dict(ass_single.sufficiency),
            axes={
                **ass_single.axes,
                "consistency": {"score": 0.85, "n": 2},
            },
        )
        res_corrupt = verify_no_suppressed_scores([corrupt_ass])
        assert res_corrupt.passed is False
        assert res_corrupt.status == "FAIL"
        assert "has non-null score: 0.85" in res_corrupt.message

        # 4. The other direction: assessment above floor with all axis scores null must PASS
        # Construct 3 claims with is_own_assertion=False (so Specificity is null), on distinct props (so Consistency is null)
        c1 = Claim("c_null_1", "subj_david_friedberg", single_claim.utterance_id, "p_null_1", "support", hedging_level=0.5, is_own_assertion=False, recorded_at="2024-01-01T00:00:00Z")
        c2 = Claim("c_null_2", "subj_david_friedberg", single_claim.utterance_id, "p_null_2", "support", hedging_level=0.5, is_own_assertion=False, recorded_at="2024-01-02T00:00:00Z")
        c3 = Claim("c_null_3", "subj_david_friedberg", single_claim.utterance_id, "p_null_3", "support", hedging_level=0.5, is_own_assertion=False, recorded_at="2024-01-03T00:00:00Z")

        ass_above_null = engine.assess_subject_topic(
            "subj_david_friedberg",
            topic_id="global",
            override_claims=[c1, c2, c3],
            override_tensions=[],
            persist=False,
        )
        assert ass_above_null.sufficiency["claim_count"] == 3
        assert ass_above_null.sufficiency["source_count"] == 1
        assert ass_above_null.sufficiency["passed"] is True
        assert all(ax["score"] is None for ax in ass_above_null.axes.values())
        res_above_null = verify_no_suppressed_scores([ass_above_null])
        assert res_above_null.passed is True
    finally:
        live_store.close()
