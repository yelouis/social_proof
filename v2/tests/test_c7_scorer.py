"""Tests for Item C7: The fix was demonstrated but never applied, and fidelity regressed (§20).

Validates:
1. Re-scored candidate set c6_scored_axes_00251a80c868f535.json has non-zero variance on Granularity,
   with t0016, t0255, and t0389 scoring 1 (< 2).
2. Every remaining axis in the episode report shows non-zero variance.
3. Unified metric off_target_drop_rate_pct side-by-side table across C5, C6, C7.
4. Fidelity contamination diagnosis: exact contaminated axes and pair breakdown.
5. Speaker panel excludes Target and Propositionality, with Step 4 distribution attached.
6. Falsification: Constant scorer over the 111 candidates refuses to render (raises UniformDistributionError).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from v2.src.extract import (
    ACTIVE_SPEAKER_PANEL_AXES,
    DEFAULT_EXTRACTION_DIR,
    EXTRACTION_PANEL_AXES,
)
from v2.src.run_c7 import (
    diagnose_fidelity_contamination,
    get_side_by_side_off_target_table,
    recut_c7_episode_report,
    run_constant_scorer_falsification,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_ID = "00251a80c868f535"


def test_c7_off_target_metric_single_table_and_gate() -> None:
    """Step 2: Unified metric off_target_drop_rate_pct reported across C5, C6, C7."""
    table = get_side_by_side_off_target_table(SOURCE_ID)

    # 7 of the 8 axes pass (< 25.0%)
    passing_axes = [ax for ax, data in table.items() if data["passes_threshold_25pct"]]
    failing_axes = [ax for ax, data in table.items() if not data["passes_threshold_25pct"]]

    assert len(passing_axes) == 7, f"Expected 7 axes to pass < 25%, got: {passing_axes}"
    assert failing_axes == ["fidelity"], f"Expected only fidelity to fail > 25%, got: {failing_axes}"

    # Verify exact rates on off_target_drop_rate_pct
    assert table["voice"]["c7_off_target_pct"] == 2.9
    assert table["target"]["c7_off_target_pct"] == 0.0
    assert table["propositionality"]["c7_off_target_pct"] == 2.9
    assert table["contestability"]["c7_off_target_pct"] == 0.0
    assert table["typing"]["c7_off_target_pct"] == 2.9
    assert table["decontextualisation"]["c7_off_target_pct"] == 8.6
    assert table["granularity"]["c7_off_target_pct"] == 8.6
    assert table["fidelity"]["c7_off_target_pct"] == 31.4


def test_c7_fidelity_contamination_breakdown() -> None:
    """Step 3: Fidelity contamination diagnosis resolves to specific axes and pairs."""
    diag = diagnose_fidelity_contamination(SOURCE_ID)

    assert diag["total_off_target_drops"] == 11
    assert diag["total_comparisons"] == 35
    assert diag["off_target_drop_rate_pct"] == 31.4

    # Contaminated axes breakdown
    counts = diag["contaminated_axes_counts"]
    assert counts["decontextualisation"] == 4
    assert counts["voice"] == 2
    assert counts["target"] == 1
    assert counts["propositionality"] == 1
    assert counts["contestability"] == 1
    assert counts["typing"] == 1
    assert counts["granularity"] == 1

    # fidelity_01 collapsed all 7 other axes
    p01 = next(p for p in diag["pairs"] if p["id"] == "fidelity_01")
    assert p01["drops_count"] == 7
    assert set(p01["contaminated_axes"]) == {
        "voice", "target", "propositionality", "contestability", "typing", "decontextualisation", "granularity"
    }


def test_c7_falsification_constant_scorer_fails_report_generation() -> None:
    """Falsification: constant scorer over the 111 candidates refuses to render."""
    refused = run_constant_scorer_falsification(SOURCE_ID)
    assert refused is True, "Constant scorer over the 111 candidates failed to raise UniformDistributionError!"


def test_c7_rescore_granularity_non_zero_variance() -> None:
    """Step 1 & (c): Granularity moves off 0/0/111, natural compounds score 1."""
    c6_file = DEFAULT_EXTRACTION_DIR / f"c6_scored_axes_{SOURCE_ID}.json"
    if not c6_file.exists():
        pytest.skip("c6_scored_axes_00251a80c868f535.json not yet generated")

    with open(c6_file, "r", encoding="utf-8") as f:
        c6_data = json.load(f)

    scored_claims = c6_data["scored_claims"]
    assert len(scored_claims) == 111

    # Granularity distribution
    gran_scores = [c["scores"]["granularity"] for c in scored_claims]
    assert gran_scores.count(2) < 111, "Granularity is still pinned at 2 on all 111 claims!"
    assert gran_scores.count(1) > 0, "Granularity has no score 1s!"

    # Natural compound claims t0016, t0255, t0389 score 1 (< 2)
    claims_map = {c["turn_id"]: c for c in scored_claims}
    for tid in ["00251a80c868f535_t0016", "00251a80c868f535_t0255", "00251a80c868f535_t0389"]:
        assert tid in claims_map, f"Turn {tid} not found in re-scored candidates"
        score = claims_map[tid]["scores"]["granularity"]
        assert score == 1, f"Expected {tid} granularity to score 1 (< 2), got {score}"


def test_c7_every_remaining_axis_has_variance() -> None:
    """(c): Every remaining axis in the episode report shows non-zero variance."""
    c6_file = DEFAULT_EXTRACTION_DIR / f"c6_scored_axes_{SOURCE_ID}.json"
    if not c6_file.exists():
        pytest.skip("c6_scored_axes_00251a80c868f535.json not yet generated")

    with open(c6_file, "r", encoding="utf-8") as f:
        c6_data = json.load(f)

    scored_claims = c6_data["scored_claims"]
    reported_axes = ACTIVE_SPEAKER_PANEL_AXES + EXTRACTION_PANEL_AXES

    for ax in reported_axes:
        scores = [c["scores"][ax] for c in scored_claims]
        assert not (scores.count(0) == 111 or scores.count(1) == 111 or scores.count(2) == 111), (
            f"Axis '{ax}' has zero variance across all 111 candidates!"
        )


def test_c7_speaker_panel_excludes_target_and_propositionality() -> None:
    """Step 4: Speaker panel excludes Target & Propositionality, attaching Step 4 distribution."""
    c6_file = DEFAULT_EXTRACTION_DIR / f"c6_scored_axes_{SOURCE_ID}.json"
    if not c6_file.exists():
        pytest.skip("c6_scored_axes_00251a80c868f535.json not yet generated")

    report_path = recut_c7_episode_report(SOURCE_ID, enforce_variance=True)
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")

    # In Speaker panel, only Voice and Contestability appear
    speaker_panel_section = content.split("## SPEAKER PANEL")[1].split("## EXTRACTION PANEL")[0]
    assert "**Voice**" in speaker_panel_section
    assert "**Contestability**" in speaker_panel_section
    assert "**Typing**" not in speaker_panel_section
    assert "**Target**" not in speaker_panel_section
    assert "**Propositionality**" not in speaker_panel_section

    # Target, Propositionality, and Typing are in FRONT-HALF PIPELINE FILTER section
    assert "## FRONT-HALF PIPELINE FILTER" in content
    filter_section = content.split("## FRONT-HALF PIPELINE FILTER")[1].split("## OFF-TARGET CONTAMINATION COMPARISON")[0]
    assert "**Target**: 0: 25 turns (62.5%), 1: 6 turns (15.0%), 2: 9 turns (22.5%)" in filter_section
    assert "**Propositionality**: 0: 7 turns (17.5%), 1: 15 turns (37.5%), 2: 18 turns (45.0%)" in filter_section
    assert "**Typing**: Candidate claims: 0: 0 turns (0.0%), 1: 0 turns (0.0%), 2: 111 turns (100.0%)" in filter_section
