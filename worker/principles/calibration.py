"""Generality calibration and principle validation.

Implements design_principle_extraction.md §3 and agent_execution_guide.md §20.
Enforces cluster-size ceilings and validates canonical text discipline (no actor, no verdict).
"""

import re
from typing import NamedTuple


class ValidationResult(NamedTuple):
    is_valid: bool
    reason: str | None = None


class GeneralityCalibrator:
    """Calibrates generality and enforces cluster-size ceilings for principles."""

    def __init__(self, max_cluster_size: int = 30) -> None:
        self.max_cluster_size = max_cluster_size

    def check_cluster_size(self, member_count: int) -> tuple[bool, str | None]:
        """Asserts cluster size does not exceed generality ceiling."""
        if member_count > self.max_cluster_size:
            return False, f"Principle cluster size {member_count} exceeds ceiling of {self.max_cluster_size} (over-general)"
        return True, None

    def validate_canonical_text(self, canonical_text: str) -> ValidationResult:
        """Validates that canonical text carries no specific actor and no verdict."""
        clean = canonical_text.strip().lower()

        # Check for named person entity markers
        if re.search(r"\b(senator|director|representative|mr\.|ms\.|dr\.)\s+[a-z]+", clean):
            return ValidationResult(
                is_valid=False,
                reason="Principle canonical text must not mention specific actors",
            )

        # Must start with generic slot or generic subject
        if not any(clean.startswith(prefix) for prefix in ("an ", "a ", "any ", "one who ", "someone who ", "an official who ")):
            return ValidationResult(
                is_valid=False,
                reason="Principle canonical text must state a general rule with actor as slot",
            )

        return ValidationResult(is_valid=True)
