"""Tests for Item C5: Validate the scorer without human labels (Issue 045 = B).

Verifies:
1. Perturbations fixture exists with 40 items (5 pairs per axis * 8 axes).
2. Falsification: A deliberately broken constant scorer (returns 2 for everything) fails Tier 2.
3. Assertion (c): For each of the eight axes, perturbed items score strictly lower on the targeted
   axis than their unperturbed originals in at least 4 of 5 pairs, with off-target movement reported.
   Committed RED (xfail strict=True) until c5 runner produces c5_perturbations_scored.json.
"""

from __future__ import annotations

import json

import pytest

from v2.src.extract import (
    AXIS_NAMES,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PERTURBATIONS_PATH,
    evaluate_perturbation_results,
)

SCORED_PERTURBATIONS_FILE = DEFAULT_EXTRACTION_DIR / "c5_perturbations_scored.json"


def test_perturbations_fixture_validity() -> None:
    """Fixture validation: perturbations.json exists, contains 40 items, 5 per axis across all 8 axes."""
    assert DEFAULT_PERTURBATIONS_PATH.exists(), f"Missing perturbations fixture: {DEFAULT_PERTURBATIONS_PATH}"

    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    assert len(items) == 40, f"Expected 40 perturbation items, got {len(items)}"

    axes_counts: dict[str, int] = {}
    for item in items:
        for required_key in [
            "id",
            "target_axis",
            "turn_id",
            "speaker",
            "quote",
            "turn_text",
            "original_claim",
            "perturbed_claim",
            "perturbation_description",
        ]:
            assert required_key in item, f"Missing key '{required_key}' in item {item.get('id')}"

        ax = item["target_axis"]
        assert ax in AXIS_NAMES, f"Invalid axis '{ax}' in item {item.get('id')}"
        axes_counts[ax] = axes_counts.get(ax, 0) + 1

    assert len(axes_counts) == 8, f"Expected all 8 axes in fixture, got {len(axes_counts)}"
    for ax, count in axes_counts.items():
        assert count == 5, f"Expected 5 items for axis '{ax}', got {count}"


def test_falsification_constant_scorer_fails() -> None:
    """Falsification test: A constant scorer returning 2 for everything must fail the sensitivity assertion.

    A validation suite that passes against a constant is testing nothing (traps 31, 80).
    """
    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    # Construct mock results where both original and perturbed score 2 on every axis
    mock_constant_results = []
    for item in items:
        mock_constant_results.append({
            "id": item["id"],
            "target_axis": item["target_axis"],
            "turn_id": item["turn_id"],
            "original_scores": {ax: 2 for ax in AXIS_NAMES},
            "perturbed_scores": {ax: 2 for ax in AXIS_NAMES},
        })

    eval_res = evaluate_perturbation_results(mock_constant_results)
    assert eval_res["all_axes_pass"] is False, "Falsification failure: constant scorer passed sensitivity assertion!"
    for ax in AXIS_NAMES:
        ax_res = eval_res["axes"][ax]
        assert ax_res["target_drops_count"] == 0, f"Expected 0 drops for axis {ax}, got {ax_res['target_drops_count']}"
        assert ax_res["passes_target_threshold"] is False, f"Axis {ax} should have failed under constant scoring"


@pytest.mark.xfail(strict=True, reason="Committed RED before C5 runner produces c5_perturbations_scored.json")
def test_c5_assertion_c_perturbation_sensitivity() -> None:
    """Assertion (c): for each of the eight axes, perturbed items score strictly lower

    on that axis than their unperturbed originals in at least 4 of 5 pairs,
    with off-target movement reported.
    """
    assert SCORED_PERTURBATIONS_FILE.exists(), f"Artifact not yet generated: {SCORED_PERTURBATIONS_FILE}"

    with open(SCORED_PERTURBATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("perturbation_results", [])
    assert len(results) == 40, f"Expected 40 scored perturbation pairs, got {len(results)}"

    eval_res = evaluate_perturbation_results(results)

    # Print summary diagnostics
    for ax in AXIS_NAMES:
        ax_res = eval_res["axes"][ax]
        drops = ax_res["target_drops_count"]
        off_drops = ax_res["off_target_drops_count"]
        off_rate = ax_res["off_target_drop_rate_pct"]
        print(f"[{ax:20s}] target drops: {drops}/5 | off-target drops: {off_drops} ({off_rate}%)")

    assert eval_res["all_axes_pass"] is True, f"Sensitivity assertion failed: {eval_res}"
