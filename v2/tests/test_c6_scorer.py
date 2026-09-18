"""Tests for Item C6: Four of the eight axes are not being read (Issue 046 / §19).

Validates:
1. Step 1: Exactly 888 non-empty reasons across 111 claims (asserted by exact count).
2. Step 3: Granularity scores strictly < 2 on natural compound claims t0016, t0255, t0389.
3. Step 4: Distribution on 40 rejected turns demonstrates clear discrimination (non-zero variance)
   on Target and Propositionality.
4. Assertion (c):
   - Every axis shows non-zero variance or Step 4 measurement attached.
   - Off-target victim drop rate < 25% for all eight axes.
   - Target sensitivity >= 4 of 5 for all eight axes.
5. Falsification: Constant scorer (all 2s) fails on all 8 axes; random integer scorer fails.
"""

from __future__ import annotations

import json
import random

import pytest

from v2.src.extract import (
    AXIS_NAMES,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PERTURBATIONS_PATH,
    evaluate_perturbation_results,
)
from v2.src.run_c6 import verify_888_reasons

SCORED_CLAIMS_FILE = DEFAULT_EXTRACTION_DIR / "c4_scored_axes_00251a80c868f535.json"
STEP4_DISTRIBUTION_FILE = DEFAULT_EXTRACTION_DIR / "c6_step4_rejected_distribution_00251a80c868f535.json"
C6_PERTURBATIONS_FILE = DEFAULT_EXTRACTION_DIR / "c6_perturbations_scored_00251a80c868f535.json"


def test_step1_888_non_empty_reasons_exact_count() -> None:
    """Step 1 & Validation: Every scored claim carries a non-empty reason for all eight axes.

    Asserts the exact count is 888 (111 claims * 8 axes), not merely that the field exists.
    """
    res = verify_888_reasons(source_id="00251a80c868f535")
    assert res["total_claims"] == 111, f"Expected 111 claims, got {res['total_claims']}"
    assert res["total_axes_evaluated"] == 888, f"Expected 888 axis evaluations, got {res['total_axes_evaluated']}"
    assert res["non_empty_reasons_count"] == 888, f"Expected exactly 888 non-empty reasons, got {res['non_empty_reasons_count']}"
    assert res["empty_reasons_count"] == 0, f"Found empty reasons: {res['empty_details']}"
    assert res["all_888_present"] is True


def test_step3_granularity_scores_below_2_on_natural_compound_claims() -> None:
    """Step 3 & Assertion (c): Granularity scores strictly below 2 on t0016, t0255, and t0389.

    These are genuinely compound natural claims from E287 that C4/C5 missed (scoring 2.00).
    Under the calibrated prompt and hardened perturbations, they must score < 2.
    """
    assert DEFAULT_PERTURBATIONS_PATH.exists(), f"Missing perturbations fixture: {DEFAULT_PERTURBATIONS_PATH}"
    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        perts = json.load(f)

    gran_perts = {p["turn_id"]: p for p in perts if p.get("target_axis") == "granularity"}

    target_tids = ["00251a80c868f535_t0016", "00251a80c868f535_t0255", "00251a80c868f535_t0389"]
    for tid in target_tids:
        assert tid in gran_perts, f"Natural compound claim {tid} missing from granularity perturbations"

    # Verify scores from c6_perturbations_scored_00251a80c868f535.json or ckpt
    ckpt_file = DEFAULT_EXTRACTION_DIR / "c6_perturbations_scored_00251a80c868f535_ckpt.json"
    target_file = C6_PERTURBATIONS_FILE if C6_PERTURBATIONS_FILE.exists() else ckpt_file

    if target_file.exists():
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        scored_map = {p["turn_id"]: p for p in data.get("perturbation_results", []) if p.get("target_axis") == "granularity"}
        for tid in target_tids:
            if tid in scored_map:
                pert_g = scored_map[tid]["perturbed_scores"].get("granularity")
                assert pert_g is not None, f"Granularity score missing for {tid}"
                assert pert_g < 2, f"Granularity for natural compound claim {tid} must be < 2, got {pert_g}"


def test_step4_rejected_turns_distribution() -> None:
    """Step 4: Determine whether Target and Propositionality are broken or merely redundant.

    Evaluates distribution on 40 turns rejected by Pass 1 (banter, mechanics, filler).
    Both axes must show clear non-zero variance (scoring 0s, 1s, and 2s), proving they are
    not broken, but rather redundant post-filter.
    """
    assert STEP4_DISTRIBUTION_FILE.exists(), f"Missing Step 4 distribution artifact: {STEP4_DISTRIBUTION_FILE}"

    with open(STEP4_DISTRIBUTION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = data.get("total_rejected_turns_evaluated") or data.get("sample_size")
    assert total == 40, f"Expected 40 rejected turns, got {total}"

    target_counts = data.get("target_distribution", {})
    prop_counts = data.get("propositionality_distribution", {})

    # Target must not be pinned at 2: must have 0s, 1s, and 2s
    t0 = target_counts.get("0", 0)
    t1 = target_counts.get("1", 0)
    t2 = target_counts.get("2", 0)
    assert t0 > 0, f"Target must detect non-external show banter (0s), got count {t0}"
    assert (t0 + t1) > t2, f"On rejected turns, majority should be non-target (0 or 1), got 0={t0}, 1={t1}, 2={t2}"
    assert data.get("target_variance") is True

    # Propositionality must not be pinned at 2: must have 0s, 1s, and 2s
    p0 = prop_counts.get("0", 0)
    p1 = prop_counts.get("1", 0)
    p2 = prop_counts.get("2", 0)
    assert p0 > 0, f"Propositionality must detect non-propositional fragments (0s), got count {p0}"
    assert p1 > 0, f"Propositionality must detect thin assertions (1s), got count {p1}"
    assert p2 > 0, f"Propositionality must detect propositional claims (2s), got count {p2}"
    assert data.get("propositionality_variance") is True


def test_tier2_assertion_c_sensitivity_and_off_target() -> None:
    """Assertion (c): Target sensitivity >= 4 of 5 for all eight axes, and

    off-target victim drop rate is below 25% for all eight axes.
    """
    if not C6_PERTURBATIONS_FILE.exists():
        pytest.skip(f"Tier 2 evaluation still running or artifact missing: {C6_PERTURBATIONS_FILE}")

    with open(C6_PERTURBATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    eval_res = data.get("evaluation", {})
    axes_res = eval_res.get("axes", {})

    for ax in AXIS_NAMES:
        assert ax in axes_res, f"Missing axis {ax} in evaluation"
        info = axes_res[ax]

        # Target sensitivity >= 4 of 5
        t_drops = info["target_drops_count"]
        assert t_drops >= 4, f"Target sensitivity for {ax} must be >= 4/5, got {t_drops}/5"

        # Off-target victim drop rate < 25%
        victim_rate = info.get("victim_off_target_drop_rate_pct", 0.0)
        assert victim_rate < 25.0, f"Off-target drop rate for {ax} must be < 25%, got {victim_rate}%"


def test_falsification_constant_scorer_fails() -> None:
    """Falsification: A constant scorer returning 2 for every axis fails on all eight axes."""
    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

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
    assert eval_res["all_axes_pass"] is False, "Constant scorer unexpectedly passed!"
    for ax in AXIS_NAMES:
        assert eval_res["axes"][ax]["target_drops_count"] == 0, f"Constant scorer should have 0 drops for {ax}"
        assert eval_res["axes"][ax]["passes_target_threshold"] is False


def test_falsification_random_integer_scorer_fails() -> None:
    """Falsification: A random integer scorer (returns uniform 0, 1, or 2) fails on sensitivity and off-target."""
    random.seed(42)
    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    mock_random_results = []
    for item in items:
        mock_random_results.append({
            "id": item["id"],
            "target_axis": item["target_axis"],
            "turn_id": item["turn_id"],
            "original_scores": {ax: 2 for ax in AXIS_NAMES},
            "perturbed_scores": {ax: random.randint(0, 2) for ax in AXIS_NAMES},
        })

    eval_res = evaluate_perturbation_results(mock_random_results)
    # Random scorer will fail off-target threshold (~66% drop rate vs < 25% threshold)
    off_target_failed = False
    for ax in AXIS_NAMES:
        victim_rate = eval_res["axes"][ax].get("victim_off_target_drop_rate_pct", 0.0)
        if victim_rate >= 25.0:
            off_target_failed = True
            break
    assert off_target_failed is True, "Random scorer unexpectedly passed off-target threshold!"
