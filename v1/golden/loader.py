"""Golden corpus schema and loader.

Implements e2e_verification_journeys.md §2 and agent_execution_guide.md §16 (V6).
Golden corpus cases are strictly real, verified citations from ingested sources.
Synthetic fixtures are prohibited in the golden corpus.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass
class GoldenCase:
    case_id: str
    class_name: str  # P1-P4, N1-N13
    subject_id: str
    source_id: str
    utterance_id: str
    span: tuple[int, int]
    expected_behaviour: str
    verified_by: str
    verified_at: str
    expected_exclusion_reason: str | None = None
    expected_stance: str | None = None
    expected_is_own_assertion: bool = True
    locator_kind: Literal["real"] = "real"
    label_source: Literal["human", "model_assisted", "model_only"] = "human"
    labeller_model: str | None = None
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_golden_cases(
    golden_file: Path | str = "golden/cases.json",
    current_extractor_model: str | None = None,
) -> list[GoldenCase]:
    """Loads all human-verified golden corpus cases.

    Enforces schema rules:
    1. locator_kind must be 'real' (never 'synthetic').
    2. Circularity guard: labeller_model may never equal current_extractor_model.
    """
    path = Path(golden_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cases: list[GoldenCase] = []
    for item in data:
        kind = item.get("locator_kind", "real")
        if kind == "synthetic":
            raise ValueError(
                f"GoldenCase loader rejects synthetic locator_kind in case {item.get('case_id')}. "
                f"Synthetic fixtures belong in fixtures/behaviour/."
            )

        labeller = item.get("labeller_model")
        if current_extractor_model and labeller and labeller == current_extractor_model:
            raise ValueError(
                f"Circularity guard violation in case {item.get('case_id')}: "
                f"labeller_model '{labeller}' matches current extractor under test '{current_extractor_model}'."
            )

        span_raw = item.get("span", [0, 0])
        span_tuple = (span_raw[0], span_raw[1])
        item_copy = dict(item)
        item_copy["span"] = span_tuple
        cases.append(GoldenCase(**item_copy))
    return cases
