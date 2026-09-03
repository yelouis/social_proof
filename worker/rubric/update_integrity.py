"""Update Integrity axis calculator.

Implements design_rubric_engine.md §3.
Evaluates proportion of stance updates acknowledged with or without stated reason.
Zero changes yields null, never 1.0.
"""

from typing import Any

from worker.entities import Tension


class UpdateIntegrityCalculator:
    """Calculates Update Integrity over all detected stance changes in the slice."""

    def __init__(self, min_changes: int = 2) -> None:
        self.min_changes = min_changes

    def calculate(self, tensions: list[Tension]) -> dict[str, Any]:
        """Calculates update integrity score or returns sufficiency gate failure."""
        changes = [
            t for t in tensions
            if t.type in ("acknowledged_update", "unacknowledged_reversal")
            and t.status == "published"
        ]
        total_changes = len(changes)

        # Invariant: Zero changes yields null, never 1.0
        if total_changes == 0:
            return {
                "score": None,
                "reason": "no_updates_detected",
                "n": 0,
                "evidence": [],
            }

        # Sufficiency gate: minimum change count
        if total_changes < self.min_changes:
            return {
                "score": None,
                "reason": "insufficient_update_history",
                "n": total_changes,
                "evidence": [t.tension_id for t in changes],
            }

        acked_with_reason = 0
        acked_without_reason = 0
        evidence_tensions: list[str] = []

        for t in changes:
            evidence_tensions.append(t.tension_id)
            if t.type == "acknowledged_update":
                # Check quarantine/status reason or default to with_reason
                if t.quarantine_reason and "without_reason" in t.quarantine_reason:
                    acked_without_reason += 1
                else:
                    acked_with_reason += 1

        weighted_sum = (1.0 * acked_with_reason) + (0.5 * acked_without_reason)
        score = round(weighted_sum / float(total_changes), 4)

        return {
            "score": score,
            "n": total_changes,
            "evidence": evidence_tensions,
        }
