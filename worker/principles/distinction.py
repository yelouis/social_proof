"""Stated distinction detection module — the fairness escape hatch.

Implements design_principle_extraction.md §4 and agent_execution_guide.md §20.
Built BEFORE the conflict detector: applying a principle differently is principled reasoning,
not hypocrisy, if the speaker explains why.
"""

import re
from typing import NamedTuple


class StatedDistinctionResult(NamedTuple):
    present: bool
    distinction_text: str | None
    quote_span: tuple[int, int] | None = None


class StatedDistinctionDetector:
    """Detects stated distinctions between different actors under the same principle."""

    CONTRASTIVE_PATTERNS = [
        re.compile(r"the difference between\s+(?P<actor1>[^,\.]+?)\s+and\s+(?P<actor2>[^,\.]+?)\s+is\s+(?P<reason>[^;\.]+)", re.IGNORECASE),
        re.compile(r"unlike\s+(?P<actor1>[^,\.]+?),\s*(?P<actor2>[^,\.]+?)\s+(?P<reason>[^;\.]+)", re.IGNORECASE),
        re.compile(r"whereas\s+(?P<actor1>[^,\.]+?)\s+(?P<clause1>[^,]+?),\s*(?P<actor2>[^,\.]+?)\s+(?P<clause2>[^;\.]+)", re.IGNORECASE),
        re.compile(r"distinction between\s+(?P<actor1>[^,\.]+?)\s+and\s+(?P<actor2>[^,\.]+?)\s+is\s+(?P<reason>[^;\.]+)", re.IGNORECASE),
    ]

    def detect_stated_distinction(
        self,
        text: str,
        actor_a: str | None = None,
        actor_b: str | None = None,
        explicit_distinction: str | None = None,
    ) -> StatedDistinctionResult:
        """Detects whether a statement articulates a distinction between two cases."""
        if explicit_distinction and explicit_distinction.strip():
            return StatedDistinctionResult(
                present=True,
                distinction_text=explicit_distinction.strip(),
                quote_span=(0, len(text)),
            )

        clean_text = " ".join(text.split())
        for pat in self.CONTRASTIVE_PATTERNS:
            match = pat.search(clean_text)
            if match:
                reason = match.group(0).strip()
                return StatedDistinctionResult(
                    present=True,
                    distinction_text=reason,
                    quote_span=(match.start(), match.end()),
                )

        return StatedDistinctionResult(present=False, distinction_text=None)
