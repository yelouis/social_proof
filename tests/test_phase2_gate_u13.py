"""Phase 2 Gate tests (Journey J3, N1-N4 breakdown, and Reversal Detection) (U13)."""

from pathlib import Path

from golden.loader import load_golden_cases
from worker.entities import Claim, Proposition, Source, Subject, Utterance
from worker.extract.dedup import stub_hash_embedding
from worker.golden.report import (
    VerifiedRuleDetector,
    evaluate_detector_on_golden,
    generate_golden_report,
)
from worker.storage import Storage, compute_claim_id, compute_proposition_id, compute_utterance_id


def test_phase_2_gate_journey_j3_reversal_detector_on_live_claims(tmp_path: Path) -> None:
    """Journey J3: Core reversal detector query against live storage.

    Subject makes Claim A (support) in 2022, Claim B (oppose) in 2024 on the same proposition.
    The DuckDB self-join finds the contradiction.
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    subject = Subject(subject_id="subj_p1_01", display_name="Dr. Jane Doe")
    store.insert_subject(subject)

    prop_text = "frontier AI model licensing requirement"
    prop_id = compute_proposition_id(prop_text)
    prop = Proposition(
        proposition_id=prop_id,
        canonical_text=prop_text,
        subject_ids=[subject.subject_id],
        claim_count=2,
    )
    store.insert_proposition(prop)
    store.insert_proposition_embedding(prop_id, stub_hash_embedding(prop_text))

    # Source 1 (2022)
    src1 = Source(
        source_id="src_2022",
        tier="B",
        title="2022 Interview",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=src2022",
        artifact_hash="hash_2022",
        recorded_at="2022-06-01T12:00:00Z",
    )
    store.insert_source(src1)

    utt1_text = "We must mandate federal licensing for all large frontier models."
    utt1_id = compute_utterance_id(src1.source_id, 1000, utt1_text)
    utt1 = Utterance(
        utterance_id=utt1_id,
        source_id=src1.source_id,
        subject_id=subject.subject_id,
        text_verbatim=utt1_text,
        start_ms=1000,
        end_ms=5000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
    )
    store.insert_utterance(utt1)

    claim1_id = compute_claim_id(utt1_id, prop_id, "support", "gemma-3-27b-it:v1.0:s1")
    claim1 = Claim(
        claim_id=claim1_id,
        subject_id=subject.subject_id,
        utterance_id=utt1_id,
        proposition_id=prop_id,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_span=(8, 63),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
        recorded_at=src1.recorded_at,
    )
    store.insert_claim(claim1)

    # Source 2 (2024)
    src2 = Source(
        source_id="src_2024",
        tier="B",
        title="2024 Interview",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=src2024",
        artifact_hash="hash_2024",
        recorded_at="2024-06-01T12:00:00Z",
    )
    store.insert_source(src2)

    utt2_text = "Mandating federal licensing for frontier models would stifle open innovation."
    utt2_id = compute_utterance_id(src2.source_id, 2000, utt2_text)
    utt2 = Utterance(
        utterance_id=utt2_id,
        source_id=src2.source_id,
        subject_id=subject.subject_id,
        text_verbatim=utt2_text,
        start_ms=2000,
        end_ms=6000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
    )
    store.insert_utterance(utt2)

    claim2_id = compute_claim_id(utt2_id, prop_id, "oppose", "gemma-3-27b-it:v1.0:s1")
    claim2 = Claim(
        claim_id=claim2_id,
        subject_id=subject.subject_id,
        utterance_id=utt2_id,
        proposition_id=prop_id,
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_span=(0, 48),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
        recorded_at=src2.recorded_at,
    )
    store.insert_claim(claim2)

    # Run Reversal Detector Query
    reversals = store.detect_unacknowledged_reversals(subject.subject_id)
    assert len(reversals) == 1
    earlier_c, later_c, p_id = reversals[0]
    assert earlier_c == claim1_id
    assert later_c == claim2_id
    assert p_id == prop_id


def test_phase_2_gate_golden_metrics_and_n1_to_n4_breakdown() -> None:
    """Evaluates golden corpus against gate targets."""
    cases = load_golden_cases()
    detector = VerifiedRuleDetector()
    metrics = evaluate_detector_on_golden(detector, cases)

    # Gate Targets:
    assert metrics.precision is not None and metrics.precision >= 0.95
    assert metrics.recall >= 0.60
    assert metrics.misattribution_rate_n9 == 0.0
    assert metrics.false_exclusion_rate <= 0.10
    assert metrics.quote_span_resolution_failures == 0
    assert metrics.n13_false_positive_rate == 0.0

    # N1-N4 Speech-Act Breakdown:
    n1 = metrics.n1_to_n4_breakdown["N1_sarcasm"]
    assert n1["correct_excluded"] == n1["total"] == 1
    assert n1["leak_as_own"] == 0

    n2 = metrics.n1_to_n4_breakdown["N2_reported_speech"]
    assert n2["correct_excluded"] == n2["total"] == 1
    assert n2["leak_as_own"] == 0

    n3 = metrics.n1_to_n4_breakdown["N3_steelman"]
    assert n3["correct_excluded"] == n3["total"] == 1
    assert n3["leak_as_own"] == 0

    n4 = metrics.n1_to_n4_breakdown["N4_hypothetical"]
    assert n4["correct_excluded"] == n4["total"] == 1
    assert n4["leak_as_own"] == 0

    report = generate_golden_report(metrics)
    assert "Tension PRECISION (primary):  1.000" in report
    assert "N1_sarcasm             Accuracy: 100.0%" in report


def test_falsification_dropping_sarcasm_guard_leaks_n1_as_own_claim() -> None:
    """Falsification test: Dropping sarcasm detection causes N1 case to leak as own assertion."""
    class BrokenSarcasmDetector(VerifiedRuleDetector):
        def evaluate_case(self, case):  # type: ignore[no-untyped-def]
            if case.type == "N1":
                # Leaking sarcasm as subject's own claim
                return {
                    "flagged_as_claim": True,
                    "is_own_assertion": True,  # Leaked!
                    "exclusion_reason": None,
                    "stance": "support",
                    "quote_span_resolved": True,
                    "detected_finding_type": "unacknowledged_reversal",
                    "attributed_correctly": True,
                }
            return super().evaluate_case(case)

    broken_detector = BrokenSarcasmDetector()
    metrics = evaluate_detector_on_golden(broken_detector)

    # N1 accuracy drops to 0 and leak_as_own is 1
    n1_stat = metrics.n1_to_n4_breakdown["N1_sarcasm"]
    assert n1_stat["leak_as_own"] == 1
    assert n1_stat["correct_excluded"] == 0  # Falsification confirmed!
