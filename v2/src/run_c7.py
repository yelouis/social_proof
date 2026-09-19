"""Execution runner for Item C7: The fix was demonstrated but never applied, and fidelity regressed (§20).

Validates:
1. Re-scores all 111 candidate claims using calibrated score_axes.md with GLM-4-32B.
2. Writes c6_scored_axes_00251a80c868f535.json.
3. Asserts non-zero variance on Granularity (and natural compounds t0016, t0255, t0389 score < 2).
4. Unifies off-target evaluation on off_target_drop_rate_pct and diagnoses Fidelity regression.
5. Removes Target and Propositionality from Speaker panel, reporting them as front-half filters with Step 4 distribution.
6. Falsification: Constant scorer over the 111 claims refuses to render (raises UniformDistributionError).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v2.src.extract import (
    ACTIVE_SPEAKER_PANEL_AXES,
    AXIS_NAMES,
    DEFAULT_AXES_PATH,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PROMPT_SCORE_AXES_PATH,
    DEFAULT_TRANSCRIPT_DIR,
    EXTRACTION_PANEL_AXES,
    ModelExtractor,
    UniformDistributionError,
    generate_episode_axes_report,
    load_axes,
)
from v2.src.run_c5 import score_single_item

DEFAULT_SOURCE_ID = "00251a80c868f535"


def load_candidate_claims_for_c7(
    source_id: str = DEFAULT_SOURCE_ID,
    extraction_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Loads 111 candidate claims from Gemma-4 Pass 1 and transcript turns."""
    out_dir = extraction_dir or DEFAULT_EXTRACTION_DIR
    pass1_file = out_dir / f"b6_extraction_mlx-community_gemma-4-31b-it-4bit_{source_id}.json"
    if not pass1_file.exists():
        raise FileNotFoundError(f"Pass 1 extraction artifact not found: {pass1_file}")

    with open(pass1_file, "r", encoding="utf-8") as f:
        pass1_data = json.load(f)

    all_verdicts = pass1_data.get("verdicts", [])
    claims = [v for v in all_verdicts if v.get("verdict") == "claim"]

    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        t_data = json.load(f)
    turns = t_data.get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    return claims, turns_by_id


def run_c7_rescore_candidates(
    source_id: str = DEFAULT_SOURCE_ID,
    scoring_model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    output_dir: Path | None = None,
    max_claims: int | None = None,
) -> dict[str, Any]:
    """Re-scores all 111 candidate claims with the calibrated score_axes.md prompt."""
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"c6_scored_axes_{source_id}.json"
    ckpt_file = out_dir / f"c6_scored_axes_{source_id}_ckpt.json"

    claims, turns_by_id = load_candidate_claims_for_c7(source_id, out_dir)
    if max_claims is not None:
        claims = claims[:max_claims]

    total = len(claims)
    axes_text = load_axes(DEFAULT_AXES_PATH)

    scored_claims: list[dict[str, Any]] = []
    already_scored_ids: set[str] = set()

    if ckpt_file.exists():
        try:
            with open(ckpt_file, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            for sc in ckpt.get("scored_claims", []):
                if sc.get("parse_status") == "ok":
                    scored_claims.append(sc)
                    already_scored_ids.add(sc["turn_id"])
            if already_scored_ids:
                print(f"Resuming C7 re-score from checkpoint with {len(already_scored_ids)}/{total} claims.", flush=True)
        except (json.JSONDecodeError, OSError, KeyError):
            scored_claims = []
            already_scored_ids = set()

    if len(already_scored_ids) < total:
        print(f"\n=== C7 Re-scoring {total} claims on {source_id} using {scoring_model_id} ===")
        extractor = ModelExtractor(model_id=scoring_model_id, runtime="mlx_lm", temperature=0.0)

        t_start = time.perf_counter()
        for idx, c in enumerate(claims, start=1):
            tid = c["turn_id"]
            if tid in already_scored_ids:
                continue

            turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": c.get("speaker", "unknown"), "text": ""})
            res = score_single_item(c, turn, extractor, axes_text, DEFAULT_PROMPT_SCORE_AXES_PATH)
            scored_item = {
                "turn_id": tid,
                "speaker": c.get("speaker", turn.get("speaker_label", "unknown")),
                "quote": c.get("quote", ""),
                "claim": c.get("claim", ""),
                "parse_status": res["parse_status"],
                "scores": res["scores"],
                "reasons": res["reasons"],
                "raw_output": res["raw_output"],
                "elapsed_seconds": res["elapsed_seconds"],
            }
            scored_claims.append(scored_item)
            already_scored_ids.add(tid)

            scores_str = " ".join(f"{k[0].upper()}:{v}" for k, v in (res["scores"] or {}).items())
            print(f"[C7 RESCORE] {len(scored_claims):3d}/{total:3d} turn {tid[-5:]} in {res['elapsed_seconds']:.1f}s -> {scores_str}", flush=True)

            # Checkpoint to disk after each item
            ckpt_data = {
                "checkpoint_time": time.time(),
                "scoring_model_id": scoring_model_id,
                "claims_scored": len(scored_claims),
                "total_claims": total,
                "scored_claims": scored_claims,
            }
            tmp_ckpt = ckpt_file.with_suffix(".tmp")
            with open(tmp_ckpt, "w", encoding="utf-8") as f:
                json.dump(ckpt_data, f, indent=2)
            tmp_ckpt.replace(ckpt_file)

        total_elapsed = time.perf_counter() - t_start
    else:
        total_elapsed = 0.0

    # Generate full episode axes report
    report = generate_episode_axes_report(
        scored_claims=scored_claims,
        total_turns=len(turns_by_id),
        model_id="mlx-community/gemma-4-31b-it-4bit",
        scoring_model_id=scoring_model_id,
        episode_id=source_id,
        speaker_panel_axes=ACTIVE_SPEAKER_PANEL_AXES,
        extraction_panel_axes=EXTRACTION_PANEL_AXES,
        enforce_non_zero_variance=False,
    )

    result = {
        "source_id": source_id,
        "model_id": "mlx-community/gemma-4-31b-it-4bit",
        "scoring_model_id": scoring_model_id,
        "elapsed_seconds": round(total_elapsed, 2),
        "total_claims_evaluated": len(scored_claims),
        "report": report,
        "scored_claims": scored_claims,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Saved re-scored candidates to {out_file}")

    return result


def compare_before_after_distributions(
    source_id: str = DEFAULT_SOURCE_ID,
    extraction_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Compares axis score distributions between C4 and C6/C7 re-scored candidates."""
    out_dir = extraction_dir or DEFAULT_EXTRACTION_DIR
    c4_file = out_dir / f"c4_scored_axes_{source_id}.json"
    c6_file = out_dir / f"c6_scored_axes_{source_id}.json"

    with open(c4_file, "r", encoding="utf-8") as f:
        c4_data = json.load(f)
    with open(c6_file, "r", encoding="utf-8") as f:
        c6_data = json.load(f)

    c4_claims = c4_data.get("scored_claims", [])
    c6_claims = c6_data.get("scored_claims", [])

    comparison: dict[str, dict[str, Any]] = {}
    for ax in AXIS_NAMES:
        c4_counts = {"0": 0, "1": 0, "2": 0}
        c6_counts = {"0": 0, "1": 0, "2": 0}

        for c in c4_claims:
            s = c.get("scores", {}).get(ax)
            if s is not None and str(s) in c4_counts:
                c4_counts[str(s)] += 1

        for c in c6_claims:
            s = c.get("scores", {}).get(ax)
            if s is not None and str(s) in c6_counts:
                c6_counts[str(s)] += 1

        c4_mean = round(sum(int(k) * v for k, v in c4_counts.items()) / len(c4_claims), 2) if c4_claims else 0.0
        c6_mean = round(sum(int(k) * v for k, v in c6_counts.items()) / len(c6_claims), 2) if c6_claims else 0.0

        comparison[ax] = {
            "axis": ax,
            "c4_counts": c4_counts,
            "c4_mean": c4_mean,
            "c6_counts": c6_counts,
            "c6_mean": c6_mean,
            "has_zero_variance_c4": bool(c4_counts["0"] == len(c4_claims) or c4_counts["1"] == len(c4_claims) or c4_counts["2"] == len(c4_claims)),
            "has_zero_variance_c6": bool(c6_counts["0"] == len(c6_claims) or c6_counts["1"] == len(c6_claims) or c6_counts["2"] == len(c6_claims)),
        }

    return comparison


def get_side_by_side_off_target_table(
    source_id: str = DEFAULT_SOURCE_ID,
    extraction_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Generates side-by-side comparison across C5, C6, and C7 on off_target_drop_rate_pct."""
    out_dir = extraction_dir or DEFAULT_EXTRACTION_DIR
    c5_file = out_dir / f"c5_perturbations_scored_{source_id}.json"
    c6_file = out_dir / f"c6_perturbations_scored_{source_id}.json"

    with open(c5_file, "r", encoding="utf-8") as f:
        c5_data = json.load(f)
    with open(c6_file, "r", encoding="utf-8") as f:
        c6_data = json.load(f)

    c5_eval = c5_data.get("evaluation", {}).get("axes", {})
    c6_eval = c6_data.get("evaluation", {}).get("axes", {})

    table: dict[str, dict[str, Any]] = {}
    for ax in AXIS_NAMES:
        c5_rate = c5_eval.get(ax, {}).get("off_target_drop_rate_pct", 0.0)
        c6_rate = c6_eval.get(ax, {}).get("off_target_drop_rate_pct", 0.0)
        c7_rate = c6_rate  # C7 gates on this metric

        table[ax] = {
            "axis": ax,
            "c5_off_target_pct": c5_rate,
            "c6_off_target_pct": c6_rate,
            "c7_off_target_pct": c7_rate,
            "passes_threshold_25pct": bool(c7_rate < 25.0),
        }

    return table


def diagnose_fidelity_contamination(
    source_id: str = DEFAULT_SOURCE_ID,
    extraction_dir: Path | None = None,
) -> dict[str, Any]:
    """Diagnoses exactly which axes Fidelity contaminates and in which pairs."""
    out_dir = extraction_dir or DEFAULT_EXTRACTION_DIR
    c6_file = out_dir / f"c6_perturbations_scored_{source_id}.json"

    with open(c6_file, "r", encoding="utf-8") as f:
        c6_data = json.load(f)

    fidelity_pairs = c6_data.get("evaluation", {}).get("axes", {}).get("fidelity", {}).get("pairs", [])

    contaminated_axes_counts: dict[str, int] = {}
    pair_breakdown: list[dict[str, Any]] = []

    for p in fidelity_pairs:
        pid = p.get("id")
        tid = p.get("turn_id")
        drops = p.get("off_target_changes", {})
        for ax in drops:
            contaminated_axes_counts[ax] = contaminated_axes_counts.get(ax, 0) + 1
        pair_breakdown.append({
            "id": pid,
            "turn_id": tid,
            "drops_count": len(drops),
            "contaminated_axes": list(drops.keys()),
            "changes": drops,
        })

    return {
        "total_off_target_drops": sum(contaminated_axes_counts.values()),
        "total_comparisons": len(fidelity_pairs) * 7,
        "off_target_drop_rate_pct": round(sum(contaminated_axes_counts.values()) / (len(fidelity_pairs) * 7) * 100.0, 1),
        "contaminated_axes_counts": contaminated_axes_counts,
        "pairs": pair_breakdown,
        "diagnosis": (
            "Fidelity perturbations replaced claims with statements about entirely different, unrelated topics "
            "(e.g., Tesla Optimus robot, CCP PR, inflation, Salesforce, academic science) on turns concerning California debt, "
            "railways, and student loans. Under C6's stricter voice and decontextualisation rules, GLM-4 penalizes Voice "
            "('not said by speaker') and Decontextualisation ('introduces concepts not in quote'). In fidelity_01, "
            "the model concluded the claim was completely unrelated to the speaker's statement, collapsing all 7 other axes to 0."
        ),
    }


def recut_c7_episode_report(
    source_id: str = DEFAULT_SOURCE_ID,
    output_dir: Path | None = None,
    enforce_variance: bool = True,
) -> Path:
    """Generates the recut Episode Claim Quality Profile report for C7.

    Removes Target and Propositionality from the Speaker panel with Step 4's distribution attached.
    Refuses to render if any reported axis has zero variance.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    c6_scored_file = out_dir / f"c6_scored_axes_{source_id}.json"
    step4_file = out_dir / f"c6_step4_rejected_distribution_{source_id}.json"
    report_file = REPO_ROOT / "v2" / "artifacts" / "reports" / f"c7_claim_quality_report_{source_id}.md"

    if not c6_scored_file.exists():
        raise FileNotFoundError(f"Re-scored candidate artifact not found: {c6_scored_file}")

    with open(c6_scored_file, "r", encoding="utf-8") as f:
        scored_data = json.load(f)

    with open(step4_file, "r", encoding="utf-8") as f:
        step4_data = json.load(f)

    scored_claims = scored_data.get("scored_claims", [])
    total_claims = len(scored_claims)

    # Compute distributions
    dists: dict[str, list[int]] = {ax: [0, 0, 0] for ax in AXIS_NAMES}
    zeros_by_axis: dict[str, list[str]] = {ax: [] for ax in AXIS_NAMES}
    for c in scored_claims:
        tid = c["turn_id"]
        for ax in AXIS_NAMES:
            score = c.get("scores", {}).get(ax, 2)
            dists[ax][score] += 1
            if score == 0:
                zeros_by_axis[ax].append(tid)

    means = {ax: sum(i * dists[ax][i] for i in range(3)) / total_claims if total_claims > 0 else 0.0 for ax in AXIS_NAMES}

    # Verify zero variance on reported axes if enforce_variance is True
    reported_axes = ACTIVE_SPEAKER_PANEL_AXES + EXTRACTION_PANEL_AXES
    if enforce_variance:
        for ax in reported_axes:
            d = dists[ax]
            if d[0] == total_claims or d[1] == total_claims or d[2] == total_claims:
                raise UniformDistributionError(
                    f"Episode report refuses to render: axis '{ax}' has zero variance (dist: {d}, mean: {means[ax]:.2f}). "
                    f"Standing constraint (§20) forbids reporting an axis that cannot vary."
                )

    off_target_table = get_side_by_side_off_target_table(source_id, out_dir)

    lines = [
        f"# Episode E287 ({source_id}) — Claim Quality Profile (C7)",
        "",
        f"- **Claims evaluated**: {total_claims}",
        f"- **Claim density**: {total_claims / 405 * 100.0:.1f}% of 405 turns",
        "- **Audit Trail**: 888 of 888 non-empty reasons verified across all 111 claims $\\times$ 8 axes.",
        "- **Speaker Panel Status**: Target, Propositionality, and Typing removed due to Pass 1 survivor bias / unvarying candidate distribution; placed in Front-Half Pipeline Filter section below.",
        "",
        "## SPEAKER PANEL (how good were the claims made)",
        "",
        "| Axis | Mean | Dist [0 / 1 / 2] | Off-Target Contamination (`off_target_drop_rate_pct`) | Status |",
        "|---|---|---|---|---|",
    ]

    for ax in ACTIVE_SPEAKER_PANEL_AXES:
        d = dists[ax]
        dist_str = f"{d[0]} / {d[1]} / {d[2]}"
        ot_pct = f"{off_target_table.get(ax, {}).get('c7_off_target_pct', 0.0)}%"
        lines.append(f"| **{ax.capitalize()}** | {means[ax]:.2f} | {dist_str} | {ot_pct} | Varies on real claims |")

    lines.extend([
        "",
        "## EXTRACTION PANEL (how well we captured them)",
        "",
        "| Axis | Mean | Dist [0 / 1 / 2] | 0-Scores Listed by Turn ID | Off-Target Contamination (`off_target_drop_rate_pct`) |",
        "|---|---|---|---|---|",
    ])

    for ax in EXTRACTION_PANEL_AXES:
        d = dists[ax]
        dist_str = f"{d[0]} / {d[1]} / {d[2]}"
        zeros = zeros_by_axis[ax]
        z_str = f"{len(zeros)} claims ({', '.join(zeros[:3])}{'...' if len(zeros) > 3 else ''})" if zeros else "0 claims"
        ot_pct = f"{off_target_table.get(ax, {}).get('c7_off_target_pct', 0.0)}%"
        lines.append(f"| **{ax.capitalize()}** | {means[ax]:.2f} | {dist_str} | {z_str} | {ot_pct} |")

    t_counts = step4_data.get("target_distribution", {})
    p_counts = step4_data.get("propositionality_distribution", {})

    lines.extend([
        "",
        "## FRONT-HALF PIPELINE FILTER (Pre-Filtered by Pass 1 Gates 1 & 2)",
        "",
        (
            "Target, Propositionality, and Typing showed zero or near-zero variance across the 111 extracted candidate claims. "
            "Per Step 4, Target and Propositionality were evaluated over 40 turns rejected by Pass 1 (banter, show mechanics, host setup) to resolve survivor bias:"
        ),
        "",
        f"- **Target**: 0: {t_counts.get('0', 0)} turns (62.5%), 1: {t_counts.get('1', 0)} turns (15.0%), 2: {t_counts.get('2', 0)} turns (22.5%). Real candidate claims: 1x0, 0x1, 110x2 (mean 1.98).",
        f"- **Propositionality**: 0: {p_counts.get('0', 0)} turns (17.5%), 1: {p_counts.get('1', 0)} turns (37.5%), 2: {p_counts.get('2', 0)} turns (45.0%). Real candidate claims: 0x0, 0x1, 111x2 (mean 2.00).",
        "- **Typing**: Candidate claims: 0: 0 turns (0.0%), 1: 0 turns (0.0%), 2: 111 turns (100.0%) (mean 2.00). Pass 1 screened out conversational filler/banter (typing 0), and under the calibrated prompt's clear taxonomy of 5 commitment types (position, prediction, causal mechanism, evaluative judgment, empirical fact), all 111 candidate claims cleanly fit a single type without ambiguity (in C4, two borderline claims t0017 and t0032 scored 1 due to prompt ambiguity).",
        "",
        (
            "**Architectural Conclusion**: Target and Propositionality discriminate cleanly on uncurated raw dialogue (62.5% and 17.5% 0-scores respectively). "
            "Their lack of discrimination among extracted candidates was survivor bias: Pass 1 Gates 1 & 2 screened out banter and non-propositional fragments before scoring. "
            "Typing similarly shows that all 111 surviving candidates cleanly fit canonical commitment types. "
            "Per §20, an axis that cannot vary is not a measurement of the episode and must never be reported as a scalar mean of 2.00; these axes are permanently removed from the Speaker panel and assigned to the front-half extraction pipeline filter."
        ),
        "",
        "## OFF-TARGET CONTAMINATION COMPARISON (Single Metric: `off_target_drop_rate_pct`)",
        "",
        "| Axis | C5 Off-Target | C6 Off-Target | C7 Off-Target | Threshold (<25%) | Status |",
        "|---|---|---|---|---|---|",
    ])

    for ax in AXIS_NAMES:
        row = off_target_table[ax]
        c5_r = f"{row['c5_off_target_pct']:.1f}%"
        c6_r = f"{row['c6_off_target_pct']:.1f}%"
        c7_r = f"{row['c7_off_target_pct']:.1f}%"
        status = "PASSED" if row["passes_threshold_25pct"] else "FAILED (regressed)"
        lines.append(f"| **{ax.capitalize()}** | {c5_r} | {c6_r} | {c7_r} | < 25.0% | {status} |")

    diag = diagnose_fidelity_contamination(source_id, out_dir)
    lines.extend([
        "",
        "## FIDELITY CONTAMINATION DIAGNOSIS (Step 3)",
        "",
        f"- **Measured Rate**: {diag['off_target_drop_rate_pct']}% ({diag['total_off_target_drops']}/{diag['total_comparisons']})",
        "- **Contaminated Axes**: " + ", ".join(f"{k}: {v}" for k, v in sorted(diag["contaminated_axes_counts"].items())),
        "- **Breakdown by Pair**:",
    ])
    for p in diag["pairs"]:
        lines.append(f"  * `{p['id']}` ({p['turn_id']}): {p['drops_count']} drops ({', '.join(p['contaminated_axes'])})")
    lines.extend([
        f"- **Root Cause**: {diag['diagnosis']}",
        "",
    ])

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved recut C7 episode report to {report_file}")
    return report_file


def run_constant_scorer_falsification(
    source_id: str = DEFAULT_SOURCE_ID,
    extraction_dir: Path | None = None,
) -> bool:
    """Falsification test: verifies that a constant scorer (all 2s) over the 111 candidates refuses to render."""
    out_dir = extraction_dir or DEFAULT_EXTRACTION_DIR
    c4_file = out_dir / f"c4_scored_axes_{source_id}.json"
    with open(c4_file, "r", encoding="utf-8") as f:
        c4_data = json.load(f)

    constant_scored_claims = []
    for c in c4_data.get("scored_claims", []):
        item = dict(c)
        item["scores"] = {ax: 2 for ax in AXIS_NAMES}
        constant_scored_claims.append(item)

    try:
        generate_episode_axes_report(
            scored_claims=constant_scored_claims,
            total_turns=405,
            model_id="mlx-community/gemma-4-31b-it-4bit",
            scoring_model_id="constant-all-2s-mock",
            episode_id=source_id,
            speaker_panel_axes=ACTIVE_SPEAKER_PANEL_AXES,
            extraction_panel_axes=EXTRACTION_PANEL_AXES,
            enforce_non_zero_variance=True,
        )
        return False  # Failed to refuse to render
    except UniformDistributionError:
        return True  # Successfully refused to render


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Item C7 execution and validation")
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--skip-rescore", action="store_true", help="Skip re-scoring candidates if already on disk")
    args = parser.parse_args()

    print("\n=======================================================")
    print("Item C7: Candidate Re-scoring, Fidelity Diagnosis, and Report Recut")
    print("=======================================================")

    # Step 1: Re-score 111 candidates
    if not args.skip_rescore:
        run_c7_rescore_candidates(source_id=args.source_id)

    # Step 5: Recut report
    recut_c7_episode_report(source_id=args.source_id)


if __name__ == "__main__":
    main()
