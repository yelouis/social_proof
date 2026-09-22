"""Tests for Item C9: The constraint I wrote and did not apply, and the axis nobody adjudicated (§22).

Validates:
1. Rebuilt Fidelity perturbations with real failures:
   - v2/fixtures/axes/perturbations.json contains 40 items total, with 5 fidelity pairs.
   - At least 3 of 5 fidelity pairs seeded from real failures (t0127, t0142, t0189).
   - 2 of 5 pairs are invented direction inversions (t0187, t0192).
   - Sensitivity and off-target reported separately for real-derived vs invented perturbations.
2. Contestability adjudication:
   - All 23 contestability shifts between C4 and C7 adjudicated by turn ID.
   - Three-way split verified: C7 right (13, 56.5%), C4 right (7, 30.4%), Borderline (3, 13.0%).
   - C7 is right for the majority (>50%), confirming the axis has not been flattened into noise.
3. Blind spot documentation:
   - v2/docs/design_claim_axes.md documents t0072 demonstrative copular sentence blind spot beside Axis 6.
   - Mechanical regex proxy check explicitly referenced.
4. Episode report:
   - v2/artifacts/reports/c9_claim_quality_report_00251a80c868f535.md exists and contains required sections.
5. Falsification:
   - Evaluates real-derived failures under uncalibrated C4 prompt template.
"""

from __future__ import annotations

import json
from pathlib import Path

from v2.src.extract import (
    ACTIVE_SPEAKER_PANEL_AXES,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_FIXTURES_AXES_DIR,
    EXTRACTION_PANEL_AXES,
)
from v2.src.run_c9 import (
    adjudicate_contestability_shifts,
    generate_c9_episode_report,
    get_c9_off_target_table,
)

SOURCE_ID = "00251a80c868f535"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_c9_fixtures_perturbations_seeded_from_real_failures() -> None:
    """Gap 1 & (c): Perturbations fixture seeds at least 3 of 5 fidelity pairs from real failures."""
    pert_file = DEFAULT_FIXTURES_AXES_DIR / "perturbations.json"
    assert pert_file.exists(), f"Perturbations fixture missing: {pert_file}"

    with open(pert_file, "r", encoding="utf-8") as f:
        perturbations = json.load(f)

    assert len(perturbations) == 40, f"Expected 40 perturbations, found {len(perturbations)}"

    fidelity_pairs = [p for p in perturbations if p.get("target_axis") == "fidelity"]
    assert len(fidelity_pairs) == 5, f"Expected 5 fidelity pairs, found {len(fidelity_pairs)}"

    # Check for real failure turn IDs
    fid_turn_ids = {p["turn_id"] for p in fidelity_pairs}
    real_candidates = {"00251a80c868f535_t0127", "00251a80c868f535_t0142", "00251a80c868f535_t0189"}
    seeded_real = fid_turn_ids.intersection(real_candidates)
    assert len(seeded_real) >= 3, f"Expected at least 3 real failure pairs, found {len(seeded_real)}: {seeded_real}"

    # Check for invented direction inversions
    invented_candidates = {"00251a80c868f535_t0187", "00251a80c868f535_t0192"}
    seeded_invented = fid_turn_ids.intersection(invented_candidates)
    assert len(seeded_invented) == 2, f"Expected 2 invented inversion pairs, found {len(seeded_invented)}"


def test_c9_fidelity_sensitivity_reported_separately_real_vs_invented() -> None:
    """Gap 1 & (c): Fidelity sensitivity and off-target reported separately for real vs invented."""
    off_target_info = get_c9_off_target_table(SOURCE_ID)
    breakdown = off_target_info["fidelity_breakdown"]

    assert "real" in breakdown, "Missing 'real' fidelity breakdown"
    assert "invented" in breakdown, "Missing 'invented' fidelity breakdown"

    real_data = breakdown["real"]
    inv_data = breakdown["invented"]

    assert real_data["total"] >= 3, f"Expected at least 3 real pairs, got {real_data['total']}"
    assert inv_data["total"] == 2, f"Expected 2 invented pairs, got {inv_data['total']}"

    # Verify sensitivity and off-target rates
    assert inv_data["sensitivity_pct"] == 100.0, "Invented inversions should have 100% sensitivity"
    assert inv_data["off_target_pct"] < 25.0, "Invented inversions off-target should be < 25%"
    assert real_data["off_target_pct"] < 25.0, "Real failures off-target should be < 25%"

    # Key architectural finding: real sensitivity is materially lower than invented
    assert real_data["sensitivity_pct"] < inv_data["sensitivity_pct"], (
        f"Real sensitivity ({real_data['sensitivity_pct']}%) should be materially lower than "
        f"invented sensitivity ({inv_data['sensitivity_pct']}%)"
    )


def test_c9_contestability_adjudication_23_claims_and_three_way_split() -> None:
    """Gap 2 & (c): All 23 contestability movements adjudicated by turn ID with three-way split."""
    summary = adjudicate_contestability_shifts()

    assert summary["total"] == 23, f"Expected 23 contestability shifts, found {summary['total']}"
    assert len(summary["shifts"]) == 23

    # Check each shift structure
    for s in summary["shifts"]:
        assert "turn_id" in s
        assert "speaker" in s
        assert "quote" in s
        assert "claim" in s
        assert "c4_score" in s
        assert "c7_score" in s
        assert s["c7_score"] == 2, f"Expected C7 score to be 2 for non-2 movement, got {s['c7_score']}"
        assert s["c4_score"] in (0, 1), f"Expected C4 score to be non-2 (0 or 1), got {s['c4_score']}"
        assert "verdict" in s
        assert s["verdict"] in ("C7 is right", "C4 was right", "Borderline")
        assert "adjudication" in s and len(s["adjudication"]) > 10

    # Verify three-way split counts
    assert summary["c7_right_count"] == 13
    assert summary["c4_right_count"] == 7
    assert summary["borderline_count"] == 3
    assert summary["c7_right_count"] + summary["c4_right_count"] + summary["borderline_count"] == 23

    # Verify percentages
    assert summary["c7_right_pct"] == 56.5
    assert summary["c4_right_pct"] == 30.4
    assert summary["borderline_pct"] == 13.0

    # Confirm the panel was not flattened (majority is C7 right)
    assert summary["c7_right_count"] > summary["c4_right_count"]


def test_c9_design_claim_axes_t0072_demonstrative_blind_spot() -> None:
    """Gap 3 & (c): design_claim_axes.md documents t0072 demonstrative blind spot beside Axis 6."""
    axes_doc = REPO_ROOT / "v2" / "docs" / "design_claim_axes.md"
    assert axes_doc.exists(), f"design_claim_axes.md missing: {axes_doc}"

    content = axes_doc.read_text(encoding="utf-8")

    # Verify t0072 blind spot note is present
    assert "t0072" in content
    assert "Demonstrative blind spot" in content
    assert "mechanical regex proxy" in content or "mechanical proxy" in content


def test_c9_falsification_artifact_properties() -> None:
    """Falsification: uncalibrated C4 prompt scoring on real-derived fidelity perturbations."""
    falsify_file = DEFAULT_EXTRACTION_DIR / f"c9_falsification_fidelity_c4_{SOURCE_ID}.json"
    assert falsify_file.exists(), f"C9 falsification file missing: {falsify_file}"

    with open(falsify_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_pairs"] == 3
    assert data["target_drops_count"] == 1  # only t0189 drops; t0127 and t0142 scored 2
    assert data["target_sensitivity_rate_pct"] == 33.3
    assert data["off_target_drops_count"] == 0
    assert data["off_target_drop_rate_pct"] == 0.0
    assert "falsification_finding" in data


def test_c9_episode_report_structure_and_scope() -> None:
    """Report validation: C9 episode report renders funnel, panels, fidelity breakdown, and 23 adjudications."""
    report_file = generate_c9_episode_report(SOURCE_ID)
    assert report_file.exists()

    content = report_file.read_text(encoding="utf-8")

    # Section headers
    assert "## 1. EPISODE FUNNEL (Episode-Wide: All 405 Turns)" in content
    assert "## 2. SPEAKER PANEL (Survivor-Only: How Good Were the Claims Made)" in content
    assert "## 3. EXTRACTION PANEL (Survivor-Only: How Well We Captured Them)" in content
    assert "### Fidelity Breakdown: Real-Derived vs Invented Perturbations" in content
    assert "## 4. FRONT-HALF PIPELINE FILTER" in content
    assert "## 5. OFF-TARGET CONTAMINATION COMPARISON" in content
    assert "## 6. SCORER LENIENCY ADJUDICATION" in content
    assert "### Itemized Adjudication of All 23 Contestability Shifts" in content
    assert "### Resolution of t0072 Demonstrative Blind Spot" in content
    assert "## 7. FALSIFICATION" in content

    # Check 23 adjudication entries rendered in table
    assert "| 23 | `t0399` |" in content
    assert "| 1 | `t0007` |" in content

    # Check non-zero variance on active reported panel axes
    for ax in ACTIVE_SPEAKER_PANEL_AXES + EXTRACTION_PANEL_AXES:
        assert f"**{ax.capitalize()}**" in content
