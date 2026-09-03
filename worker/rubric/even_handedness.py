"""Even-handedness axis calculator.

Implements design_rubric_engine.md §4.
Evaluates directional alignment across principle conflicts with two-sided binomial significance testing.
"""

from typing import Any

from scipy.stats import binomtest  # type: ignore[import-untyped]

from worker.entities import Tension


class EvenHandednessCalculator:
    """Calculates Even-handedness using directional alignment and binomial significance gating."""

    def __init__(self, min_directional: int = 4, alpha: float = 0.05) -> None:
        self.min_directional = min_directional
        self.alpha = alpha

    def calculate(
        self,
        tensions: list[Tension],
        conflict_directions: list[int] | None = None,
    ) -> dict[str, Any]:
        """Calculates even-handedness score or returns null with reason.

        Evidence conflicts are always returned even when the pattern is not significant.
        """
        conflicts = [
            t for t in tensions
            if t.type == "principle_conflict" and t.status == "published"
        ]
        evidence_ids = [t.tension_id for t in conflicts]

        if not conflicts:
            return {
                "score": None,
                "reason": "no_principle_conflicts",
                "n": 0,
                "evidence": [],
            }

        # Directions: +1 for ally-favored/opponent-disfavored, -1 for reverse, 0 for neutral/unknown
        directions = conflict_directions or [1] * len(conflicts)
        non_zero = [d for d in directions if d in (1, -1)]
        n = len(non_zero)

        # Sufficiency gate 1: minimum directional conflicts
        if n < self.min_directional:
            return {
                "score": None,
                "reason": "pattern_not_significant",
                "n": n,
                "evidence": evidence_ids,
            }

        # Significance test: two-sided binomial test at p = 0.5
        k = sum(1 for d in non_zero if d == 1)
        test_res = binomtest(k=k, n=n, p=0.5)

        if test_res.pvalue >= self.alpha:
            return {
                "score": None,
                "reason": "pattern_not_significant",
                "n": n,
                "p_value": round(float(test_res.pvalue), 4),
                "evidence": evidence_ids,
            }

        # Score = 1 - (|sum(d)| / n)
        alignment = abs(sum(non_zero)) / float(n)
        score = round(1.0 - alignment, 4)

        return {
            "score": score,
            "n": n,
            "p_value": round(float(test_res.pvalue), 4),
            "evidence": evidence_ids,
        }
