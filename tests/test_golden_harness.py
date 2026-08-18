import json
import re
from pathlib import Path

import pytest

from fixtures.behaviour.loader import load_behaviour_cases
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
    assert len(cases) == 16
    for c in cases:
        assert c.locator_kind == "synthetic"

    detector = VerifiedRuleDetector()
    results = evaluate_behaviour_fixtures(detector, cases)
    assert len(results) == 16
    assert all(r.passed for r in results)

    # Full report verification
    report = generate_full_report(detector, behaviour_cases=cases, golden_cases=[])
    fixture_section = report.split("BEHAVIOUR FIXTURES (regression only — never a quality measure)")[1].split("GOLDEN CORPUS METRICS")[0]

    # Assert NO percentage (%) or decimal rate appears in the fixture regression block
    assert "%" not in fixture_section
    assert not re.search(r"\b0\.\d+\b", fixture_section)
    assert not re.search(r"\b1\.\d+\b", fixture_section)


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
