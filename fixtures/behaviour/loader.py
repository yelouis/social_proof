"""Behaviour fixtures schema and loader.

Behaviour fixtures are regression tests with synthetic locators and binary PASS/FAIL expectations.
They must NEVER contribute to metrics or quality rates.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass
class BehaviourCase:
    case_id: str
    type: Literal[
        "P1", "P2", "P3", "P4",
        "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13",
    ]
    subject_id: str
    source_locator: str
    text_snippet: str
    span: tuple[int, int]
    expected_behaviour: str
    expected_exclusion_reason: str | None = None
    expected_stance: str | None = None
    expected_is_own_assertion: bool = True
    locator_kind: Literal["synthetic"] = "synthetic"
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_behaviour_cases(fixture_file: Path | str = "fixtures/behaviour/cases.json") -> list[BehaviourCase]:
    """Loads regression behaviour fixtures. Rejects any case that is not synthetic."""
    path = Path(fixture_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cases: list[BehaviourCase] = []
    for item in data:
        kind = item.get("locator_kind", "synthetic")
        if kind != "synthetic":
            raise ValueError(f"BehaviourCase loader rejects non-synthetic locator_kind: '{kind}' in case {item.get('case_id')}")
        span_raw = item.get("span", [0, 0])
        span_tuple = (span_raw[0], span_raw[1])
        item_copy = dict(item)
        item_copy["span"] = span_tuple
        cases.append(BehaviourCase(**item_copy))
    return cases
