import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from fixtures.behaviour.loader import ALL_BEHAVIOUR_CLASSES, PAIR_TYPE_CLASSES, load_behaviour_cases
from golden.loader import GoldenCase, load_golden_cases
from worker.golden.report import (
    VerifiedRuleDetector,
    evaluate_behaviour_fixtures,
    evaluate_golden_corpus,
    generate_full_report,
)


def test_behaviour_fixtures_load_and_run_binary_regression() -> None:
    """Behaviour fixtures evaluate binary PASS/FAIL regression with zero quality percentages."""
    cases = load_behaviour_cases()
    assert len(cases) == 20
    for c in cases:
        assert c.locator_kind == "synthetic"

    detector = VerifiedRuleDetector()
    results = evaluate_behaviour_fixtures(detector, cases)
    assert len(results) == 20
    assert all(r.passed for r in results)

    # Full report verification
    report = generate_full_report(detector, behaviour_cases=cases, golden_cases=[])
    fixture_section = report.split("BEHAVIOUR FIXTURES (regression only — never a quality measure)")[1].split("GOLDEN CORPUS METRICS")[0]

    # Assert NO percentage (%) or decimal rate appears in the fixture regression block
    assert "%" not in fixture_section
    assert not re.search(r"\b0\.\d+\b", fixture_section)
    assert not re.search(r"\b1\.\d+\b", fixture_section)
    assert "Result: 20/20 PASS" in fixture_section


def test_all_17_classes_present_in_behaviour_fixtures() -> None:
    """All 17 case classes must be present in behaviour fixtures per e2e_verification_journeys.md §2."""
    cases = load_behaviour_cases()
    present_classes = {c.type for c in cases}
    assert present_classes == ALL_BEHAVIOUR_CLASSES
    assert len(ALL_BEHAVIOUR_CLASSES) == 17


def test_loader_rejects_missing_recorded_at(tmp_path: Path) -> None:
    """Loader rejects any case whose utterances lack recorded_at."""
    bad_data = [
        {
            "case_id": "bad_case",
            "type": "N1",
            "subject_id": "subj_01",
            "source_locator": "https://example.com/s",
            "utterances": [
                {
                    "text": "Some text",
                    "span": [0, 9],
                }
            ],
            "expected_behaviour": "excluded",
            "locator_kind": "synthetic",
        }
    ]
    bad_file = tmp_path / "bad_cases.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks required 'recorded_at'"):
        load_behaviour_cases(bad_file)


def test_loader_rejects_pair_case_with_fewer_than_two_utterances(tmp_path: Path) -> None:
    """Loader rejects any pair-type case carrying fewer than two utterances."""
    for pair_type in ["P1", "P2", "P3", "P4", "N5", "N7", "N8", "N12"]:
        assert pair_type in PAIR_TYPE_CLASSES
        bad_data = [
            {
                "case_id": f"bad_{pair_type}",
                "type": pair_type,
                "subject_id": "subj_01",
                "source_locator": "https://example.com/s",
                "utterances": [
                    {
                        "text": "Single utterance only",
                        "recorded_at": "2024-01-01T10:00:00Z",
                        "span": [0, 21],
                    }
                ],
                "expected_behaviour": "unacknowledged_reversal",
                "locator_kind": "synthetic",
            }
        ]
        bad_file = tmp_path / f"bad_{pair_type}.json"
        bad_file.write_text(json.dumps(bad_data), encoding="utf-8")
        with pytest.raises(ValueError, match="requires at least 2 utterances"):
            load_behaviour_cases(bad_file)


def test_loader_rejects_thin_corpus_case_with_fewer_than_six_utterances(tmp_path: Path) -> None:
    """Loader rejects any N11 thin-corpus case carrying fewer than six utterances."""
    bad_data = [
        {
            "case_id": "bad_n11",
            "type": "N11",
            "subject_id": "subj_01",
            "source_locator": "https://example.com/s",
            "utterances": [
                {
                    "text": f"Claim number {i}",
                    "recorded_at": f"2024-0{i+1}-01T10:00:00Z",
                    "span": [0, 14],
                }
                for i in range(5)
            ],
            "expected_behaviour": "insufficient_corpus",
            "locator_kind": "synthetic",
        }
    ]
    bad_file = tmp_path / "bad_n11.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="requires at least 6 utterances"):
        load_behaviour_cases(bad_file)


def test_utterances_orderable_and_p2_marker_in_interval() -> None:
    """Utterances within every case are orderable by recorded_at, and P2's marker is in the interval."""
    cases = load_behaviour_cases()
    for c in cases:
        for u in c.utterances:
            dt = datetime.fromisoformat(u.recorded_at.replace("Z", "+00:00"))
            assert dt is not None

    p2 = next(c for c in cases if c.type == "P2")
    assert len(p2.utterances) >= 3
    t1 = datetime.fromisoformat(p2.utterances[0].recorded_at.replace("Z", "+00:00"))
    marker_utts = [u for u in p2.utterances if u.change_marker]
    assert len(marker_utts) == 1
    t_marker = datetime.fromisoformat(marker_utts[0].recorded_at.replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(p2.utterances[-1].recorded_at.replace("Z", "+00:00"))
    assert t1 < t_marker < t2


def test_golden_corpus_empty_reports_not_measured_never_zero_or_one() -> None:
    """An empty golden corpus reports NOT MEASURED with sample size 0, not 0.0 or 1.0."""
    cases = load_golden_cases()
    assert len(cases) == 0

    detector = VerifiedRuleDetector()
    metrics = evaluate_golden_corpus(detector, cases)
    assert metrics.total_cases == 0
    assert metrics.aggregate_precision is None
    assert metrics.aggregate_recall is None

    report = generate_full_report(detector, golden_cases=cases)
    assert "Precision .......... NOT MEASURED — n=0, minimum 5" in report
    assert "Recall ............. NOT MEASURED — n=0, minimum 5" in report
    assert "N1 speech-act guard ... NOT MEASURED — n=0, minimum 5" in report
    assert "Misattribution (N9)  NOT MEASURED — n=0, minimum 5" in report


def test_per_class_floor_of_five_enforced() -> None:
    """Rates are only printable when a class has at least 5 cases."""
    def make_case(cid: str, cls: str) -> GoldenCase:
        return GoldenCase(
            case_id=cid,
            class_name=cls,
            subject_id="subj_01",
            source_id="src_01",
            utterance_id="utt_01",
            span=(0, 10),
            expected_behaviour="unacknowledged_reversal" if cls.startswith("P") else "excluded",
            verified_by="human_auditor",
            verified_at="2026-08-17T00:00:00Z",
            locator_kind="real",
            label_source="human",
        )

    # 4 cases -> NOT MEASURED
    four_cases = [make_case(f"c_{i}", "P1") for i in range(4)]
    metrics_4 = evaluate_golden_corpus(cases=four_cases, min_floor=5)
    assert metrics_4.precision_by_class["P1"] is None

    # 5 cases -> number computed
    five_cases = [make_case(f"c_{i}", "P1") for i in range(5)]
    metrics_5 = evaluate_golden_corpus(cases=five_cases, min_floor=5)
    assert metrics_5.precision_by_class["P1"] == 1.0


def test_circularity_guard_rejects_matching_extractor_model() -> None:
    """Circularity guard: A case pre-labelled by the same model as the extractor under test raises ValueError."""
    tmp_golden_file = Path("/tmp/test_circ_golden.json")
    data = [
        {
            "case_id": "circ_01",
            "class_name": "P1",
            "subject_id": "subj_01",
            "source_id": "src_01",
            "utterance_id": "utt_01",
            "span": [0, 10],
            "expected_behaviour": "unacknowledged_reversal",
            "verified_by": "auto",
            "verified_at": "2026-08-17T00:00:00Z",
            "locator_kind": "real",
            "label_source": "model_only",
            "labeller_model": "gemma-3-27b-it",
        }
    ]
    tmp_golden_file.write_text(json.dumps(data))
    try:
        with pytest.raises(ValueError, match="Circularity guard violation"):
            load_golden_cases(tmp_golden_file, current_extractor_model="gemma-3-27b-it")
    finally:
        if tmp_golden_file.exists():
            tmp_golden_file.unlink()


def test_falsification_pointing_golden_loader_at_behaviour_fixtures_fails() -> None:
    """Falsification test: Pointing golden/loader at synthetic behaviour fixtures raises ValueError."""
    with pytest.raises(ValueError, match="GoldenCase loader rejects synthetic locator_kind"):
        load_golden_cases("fixtures/behaviour/cases.json")  # Falsification confirmed!
