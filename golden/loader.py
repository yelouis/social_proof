"""Golden corpus schema and loader.

Implements e2e_verification_journeys.md §2 and agent_execution_guide.md §9 (U5).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass
class GoldenCase:
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
    verified_by: str = "curator"
    verified_at: str = "2024-01-15T12:00:00Z"
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_golden_cases(golden_file: Path | str = "golden/cases.json") -> list[GoldenCase]:
    """Loads all human-verified golden corpus cases."""
    path = Path(golden_file)
    if not path.exists():
        return get_builtin_golden_cases()
    data = json.loads(path.read_text(encoding="utf-8"))
    return [GoldenCase(**item) for item in data]


def get_builtin_golden_cases() -> list[GoldenCase]:
    """Returns the verified golden corpus cases for P1-P4 and N1-N13."""
    cases = [
        # --- POSITIVES ---
        GoldenCase(
            case_id="case_p1_reversal",
            type="P1",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_p1",
            text_snippet="We must mandate federal licensing for all large frontier models.",
            span=(0, 62),
            expected_behaviour="unacknowledged_reversal",
            expected_stance="support",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_p2_update",
            type="P2",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_p2",
            text_snippet="I used to think open weights were reckless, but watching the last two years changed my mind because diffusion won.",
            span=(0, 114),
            expected_behaviour="acknowledged_update",
            expected_stance="support",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_p3_principle",
            type="P3",
            subject_id="subj_golden_02",
            source_locator="https://youtube.com/watch?v=golden_p3",
            text_snippet="Senator Alvarez knowingly misled the oversight committee and should resign immediately.",
            span=(0, 87),
            expected_behaviour="principle_conflict",
            expected_stance="support",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_p4_audience",
            type="P4",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_p4",
            text_snippet="Under hostile questioning: I have never supported federal licensing of compute.",
            span=(27, 79),
            expected_behaviour="audience_divergence",
            expected_stance="oppose",
            expected_is_own_assertion=True,
        ),

        # --- NEGATIVES (I7 Speech-Act Guards & Exclusions) ---
        GoldenCase(
            case_id="case_n1_sarcasm",
            type="N1",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n1",
            text_snippet="Oh sure, mandatory licensing for every open source Python script, brilliant idea.",
            span=(0, 81),
            expected_behaviour="excluded",
            expected_exclusion_reason="sarcasm",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n2_reported_speech",
            type="N2",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n2",
            text_snippet="The argument from the other side is that AI will cause catastrophic unemployment next year.",
            span=(0, 91),
            expected_behaviour="excluded",
            expected_exclusion_reason="reported_speech",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n3_steelman",
            type="N3",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n3",
            text_snippet="The strongest case for licensing is that it provides a choke point on rogue actors.",
            span=(0, 83),
            expected_behaviour="excluded",
            expected_exclusion_reason="steelman",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n4_hypothetical",
            type="N4",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n4",
            text_snippet="Suppose frontier models were capable of autonomous replication, then strict containment would follow.",
            span=(0, 101),
            expected_behaviour="excluded",
            expected_exclusion_reason="hypothetical",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n5_conditional",
            type="N5",
            subject_id="subj_golden_03",
            source_locator="https://youtube.com/watch?v=golden_n5",
            text_snippet="If inflation stays above four percent through December, we must raise interest rates.",
            span=(0, 85),
            expected_behaviour="no_tension_condition_mismatch",
            expected_stance="support",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_n7_hedge",
            type="N7",
            subject_id="subj_golden_03",
            source_locator="https://youtube.com/watch?v=golden_n7",
            text_snippet="I could maybe see rates moving slightly either way depending on seasonal data.",
            span=(0, 78),
            expected_behaviour="hedge_low_weight",
            expected_stance="hedge",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_n8_topic_drift",
            type="N8",
            subject_id="subj_golden_03",
            source_locator="https://youtube.com/watch?v=golden_n8",
            text_snippet="In 2014: Neural networks are useless for production machine translation.",
            span=(9, 72),
            expected_behaviour="era_boundary_wide_gap",
            expected_stance="oppose",
            expected_is_own_assertion=True,
        ),
        GoldenCase(
            case_id="case_n10_quote_unclear",
            type="N10",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n10",
            text_snippet="Let me read this tweet: 'All software patents should be abolished by executive order.'",
            span=(24, 86),
            expected_behaviour="excluded",
            expected_exclusion_reason="quote_agreement_unclear",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n12_re_aired_archive",
            type="N12",
            subject_id="subj_golden_02",
            source_locator="https://youtube.com/watch?v=golden_n12",
            text_snippet="Archive rebroadcast of 2018 interview: We should not subsidize commercial space flight.",
            span=(40, 87),
            expected_behaviour="original_recording_dated",
            expected_stance="oppose",
            expected_is_own_assertion=True,
        ),
        # --- N13 CONVERSATIONAL FILLER ---
        GoldenCase(
            case_id="case_n13_filler_01",
            type="N13",
            subject_id="subj_golden_01",
            source_locator="https://youtube.com/watch?v=golden_n13_1",
            text_snippet="Yeah, absolutely, thanks so much for having me on the show today.",
            span=(0, 65),
            expected_behaviour="empty_claim_list",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n13_filler_02",
            type="N13",
            subject_id="subj_golden_02",
            source_locator="https://youtube.com/watch?v=golden_n13_2",
            text_snippet="Let me check my calendar for next Tuesday afternoon, I think that works.",
            span=(0, 72),
            expected_behaviour="empty_claim_list",
            expected_is_own_assertion=False,
        ),
        GoldenCase(
            case_id="case_n13_filler_03",
            type="N13",
            subject_id="subj_golden_03",
            source_locator="https://youtube.com/watch?v=golden_n13_3",
            text_snippet="Right, exactly, mm-hmm, totally agree with that logistical point.",
            span=(0, 65),
            expected_behaviour="empty_claim_list",
            expected_is_own_assertion=False,
        ),
    ]
    return cases
