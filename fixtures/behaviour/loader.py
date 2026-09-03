"""Behaviour fixtures schema and loader.

Behaviour fixtures are regression tests with synthetic locators and binary PASS/FAIL expectations.
They must NEVER contribute to metrics or quality rates.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

PAIR_TYPE_CLASSES: frozenset[str] = frozenset({
    "P1", "P2", "P3", "P4",
    "N5", "N6", "N7", "N8", "N9", "N11", "N12",
})

ALL_BEHAVIOUR_CLASSES: frozenset[str] = frozenset({
    "P1", "P2", "P3", "P4",
    "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13",
})


@dataclass
class BehaviourUtterance:
    text: str
    recorded_at: str  # ISO 8601 string
    span: tuple[int, int]
    speaker: str | None = None
    venue_type: str | None = None
    audience_stance: str | None = None
    hedging_level: float | None = None
    condition: str | None = None
    stated_distinction: str | None = None
    published_at: str | None = None
    change_marker: bool = False
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BehaviourCase:
    case_id: str
    type: Literal[
        "P1", "P2", "P3", "P4",
        "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13",
    ]
    subject_id: str
    source_locator: str
    utterances: list[BehaviourUtterance]
    expected_behaviour: str
    expected_exclusion_reason: str | None = None
    expected_stance: str | None = None
    expected_is_own_assertion: bool = True
    locator_kind: Literal["synthetic"] = "synthetic"
    extra: dict[str, Any] | None = None

    @property
    def text_snippet(self) -> str:
        """Backward-compatibility helper returning the first utterance text."""
        return self.utterances[0].text if self.utterances else ""

    @property
    def span(self) -> tuple[int, int]:
        """Backward-compatibility helper returning the first utterance span."""
        return self.utterances[0].span if self.utterances else (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_behaviour_cases(fixture_file: Path | str = "fixtures/behaviour/cases.json") -> list[BehaviourCase]:
    """Loads regression behaviour fixtures.

    Rejects:
    - Any case that is not synthetic (locator_kind != 'synthetic')
    - Any case whose utterances lack recorded_at or have invalid ISO 8601 recorded_at
    - Any pair-type case carrying fewer than two utterances
    - Any thin-corpus N11 case carrying fewer than six utterances
    - Any case carrying zero utterances
    """
    path = Path(fixture_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cases: list[BehaviourCase] = []

    for item in data:
        case_id = item.get("case_id", "<unknown>")
        kind = item.get("locator_kind", "synthetic")
        if kind != "synthetic":
            raise ValueError(
                f"BehaviourCase loader rejects non-synthetic locator_kind: '{kind}' in case {case_id}"
            )

        case_type = item.get("type")
        raw_utterances = item.get("utterances")
        if not raw_utterances or not isinstance(raw_utterances, list):
            raise ValueError(
                f"Case '{case_id}' of type '{case_type}' missing required 'utterances' list"
            )

        parsed_utterances: list[BehaviourUtterance] = []
        for idx, u_data in enumerate(raw_utterances):
            rec_at = u_data.get("recorded_at")
            if not rec_at or not isinstance(rec_at, str):
                raise ValueError(
                    f"Utterance index {idx} in case '{case_id}' lacks required 'recorded_at'"
                )
            try:
                datetime.fromisoformat(rec_at.replace("Z", "+00:00"))
            except Exception as e:
                raise ValueError(
                    f"Invalid recorded_at ISO 8601 string '{rec_at}' in case '{case_id}': {e}"
                ) from e

            span_raw = u_data.get("span", [0, len(u_data.get("text", ""))])
            span_tuple = (span_raw[0], span_raw[1])
            u_copy = dict(u_data)
            u_copy["span"] = span_tuple
            parsed_utterances.append(BehaviourUtterance(**u_copy))

        # Check pair-type and multi-utterance requirements
        if case_type in PAIR_TYPE_CLASSES and len(parsed_utterances) < 2:
            raise ValueError(
                f"Pair-type case '{case_id}' of type '{case_type}' requires at least 2 utterances, got {len(parsed_utterances)}"
            )
        if case_type == "N11" and len(parsed_utterances) < 6:
            raise ValueError(
                f"Thin-corpus case '{case_id}' of type 'N11' requires at least 6 utterances, got {len(parsed_utterances)}"
            )

        item_copy = dict(item)
        item_copy["utterances"] = parsed_utterances
        # Remove deprecated single-utterance top-level fields if present
        item_copy.pop("text_snippet", None)
        item_copy.pop("span", None)

        cases.append(BehaviourCase(**item_copy))

    return cases
