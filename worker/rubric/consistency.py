"""Consistency axis calculator.

Implements design_rubric_engine.md §2.
Hedging-weighted unacknowledged reversal penalties over eligible propositions.
"""

from typing import Any

from worker.entities import Claim, Tension


class ConsistencyCalculator:
    """Calculates Consistency over propositions with >= 2 own-assertion claims across time."""

    def __init__(self, min_eligible_propositions: int = 2) -> None:
        self.min_eligible_propositions = min_eligible_propositions

    def calculate(
        self,
        claims: list[Claim],
        tensions: list[Tension],
    ) -> dict[str, Any]:
        """Calculates consistency score or returns sufficiency gate failure.

        Strictly avoids computing any score when below sufficiency gate.
        """
        # 1. Identify eligible propositions: own-assertion claims at >= 2 different timestamps
        claims_by_prop: dict[str, list[Claim]] = {}
        for c in claims:
            if c.is_own_assertion:
                claims_by_prop.setdefault(c.proposition_id, []).append(c)

        eligible_props: set[str] = set()
        for pid, prop_claims in claims_by_prop.items():
            distinct_times = {c.recorded_at for c in prop_claims if c.recorded_at}
            if len(distinct_times) >= 2 or len(prop_claims) >= 2:
                eligible_props.add(pid)

        eligible_count = len(eligible_props)

        # 2. Sufficiency gate
        if eligible_count < self.min_eligible_propositions:
            return {
                "score": None,
                "reason": "insufficient_repeat_coverage",
                "n": eligible_count,
                "evidence": [],
            }

        # 3. Sum penalties over unacknowledged reversal pairs on eligible propositions
        claims_by_id = {c.claim_id: c for c in claims}
        penalty = 0.0
        evidence_tensions: list[str] = []

        for t in tensions:
            if t.type == "unacknowledged_reversal" and t.status == "published":
                if t.proposition_id in eligible_props:
                    c_a = claims_by_id.get(t.claim_a_id)
                    c_b = claims_by_id.get(t.claim_b_id)
                    hedging_a = c_a.hedging_level if c_a else 0.0
                    hedging_b = c_b.hedging_level if c_b else 0.0
                    weight = (1.0 - hedging_a) * (1.0 - hedging_b)
                    penalty += weight
                    evidence_tensions.append(t.tension_id)

        # 4. Consistency = 1.0 - penalty / eligible_count (clamped to [0.0, 1.0])
        raw_score = 1.0 - (penalty / float(eligible_count))
        clamped_score = max(0.0, min(1.0, round(raw_score, 4)))

        return {
            "score": clamped_score,
            "n": eligible_count,
            "evidence": evidence_tensions,
        }
