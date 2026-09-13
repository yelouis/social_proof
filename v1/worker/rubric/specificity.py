"""Specificity axis calculator.

Implements design_rubric_engine.md §2A.
Rate of checkable claims: hedging <= H_max AND stance in {support, oppose}
AND (named_entity OR numeric OR temporal_anchor).
"""

import re
from typing import Any

from worker.entities import Claim


class SpecificityCalculator:
    """Calculates Specificity as a deterministic rate of checkable claims."""

    # Pinned regex rules corresponding to nlp_version="v1.0-regex-ner"
    NAMED_ENTITY_PATTERN = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z]{2,}|Nvidia|Apple|Google|Microsoft|OpenAI|Congress|Senate|China|US|America|CCP)\b"
    )
    NUMERIC_PATTERN = re.compile(
        r"(\b\d+(?:\.\d+)?%?|\$\d+|\b(?:hundred|thousand|million|billion|trillion|percent|double|triple)\b)",
        re.IGNORECASE,
    )
    TEMPORAL_PATTERN = re.compile(
        r"(\b20\d\d\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b|\b(?:by\s+\d+|within\s+\d+\s+(?:days|months|years))\b)",
        re.IGNORECASE,
    )

    def __init__(self, h_max: float = 0.25, min_claims: int = 3) -> None:
        self.h_max = h_max
        self.min_claims = min_claims
        self.nlp_version = "v1.0-regex-ner"

    def is_checkable(self, claim: Claim, quote_text: str = "") -> bool:
        """Determines if a claim satisfies the checkability predicate."""
        if claim.hedging_level > self.h_max:
            return False
        if claim.stance not in ("support", "oppose"):
            return False

        text_to_scan = quote_text or claim.quote_text or ""
        has_ne = bool(self.NAMED_ENTITY_PATTERN.search(text_to_scan))
        has_num = bool(self.NUMERIC_PATTERN.search(text_to_scan))
        has_temp = bool(self.TEMPORAL_PATTERN.search(text_to_scan))

        return has_ne or has_num or has_temp

    def calculate(
        self,
        claims: list[Claim],
        quote_texts_by_claim_id: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Calculates specificity rate or returns sufficiency gate failure."""
        quote_map = quote_texts_by_claim_id or {}
        own_claims = [c for c in claims if c.is_own_assertion]
        total_count = len(own_claims)

        # Sufficiency gate
        if total_count < self.min_claims:
            return {
                "score": None,
                "reason": "insufficient_corpus",
                "n": total_count,
                "checkable": 0,
                "evidence": [],
            }

        checkable_claims: list[str] = []
        for c in own_claims:
            quote_text = quote_map.get(c.claim_id, "")
            if self.is_checkable(c, quote_text):
                checkable_claims.append(c.claim_id)

        checkable_count = len(checkable_claims)
        rate = round(float(checkable_count) / float(total_count), 4)

        return {
            "score": rate,
            "n": total_count,
            "checkable": checkable_count,
            "evidence": checkable_claims,
        }
