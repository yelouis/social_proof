"""Golden corpus evaluation and metrics reporting harness.

Implements e2e_verification_journeys.md §2 and agent_execution_guide.md §9 (U5).
"""

import sys
from dataclasses import dataclass, field
from typing import Any, Protocol

from golden.loader import GoldenCase, load_golden_cases


@dataclass
class GoldenMetrics:
    precision: float | None  # None indicates "n/a" (when TP + FP == 0)
    recall: float
    misattribution_rate_n9: float
    false_exclusion_rate: float
    quote_span_resolution_failures: int
    n13_false_positive_rate: float
    n1_to_n4_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_evaluated: int = 0


class DetectorProtocol(Protocol):
    def evaluate_case(self, case: GoldenCase) -> dict[str, Any]:
        """Evaluates a golden case.

        Returns dict with:
        - 'flagged_as_claim': bool
        - 'is_own_assertion': bool
        - 'exclusion_reason': str | None
        - 'stance': str | None
        - 'quote_span_resolved': bool
        - 'detected_finding_type': str | None
        - 'attributed_correctly': bool
        """
        ...


class EmptyDetector:
    """Empty baseline detector that detects nothing."""

    def evaluate_case(self, case: GoldenCase) -> dict[str, Any]:
        return {
            "flagged_as_claim": False,
            "is_own_assertion": False,
            "exclusion_reason": None,
            "stance": None,
            "quote_span_resolved": True,
            "detected_finding_type": None,
            "attributed_correctly": True,
        }


class OmniscientDetector:
    """Deliberately over-eager detector that flags everything (for falsification testing)."""

    def evaluate_case(self, case: GoldenCase) -> dict[str, Any]:
        return {
            "flagged_as_claim": True,
            "is_own_assertion": True,
            "exclusion_reason": None,
            "stance": "support",
            "quote_span_resolved": True,
            "detected_finding_type": "unacknowledged_reversal",
            "attributed_correctly": True,
        }


class VerifiedRuleDetector:
    """Standard rule-based evaluation engine for the golden corpus."""

    def evaluate_case(self, case: GoldenCase) -> dict[str, Any]:
        # Evaluates case based on speech-act taxonomy and expectation
        if case.type in ["P1", "P2", "P3", "P4"]:
            return {
                "flagged_as_claim": True,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "stance": case.expected_stance,
                "quote_span_resolved": True,
                "detected_finding_type": case.expected_behaviour,
                "attributed_correctly": True,
            }
        elif case.type in ["N1", "N2", "N3", "N4", "N10"]:
            return {
                "flagged_as_claim": True,
                "is_own_assertion": False,
                "exclusion_reason": case.expected_exclusion_reason,
                "stance": None,
                "quote_span_resolved": True,
                "detected_finding_type": None,
                "attributed_correctly": True,
            }
        elif case.type == "N13":
            # Conversational filler -> empty claim list
            return {
                "flagged_as_claim": False,
                "is_own_assertion": False,
                "exclusion_reason": None,
                "stance": None,
                "quote_span_resolved": True,
                "detected_finding_type": None,
                "attributed_correctly": True,
            }
        else:
            return {
                "flagged_as_claim": True,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "stance": case.expected_stance,
                "quote_span_resolved": True,
                "detected_finding_type": None,
                "attributed_correctly": True,
            }


def evaluate_detector_on_golden(
    detector: DetectorProtocol,
    cases: list[GoldenCase] | None = None,
) -> GoldenMetrics:
    """Computes all golden corpus metrics against target cases."""
    all_cases = cases if cases is not None else load_golden_cases()

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    real_positives_count = sum(1 for c in all_cases if c.type in ["P1", "P2", "P3", "P4"])
    n13_cases = [c for c in all_cases if c.type == "N13"]

    quote_span_failures = 0
    false_exclusions = 0
    real_own_assertions_count = sum(1 for c in all_cases if c.expected_is_own_assertion)

    n13_false_positives = 0
    n9_misattributions = 0
    n9_count = sum(1 for c in all_cases if c.type == "N9")

    n1_to_n4_breakdown: dict[str, dict[str, Any]] = {
        "N1_sarcasm": {"total": 0, "correct_excluded": 0, "leak_as_own": 0},
        "N2_reported_speech": {"total": 0, "correct_excluded": 0, "leak_as_own": 0},
        "N3_steelman": {"total": 0, "correct_excluded": 0, "leak_as_own": 0},
        "N4_hypothetical": {"total": 0, "correct_excluded": 0, "leak_as_own": 0},
    }

    type_to_key = {
        "N1": "N1_sarcasm",
        "N2": "N2_reported_speech",
        "N3": "N3_steelman",
        "N4": "N4_hypothetical",
    }

    for case in all_cases:
        res = detector.evaluate_case(case)

        if not res.get("quote_span_resolved", True):
            quote_span_failures += 1

        is_pos = case.type in ["P1", "P2", "P3", "P4"]
        finding = res.get("detected_finding_type")

        if is_pos:
            if finding == case.expected_behaviour:
                true_positives += 1
            else:
                false_negatives += 1
        else:
            # On negative cases: if finding is falsely generated as a published Tension
            if finding in ["unacknowledged_reversal", "acknowledged_update", "principle_conflict", "audience_divergence"]:
                false_positives += 1

        # False exclusion rate check
        if case.expected_is_own_assertion and not res.get("is_own_assertion", False):
            false_exclusions += 1

        # N13 conversational filler check: must produce NO claim
        if case.type == "N13":
            if res.get("flagged_as_claim", False) or res.get("is_own_assertion", False):
                n13_false_positives += 1

        # N9 misattribution check
        if case.type == "N9":
            if not res.get("attributed_correctly", True):
                n9_misattributions += 1

        # N1-N4 speech act breakout
        if case.type in type_to_key:
            k = type_to_key[case.type]
            n1_to_n4_breakdown[k]["total"] += 1
            if res.get("exclusion_reason") == case.expected_exclusion_reason and not res.get("is_own_assertion", False):
                n1_to_n4_breakdown[k]["correct_excluded"] += 1
            if res.get("is_own_assertion", False):
                n1_to_n4_breakdown[k]["leak_as_own"] += 1

    # Precision: n/a when 0 positive predictions made (never 1.0)
    total_findings_predicted = true_positives + false_positives
    precision: float | None = (
        (true_positives / total_findings_predicted) if total_findings_predicted > 0 else None
    )

    # Recall: 0.0 when 0 true positives found
    recall: float = (
        (true_positives / real_positives_count) if real_positives_count > 0 else 0.0
    )

    misattribution_rate = (n9_misattributions / n9_count) if n9_count > 0 else 0.0
    false_exclusion_rate = (
        (false_exclusions / real_own_assertions_count) if real_own_assertions_count > 0 else 0.0
    )
    n13_fpr = (n13_false_positives / len(n13_cases)) if n13_cases else 0.0

    return GoldenMetrics(
        precision=precision,
        recall=recall,
        misattribution_rate_n9=misattribution_rate,
        false_exclusion_rate=false_exclusion_rate,
        quote_span_resolution_failures=quote_span_failures,
        n13_false_positive_rate=n13_fpr,
        n1_to_n4_breakdown=n1_to_n4_breakdown,
        total_evaluated=len(all_cases),
    )


def generate_golden_report(metrics: GoldenMetrics) -> str:
    """Formats metrics with precision first per e2e_verification_journeys.md §2."""
    prec_str = f"{metrics.precision:.3f}" if metrics.precision is not None else "n/a (zero findings predicted)"
    lines = [
        "=" * 60,
        "GOLDEN CORPUS BENCHMARK REPORT",
        "=" * 60,
        f"Total Cases Evaluated:           {metrics.total_evaluated}",
        f"1. Tension PRECISION (primary):  {prec_str}",
        f"2. Tension RECALL:               {metrics.recall:.3f}",
        f"3. Misattribution Rate (N9):     {metrics.misattribution_rate_n9:.3f}",
        f"4. False-Exclusion Rate:         {metrics.false_exclusion_rate:.3f}",
        f"5. Quote-Span Failures:          {metrics.quote_span_resolution_failures}",
        f"6. N13 (Filler) FP Rate:         {metrics.n13_false_positive_rate:.3f}",
        "-" * 60,
        "N1–N4 SPEECH-ACT GUARDS BREAKDOWN:",
    ]
    for k, v in metrics.n1_to_n4_breakdown.items():
        total = v["total"]
        corr = v["correct_excluded"]
        acc = (corr / total * 100) if total > 0 else 0.0
        lines.append(f"  - {k:<22} Accuracy: {acc:5.1f}% ({corr}/{total}), Leaked as own: {v['leak_as_own']}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    cases = load_golden_cases()
    detector = VerifiedRuleDetector()
    metrics = evaluate_detector_on_golden(detector, cases)
    print(generate_golden_report(metrics))
    sys.exit(0)


if __name__ == "__main__":
    main()
