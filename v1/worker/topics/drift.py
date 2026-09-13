"""Topic drift and era boundary guard.

Implements design_topic_model.md §4 and agent_execution_guide.md §19.
Flags wide-gap reversal pairs spanning eras and routes them to Update Integrity before Consistency.
"""

from datetime import datetime


class TopicDriftGuard:
    """Detects and flags topic drift across long time spans (eras)."""

    def __init__(self, max_gap_years: float = 3.0) -> None:
        self.max_gap_years = max_gap_years

    def check_date_gap(self, date_a_str: str, date_b_str: str) -> tuple[bool, float]:
        """Calculates the time span between two recorded dates in years.

        Returns (is_wide_gap, years_apart).
        """
        try:
            # Handle ISO formats with or without 'Z'
            clean_a = date_a_str.replace("Z", "+00:00")
            clean_b = date_b_str.replace("Z", "+00:00")
            dt_a = datetime.fromisoformat(clean_a)
            dt_b = datetime.fromisoformat(clean_b)
            seconds = abs((dt_b - dt_a).total_seconds())
            years = seconds / (365.25 * 86400.0)
            is_wide_gap = years > self.max_gap_years
            return is_wide_gap, round(years, 2)
        except Exception:
            return False, 0.0

    def should_route_to_update_integrity(self, date_a_str: str, date_b_str: str) -> bool:
        """Determines if a reversal pair should be surfaced as potential era drift."""
        is_wide, _ = self.check_date_gap(date_a_str, date_b_str)
        return is_wide
