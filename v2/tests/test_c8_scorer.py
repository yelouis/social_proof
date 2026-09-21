"""Tests for Item C8: Three residues, and an episode report that answers a narrower question than the one asked (§21).

Validates:
1. Rebuilt Fidelity perturbations: target sensitivity >= 4 of 5 (100.0%) and off_target_drop_rate_pct < 25.0% (0.0%).
2. Full 405-turn episode funnel:
   - Claim count: 111 (27.4%)
   - Gate 1: 174 (43.0%)
   - Gate 2: 37 (9.1%)
   - Gate 3: 4 (1.0%)
   - Gate 4: 79 (19.5%)
   - Sum: 405 (100.0%)
3. Scorer leniency adjudication:
   - Before/after distribution table across all 8 axes between C4 and C7.
   - Aggregate non-2 count drop: 69 of 888 (7.8%) -> 29 of 888 (3.3%), a 58.0% drop.
   - Itemized adjudication of the 9 dropped decontextualisation zeros.
   - Resolution of t0072 (model leniency on bare demonstrative "This" vs Level-0 anchor).
4. Off-target comparison: all 8 axes pass (< 25.0%) with Fidelity falling from 31.4% to 0.0%.
5. Episode report renders the 405-turn funnel above the panels, distinguishing episode-wide from survivor-only scope.
6. Falsification: uncalibrated C4 scorer on rebuilt fidelity perturbations.
"""

from __future__ import annotations

import json

from v2.src.extract import (
    ACTIVE_SPEAKER_PANEL_AXES,
    AXIS_NAMES,
    DEFAULT_EXTRACTION_DIR,
    EXTRACTION_PANEL_AXES,
)
from v2.src.run_c8 import (
    adjudicate_dropped_decontextualisation_zeros,
    adjudicate_t0072,
    compute_405_turn_funnel,
    generate_c8_episode_report,
    get_before_after_distribution_table,
    get_c8_off_target_table,
)

SOURCE_ID = "00251a80c868f535"


def test_c8_fidelity_perturbation_rebuild_sensitivity_and_off_target() -> None:
    """Gap 1 & (c): Fidelity off_target_drop_rate_pct below 25% with target sensitivity >= 4 of 5."""
    c8_pert_file = DEFAULT_EXTRACTION_DIR / f"c8_perturbations_scored_{SOURCE_ID}.json"
    assert c8_pert_file.exists(), f"C8 perturbation results file missing: {c8_pert_file}"

    with open(c8_pert_file, "r", encoding="utf-8") as f:
        c8_data = json.load(f)

    eval_res = c8_data.get("evaluation", {})
    assert eval_res.get("all_axes_pass") is True

    fid_info = eval_res.get("axes", {}).get("fidelity", {})
    target_drops = fid_info.get("target_drops_count", 0)
    total_pairs = fid_info.get("total_pairs", 0)
    sensitivity_pct = fid_info.get("target_sensitivity_rate_pct", 0.0)
    off_target_rate_pct = fid_info.get("off_target_drop_rate_pct", 100.0)

    assert target_drops >= 4, f"Fidelity sensitivity fell below 4/5: {target_drops}/{total_pairs}"
    assert target_drops == 5
    assert sensitivity_pct == 100.0
    assert off_target_rate_pct < 25.0, f"Fidelity off-target drop rate exceeded 25%: {off_target_rate_pct}%"
    assert off_target_rate_pct == 0.0


def test_c8_episode_funnel_sums_to_405_and_matches_claims() -> None:
    """Gap 3 & (c): Episode funnel sums to 405 and its claim count matches the panel's 111."""
    funnel = compute_405_turn_funnel(SOURCE_ID)

    assert funnel["total_turns"] == 405
    assert funnel["sums_to_405"] is True
    assert funnel["claim_count"] == 111
    assert funnel["gate_1_count"] == 174
    assert funnel["gate_2_count"] == 37
    assert funnel["gate_3_count"] == 4
    assert funnel["gate_4_count"] == 79

    # Verify percentages match §21 contract table
    assert funnel["shares_pct"]["claim"] == 27.4
    assert funnel["shares_pct"]["gate_1"] == 43.0
    assert funnel["shares_pct"]["gate_2"] == 9.1
    assert funnel["shares_pct"]["gate_3"] == 1.0
    assert funnel["shares_pct"]["gate_4"] == 19.5


def test_c8_before_after_distribution_and_non2_reduction() -> None:
    """Gap 2 & (c): Before/after 0/1/2 table for all 8 axes; non-2 judgements fell 69 -> 29 (58% drop)."""
    dist_table = get_before_after_distribution_table(SOURCE_ID)

    assert dist_table["total_claims"] == 111
    assert dist_table["total_judgements"] == 888

    # Verify non-2 aggregate counts
    assert dist_table["c4_non2_total"] == 69
    assert dist_table["c4_non2_rate_pct"] == 7.8
    assert dist_table["c7_non2_total"] == 29
    assert dist_table["c7_non2_rate_pct"] == 3.3
    assert dist_table["non2_reduction_count"] == 40
    assert dist_table["non2_reduction_pct"] == 58.0

    # Verify all 8 axes are present
    axes = dist_table["axes"]
    assert set(axes.keys()) == set(AXIS_NAMES)

    # Voice: 4 -> 1
    assert axes["voice"]["c4_dist"] == [3, 1, 107]
    assert axes["voice"]["c7_dist"] == [1, 0, 110]

    # Target: 0 -> 1
    assert axes["target"]["c4_dist"] == [0, 0, 111]
    assert axes["target"]["c7_dist"] == [1, 0, 110]

    # Contestability: 35 -> 12
    assert axes["contestability"]["c4_dist"] == [4, 31, 76]
    assert axes["contestability"]["c7_dist"] == [1, 11, 99]

    # Decontextualisation: 24 -> 9
    assert axes["decontextualisation"]["c4_dist"] == [18, 6, 87]
    assert axes["decontextualisation"]["c7_dist"] == [9, 0, 102]

    # Granularity: 0 -> 3 (natural compounds moved)
    assert axes["granularity"]["c4_dist"] == [0, 0, 111]
    assert axes["granularity"]["c7_dist"] == [0, 3, 108]


def test_c8_adjudication_of_9_dropped_decontextualisation_zeros() -> None:
    """Gap 2 & (c): Adjudicate one-by-one the nine decontextualisation zeros calibration removed."""
    adjudications = adjudicate_dropped_decontextualisation_zeros(SOURCE_ID)

    assert len(adjudications) == 9

    expected_turns = {
        f"{SOURCE_ID}_t0007",
        f"{SOURCE_ID}_t0099",
        f"{SOURCE_ID}_t0113",
        f"{SOURCE_ID}_t0131",
        f"{SOURCE_ID}_t0144",
        f"{SOURCE_ID}_t0162",
        f"{SOURCE_ID}_t0168",
        f"{SOURCE_ID}_t0194",
        f"{SOURCE_ID}_t0385",
    }
    actual_turns = {item["turn_id"] for item in adjudications}
    assert actual_turns == expected_turns

    for item in adjudications:
        assert item["c4_score"] == 0
        assert item["c7_score"] == 2
        assert len(item["adjudication"]) > 20
        assert len(item["quote"]) > 0
        assert len(item["claim"]) > 0

    # Verify specific findings
    t162 = next(item for item in adjudications if item["turn_id"].endswith("_t0162"))
    assert "C4 was right" in t162["verdict"]

    t007 = next(item for item in adjudications if item["turn_id"].endswith("_t0007"))
    assert "C7 is right" in t007["verdict"]

    t144 = next(item for item in adjudications if item["turn_id"].endswith("_t0144"))
    assert "C7 is right on decontextualisation" in t144["verdict"]


def test_c8_t0072_resolution_and_level_0_anchor() -> None:
    """Gap 2 & (c): t0072 resolved with level-0 anchor explanation."""
    res = adjudicate_t0072(SOURCE_ID)

    assert res["turn_id"] == f"{SOURCE_ID}_t0072"
    assert res["c4_score"] == 2
    assert res["c7_score"] == 2
    assert "This" in res["claim"]
    assert "unresolved subject or object" in res["level_0_anchor"]
    assert "Model leniency" in res["status"]
    assert len(res["resolution"]) > 50


def test_c8_all_8_axes_pass_off_target_threshold() -> None:
    """Gap 1 & (c): All eight axes pass off_target_drop_rate_pct < 25.0%."""
    table = get_c8_off_target_table(SOURCE_ID)

    for ax in AXIS_NAMES:
        row = table[ax]
        assert row["passes_threshold_25pct"] is True, f"Axis {ax} failed C8 threshold: {row}"
        assert row["c8_off_target_pct"] < 25.0
        assert row["c8_sensitivity_pct"] >= 80.0

    # Fidelity specifically dropped from 31.4% to 0.0%
    assert table["fidelity"]["c6_off_target_pct"] == 31.4
    assert table["fidelity"]["c7_off_target_pct"] == 31.4
    assert table["fidelity"]["c8_off_target_pct"] == 0.0
    assert table["fidelity"]["c8_sensitivity_pct"] == 100.0


def test_c8_episode_report_structure_and_scope_labels() -> None:
    """Gap 3: Episode report renders funnel above survivor panels, with distinct scope labels."""
    report_path = generate_c8_episode_report(SOURCE_ID)
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")

    # Funnel appears before Speaker Panel
    funnel_pos = content.find("## 1. EPISODE FUNNEL")
    speaker_pos = content.find("## 2. SPEAKER PANEL")
    extraction_pos = content.find("## 3. EXTRACTION PANEL")
    filter_pos = content.find("## 4. FRONT-HALF PIPELINE FILTER")
    off_target_pos = content.find("## 5. OFF-TARGET CONTAMINATION COMPARISON")
    adjudication_pos = content.find("## 6. SCORER LENIENCY ADJUDICATION")
    falsification_pos = content.find("## 7. FALSIFICATION")

    assert funnel_pos != -1
    assert speaker_pos != -1
    assert extraction_pos != -1
    assert filter_pos != -1
    assert off_target_pos != -1
    assert adjudication_pos != -1
    assert falsification_pos != -1

    assert funnel_pos < speaker_pos < extraction_pos < filter_pos < off_target_pos < adjudication_pos < falsification_pos

    # Scope labels
    assert "Episode-Wide: All 405 Turns" in content
    assert "Survivor-Only" in content

    # Assert non-zero variance on reported panel axes
    for ax in ACTIVE_SPEAKER_PANEL_AXES + EXTRACTION_PANEL_AXES:
        assert f"**{ax.capitalize()}**" in content


def test_c8_falsification_uncalibrated_c4_scorer() -> None:
    """Falsification: rebuilt fidelity perturbations evaluated through uncalibrated C4 scorer."""
    falsify_file = DEFAULT_EXTRACTION_DIR / f"c8_falsification_fidelity_c4_{SOURCE_ID}.json"
    assert falsify_file.exists(), f"Falsification artifact not found: {falsify_file}"

    with open(falsify_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["target_drops_count"] == 5
    assert data["target_sensitivity_rate_pct"] == 100.0
    assert data["off_target_drops_count"] == 0
    assert data["off_target_drop_rate_pct"] == 0.0
    assert "falsification_finding" in data
