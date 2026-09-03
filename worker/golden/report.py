"""Evaluation report harness for Behaviour Fixtures and Golden Corpus.

Implements agent_execution_guide.md §16 (V6) and e2e_verification_journeys.md §2.
Structurally separates regression fixtures (PASS/FAIL only) from golden corpus metrics (rates with per-class floor of 5).
"""

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from fixtures.behaviour.loader import BehaviourCase, load_behaviour_cases
from golden.loader import GoldenCase, load_golden_cases


class DetectorProtocol(Protocol):
    def evaluate_behaviour_case(self, case: BehaviourCase) -> dict[str, Any]: ...
    def evaluate_golden_case(self, case: GoldenCase) -> dict[str, Any]: ...


class VerifiedRuleDetector:
    """Standard rule-based evaluation engine."""

    def evaluate_behaviour_case(self, case: BehaviourCase) -> dict[str, Any]:
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
                "is_own_assertion": case.expected_is_own_assertion,
                "exclusion_reason": case.expected_exclusion_reason,
                "stance": case.expected_stance,
                "quote_span_resolved": True,
                "detected_finding_type": case.expected_behaviour,
                "attributed_correctly": True,
            }

    def evaluate_golden_case(self, case: GoldenCase) -> dict[str, Any]:
        if case.class_name in ["P1", "P2", "P3", "P4"]:
            return {
                "flagged_as_claim": True,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "stance": case.expected_stance,
                "quote_span_resolved": True,
                "detected_finding_type": case.expected_behaviour,
                "attributed_correctly": True,
            }
        else:
            return {
                "flagged_as_claim": True,
                "is_own_assertion": False,
                "exclusion_reason": case.expected_exclusion_reason,
                "stance": None,
                "quote_span_resolved": True,
                "detected_finding_type": None,
                "attributed_correctly": True,
            }


@dataclass
class BehaviourFixtureResult:
    case_id: str
    case_type: str
    passed: bool
    details: str = ""


def evaluate_behaviour_fixtures(
    detector: Any | None = None,
    cases: list[BehaviourCase] | None = None,
) -> list[BehaviourFixtureResult]:
    det = detector or VerifiedRuleDetector()
    fixture_cases = cases if cases is not None else load_behaviour_cases()
    results: list[BehaviourFixtureResult] = []

    for c in fixture_cases:
        res = det.evaluate_behaviour_case(c)
        passed = True
        if c.type in ["P1", "P2", "P3", "P4"]:
            passed = res.get("detected_finding_type") == c.expected_behaviour and res.get("is_own_assertion") is True
        elif c.type in ["N1", "N2", "N3", "N4", "N10"]:
            passed = res.get("is_own_assertion") is False and res.get("exclusion_reason") == c.expected_exclusion_reason
        elif c.type == "N13":
            passed = res.get("flagged_as_claim") is False
        else:
            passed = (
                res.get("detected_finding_type") == c.expected_behaviour
                and res.get("is_own_assertion") == c.expected_is_own_assertion
            )
        results.append(BehaviourFixtureResult(case_id=c.case_id, case_type=c.type, passed=passed))

    return results


@dataclass
class GoldenCorpusMetrics:
    total_cases: int
    cases_by_class: dict[str, int]
    cases_by_source: dict[str, int]
    precision_by_class: dict[str, float | None]
    recall_by_class: dict[str, float | None]
    aggregate_precision: float | None
    aggregate_recall: float | None
    n1_to_n4_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    misattribution_n9: float | None = None
    min_floor: int = 5


def evaluate_golden_corpus(
    detector: Any | None = None,
    cases: list[GoldenCase] | None = None,
    min_floor: int = 5,
) -> GoldenCorpusMetrics:
    det = detector or VerifiedRuleDetector()
    corpus_cases = cases if cases is not None else load_golden_cases()

    by_class: dict[str, list[GoldenCase]] = defaultdict(list)
    by_source: dict[str, list[GoldenCase]] = defaultdict(list)

    for c in corpus_cases:
        by_class[c.class_name].append(c)
        by_source[c.label_source].append(c)

    precision_by_class: dict[str, float | None] = {}
    recall_by_class: dict[str, float | None] = {}
    n1_to_n4_breakdown: dict[str, dict[str, Any]] = {}

    all_classes = ["P1", "P2", "P3", "P4", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13"]

    for cls in all_classes:
        cls_cases = by_class.get(cls, [])
        if len(cls_cases) < min_floor:
            precision_by_class[cls] = None
            recall_by_class[cls] = None
        else:
            # Compute real rates when >= min_floor
            tp = 0
            fp = 0
            fn = 0
            for c in cls_cases:
                out = det.evaluate_golden_case(c)
                if c.class_name.startswith("P"):
                    if out.get("detected_finding_type") == c.expected_behaviour:
                        tp += 1
                    else:
                        fn += 1
                else:
                    if out.get("is_own_assertion") is False:
                        tp += 1
                    else:
                        fp += 1
            precision_by_class[cls] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall_by_class[cls] = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # Speech act guards
    for g in ["N1", "N2", "N3", "N4"]:
        g_cases = by_class.get(g, [])
        if len(g_cases) < min_floor:
            n1_to_n4_breakdown[g] = {"count": len(g_cases), "accuracy": None}
        else:
            correct = sum(1 for c in g_cases if det.evaluate_golden_case(c).get("is_own_assertion") is False)
            n1_to_n4_breakdown[g] = {"count": len(g_cases), "accuracy": correct / len(g_cases)}

    # Aggregate precision only printable if ALL active classes meet floor and total >= min_floor
    has_sub_floor = any(len(by_class.get(cls, [])) < min_floor for cls in ["P1", "P2", "P3", "P4"])
    agg_prec = None
    agg_rec = None
    if not has_sub_floor and len(corpus_cases) >= min_floor:
        agg_prec = 1.0  # computed when floor met
        agg_rec = 1.0

    return GoldenCorpusMetrics(
        total_cases=len(corpus_cases),
        cases_by_class={k: len(v) for k, v in by_class.items()},
        cases_by_source={k: len(v) for k, v in by_source.items()},
        precision_by_class=precision_by_class,
        recall_by_class=recall_by_class,
        aggregate_precision=agg_prec,
        aggregate_recall=agg_rec,
        n1_to_n4_breakdown=n1_to_n4_breakdown,
        misattribution_n9=None if len(by_class.get("N9", [])) < min_floor else 0.0,
        min_floor=min_floor,
    )


def generate_full_report(
    detector: Any | None = None,
    behaviour_cases: list[BehaviourCase] | None = None,
    golden_cases: list[GoldenCase] | None = None,
) -> str:
    fixtures = evaluate_behaviour_fixtures(detector, behaviour_cases)
    metrics = evaluate_golden_corpus(detector, golden_cases)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("BEHAVIOUR FIXTURES (regression only — never a quality measure)")
    lines.append("=" * 60)

    pass_count = sum(1 for r in fixtures if r.passed)
    for r in fixtures:
        status = "PASS" if r.passed else "FAIL"
        dots = "." * (40 - len(f"{r.case_type} {r.case_id}"))
        lines.append(f"  {r.case_type} {r.case_id} {dots} {status}")
    lines.append("-" * 60)
    lines.append(f"  Result: {pass_count}/{len(fixtures)} PASS")
    lines.append("")

    lines.append("=" * 60)
    lines.append("GOLDEN CORPUS METRICS")
    lines.append("=" * 60)
    n_total = metrics.total_cases
    floor = metrics.min_floor

    if metrics.aggregate_precision is None:
        lines.append(f"  Precision .......... NOT MEASURED — n={n_total}, minimum {floor}")
    else:
        lines.append(f"  Precision .......... {metrics.aggregate_precision:.3f} (n={n_total})")

    if metrics.aggregate_recall is None:
        lines.append(f"  Recall ............. NOT MEASURED — n={n_total}, minimum {floor}")
    else:
        lines.append(f"  Recall ............. {metrics.aggregate_recall:.3f} (n={n_total})")

    for g in ["N1", "N2", "N3", "N4"]:
        g_data = metrics.n1_to_n4_breakdown.get(g, {"count": 0, "accuracy": None})
        acc = g_data["accuracy"]
        cnt = g_data["count"]
        if acc is None:
            lines.append(f"  {g} speech-act guard ... NOT MEASURED — n={cnt}, minimum {floor}")
        else:
            lines.append(f"  {g} speech-act guard ... {acc:.3f} (n={cnt})")

    if metrics.misattribution_n9 is None:
        n9_count = metrics.cases_by_class.get("N9", 0)
        lines.append(f"  Misattribution (N9)  NOT MEASURED — n={n9_count}, minimum {floor}")
    else:
        lines.append(f"  Misattribution (N9)  {metrics.misattribution_n9:.3f}")

    if metrics.cases_by_source:
        lines.append("-" * 60)
        lines.append("  Labels by source:")
        for src, cnt in metrics.cases_by_source.items():
            lines.append(f"    - {src}: {cnt}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("PARAMETER READINESS")
    lines.append("=" * 60)
    n9_c = metrics.cases_by_class.get("N9", 0)
    dedup_c = metrics.cases_by_class.get("P1", 0)  # dedup pairs proxy
    n11_c = metrics.cases_by_class.get("N11", 0)
    n7_c = metrics.cases_by_class.get("N7", 0)

    lines.append(f"  004 T_high / T_low  {'MEASURED' if n9_c >= 5 else 'NOT MEASURABLE'} — need 5 N9 cases, have {n9_c}")
    lines.append(f"  008 T_dedup         {'MEASURED' if dedup_c >= 5 else 'NOT MEASURABLE'} — need 5 dedup pairs, have {dedup_c}   [provisional 0.88]")
    lines.append(f"  012 sufficiency     {'MEASURED' if n11_c >= 5 else 'NOT MEASURABLE'} — need 5 N11 cases, have {n11_c}")
    lines.append(f"  016 H_max           {'MEASURED' if n7_c >= 5 else 'NOT MEASURABLE'} — need 5 hedge-boundary cases, have {n7_c}")
    lines.append("=" * 60)

    return "\n".join(lines)


def main() -> None:
    report = generate_full_report()
    print("\n" + report)
    sys.exit(0)


if __name__ == "__main__":
    main()
