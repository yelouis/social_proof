"""Unit and falsification tests for Golden Corpus scaffold and reporting (U5)."""

from golden.loader import load_golden_cases
from worker.golden.report import (
    EmptyDetector,
    OmniscientDetector,
    VerifiedRuleDetector,
    evaluate_detector_on_golden,
    generate_golden_report,
)


def test_golden_cases_load_and_validate_structure() -> None:
    cases = load_golden_cases()
    assert len(cases) >= 15
    types = {c.type for c in cases}
    assert "P1" in types
    assert "P2" in types
    assert "N1" in types
    assert "N2" in types
    assert "N3" in types
    assert "N4" in types
    assert "N13" in types

    for c in cases:
        assert c.case_id != ""
        assert c.subject_id != ""
        assert c.source_locator.startswith("https://")
        start, end = c.span
        assert 0 <= start <= end <= len(c.text_snippet)


def test_empty_detector_reports_precision_na_and_recall_zero() -> None:
    """The harness run against an empty detector reports precision n/a and recall 0 — NOT precision 1.0."""
    detector = EmptyDetector()
    metrics = evaluate_detector_on_golden(detector)

    assert metrics.precision is None  # Renders as 'n/a'
    assert metrics.recall == 0.0

    report = generate_golden_report(metrics)
    assert "n/a" in report
    assert "1.000" not in report.split("1. Tension PRECISION (primary):")[1].split("\n")[0]


def test_verified_detector_meets_golden_targets() -> None:
    detector = VerifiedRuleDetector()
    metrics = evaluate_detector_on_golden(detector)

    assert metrics.precision is not None and metrics.precision >= 0.95
    assert metrics.recall >= 0.60
    assert metrics.misattribution_rate_n9 == 0.0
    assert metrics.false_exclusion_rate <= 0.10
    assert metrics.quote_span_resolution_failures == 0
    assert metrics.n13_false_positive_rate == 0.0

    report = generate_golden_report(metrics)
    assert "1.000" in report
    assert "N13 (Filler) FP Rate:         0.000" in report


def test_falsification_omniscient_detector_collapses_precision() -> None:
    """Falsification test: Omniscient detector that flags everything causes precision to collapse."""
    detector = OmniscientDetector()
    metrics = evaluate_detector_on_golden(detector)

    assert metrics.precision is not None
    # Precision collapses because all negative cases (N1-N13) produce false positives
    assert metrics.precision <= 0.30
    assert metrics.n13_false_positive_rate == 1.0  # Falsification confirmed!
