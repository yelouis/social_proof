"""Score C9 Fidelity Perturbations with Calibrated Scorer on Both Sides.

Scores all 5 fidelity pairs (both original and perturbed sides) using GLM-4-32B
at temperature 0.0 with the calibrated prompt template (v2/prompts/score_axes.md).
Merges with the 35 non-fidelity pairs from C8.
Records fixture_sha256 in the output artifact to prevent stale fixture reads.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v2.src.extract import (
    AXIS_NAMES,
    DEFAULT_AXES_PATH,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_FIXTURES_AXES_DIR,
    DEFAULT_PROMPT_SCORE_AXES_PATH,
    DEFAULT_TRANSCRIPT_DIR,
    ModelExtractor,
    evaluate_perturbation_results,
    load_axes,
)
from v2.src.run_c5 import score_single_item
from v2.src.run_c7 import DEFAULT_SOURCE_ID


def run_c9_fidelity_scoring(source_id: str = DEFAULT_SOURCE_ID) -> dict[str, Any]:
    fixtures_path = DEFAULT_FIXTURES_AXES_DIR / "perturbations.json"
    fixture_bytes = fixtures_path.read_bytes()
    fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()

    with open(fixtures_path, "r", encoding="utf-8") as f_in:
        perturbations = json.load(f_in)

    # Load C8 perturbation scored results for non-fidelity pairs
    c8_file = DEFAULT_EXTRACTION_DIR / f"c8_perturbations_scored_{source_id}.json"
    with open(c8_file, "r", encoding="utf-8") as f_c8:
        c8_data = json.load(f_c8)

    non_fid_results = [
        item for item in c8_data.get("perturbation_results", [])
        if item.get("target_axis") != "fidelity"
    ]
    if len(non_fid_results) != 35:
        raise ValueError(f"Expected 35 non-fidelity pairs from C8, found {len(non_fid_results)}")

    # Load transcript turns
    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f_trans:
        turns = json.load(f_trans).get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    axes_text = load_axes(DEFAULT_AXES_PATH)
    extractor = ModelExtractor(
        model_id="mlx-community/GLM-4-32B-0414-4bit",
        runtime="mlx_lm",
        temperature=0.0,
    )

    fidelity_pairs = [p for p in perturbations if p.get("target_axis") == "fidelity"]
    if len(fidelity_pairs) != 5:
        raise ValueError(f"Expected 5 fidelity pairs in fixture, found {len(fidelity_pairs)}")

    print(f"\n=== Scoring {len(fidelity_pairs)} fidelity pairs on BOTH sides with calibrated prompt ===")
    scored_fidelity_results: list[dict[str, Any]] = []

    for idx, item in enumerate(fidelity_pairs, start=1):
        pid = item["id"]
        tid = item["turn_id"]
        speaker = item["speaker"]
        turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": speaker, "text": item["turn_text"]})

        orig_quote = item.get("quote", "")
        orig_claim = item["original_claim"]
        orig_turn_text = item.get("turn_text", turn.get("text", ""))

        pert_quote = item.get("perturbed_quote", orig_quote)
        pert_claim = item["perturbed_claim"]
        pert_turn_text = item.get("perturbed_turn_text", orig_turn_text)

        orig_turn = {"turn_id": tid, "speaker_label": speaker, "text": orig_turn_text}
        pert_turn = {"turn_id": tid, "speaker_label": speaker, "text": pert_turn_text}

        print(f"\n[{idx}/5] {pid} ({tid}): Scoring original claim...", flush=True)
        t0 = time.perf_counter()
        orig_scored = score_single_item(
            item={"turn_id": tid, "speaker": speaker, "quote": orig_quote, "claim": orig_claim},
            turn=orig_turn,
            extractor=extractor,
            axes_text=axes_text,
            prompt_template_path=DEFAULT_PROMPT_SCORE_AXES_PATH,
            max_tokens=500,
        )
        orig_elapsed = time.perf_counter() - t0
        print(f"  -> ORIG Fidelity: {orig_scored['scores'].get('fidelity')} ({orig_elapsed:.1f}s)", flush=True)

        print(f"[{idx}/5] {pid} ({tid}): Scoring perturbed claim...", flush=True)
        t0 = time.perf_counter()
        pert_scored = score_single_item(
            item={"turn_id": tid, "speaker": speaker, "quote": pert_quote, "claim": pert_claim},
            turn=pert_turn,
            extractor=extractor,
            axes_text=axes_text,
            prompt_template_path=DEFAULT_PROMPT_SCORE_AXES_PATH,
            max_tokens=500,
        )
        pert_elapsed = time.perf_counter() - t0
        print(f"  -> PERT Fidelity: {pert_scored['scores'].get('fidelity')} ({pert_elapsed:.1f}s)", flush=True)

        pair_record = {
            "id": pid,
            "target_axis": "fidelity",
            "turn_id": tid,
            "speaker": speaker,
            "quote": orig_quote,
            "original_claim": orig_claim,
            "perturbed_claim": pert_claim,
            "perturbation_description": item.get("perturbation_description", ""),
            "original_scores": orig_scored["scores"],
            "original_reasons": orig_scored["reasons"],
            "original_parse_status": orig_scored["parse_status"],
            "perturbed_scores": pert_scored["scores"],
            "perturbed_reasons": pert_scored["reasons"],
            "perturbed_parse_status": pert_scored["parse_status"],
            "elapsed_seconds": round(orig_elapsed + pert_elapsed, 2),
        }
        scored_fidelity_results.append(pair_record)

    del extractor
    import gc
    gc.collect()

    all_scored_results = non_fid_results + scored_fidelity_results
    if len(all_scored_results) != 40:
        raise ValueError(f"Expected 40 total scored pairs, got {len(all_scored_results)}")

    evaluation = evaluate_perturbation_results(all_scored_results)

    # Compute separate real vs invented fidelity breakdown
    real_ids = {"fidelity_01", "fidelity_02", "fidelity_03"}
    inv_ids = {"fidelity_04", "fidelity_05"}

    real_pairs = [p for p in scored_fidelity_results if p["id"] in real_ids]
    inv_pairs = [p for p in scored_fidelity_results if p["id"] in inv_ids]

    def compute_subset_metrics(pairs: list[dict[str, Any]]) -> dict[str, Any]:
        target_drops = 0
        off_target_drops = 0
        off_target_comps = 0
        for p in pairs:
            o_s = p.get("original_scores", {})
            p_s = p.get("perturbed_scores", {})
            if (
                p_s.get("fidelity") is not None
                and o_s.get("fidelity") is not None
                and p_s["fidelity"] < o_s["fidelity"]
            ):
                target_drops += 1
            for ax in AXIS_NAMES:
                if ax == "fidelity":
                    continue
                if p_s.get(ax) is not None and o_s.get(ax) is not None:
                    off_target_comps += 1
                    if p_s[ax] < o_s[ax]:
                        off_target_drops += 1
        return {
            "total": len(pairs),
            "target_drops": target_drops,
            "sensitivity_pct": round(target_drops / len(pairs) * 100.0, 1) if pairs else 0.0,
            "off_target_drops": off_target_drops,
            "off_target_comparisons": off_target_comps,
            "off_target_drop_rate_pct": round(off_target_drops / off_target_comps * 100.0, 1) if off_target_comps else 0.0,
            "pairs": [p["id"] for p in pairs],
            "turn_ids": [p["turn_id"] for p in pairs],
        }

    real_metrics = compute_subset_metrics(real_pairs)
    inv_metrics = compute_subset_metrics(inv_pairs)

    fidelity_breakdown = {
        "scorer": "GLM-4-32B (Calibrated score_axes.md)",
        "real": real_metrics,
        "invented": inv_metrics,
    }

    final_artifact = {
        "model_id": "mlx-community/GLM-4-32B-0414-4bit",
        "prompt_template": "v2/prompts/score_axes.md",
        "fixture_path": "v2/fixtures/axes/perturbations.json",
        "fixture_sha256": fixture_sha256,
        "total_pairs": 40,
        "evaluation": evaluation,
        "fidelity_breakdown": fidelity_breakdown,
        "perturbation_results": all_scored_results,
    }

    out_file = DEFAULT_EXTRACTION_DIR / f"c9_perturbations_scored_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f_out:
        json.dump(final_artifact, f_out, indent=2)

    print(f"\nWrote C9 scored perturbations to {out_file}")
    print(f"Fixture SHA256: {fixture_sha256}")
    print(f"Real fidelity sensitivity: {real_metrics['sensitivity_pct']}% ({real_metrics['target_drops']}/{real_metrics['total']})")
    print(f"Invented fidelity sensitivity: {inv_metrics['sensitivity_pct']}% ({inv_metrics['target_drops']}/{inv_metrics['total']})")
    print(f"Overall fidelity sensitivity: {evaluation['axes']['fidelity']['target_sensitivity_rate_pct']}%")
    print(f"Overall fidelity off-target: {evaluation['axes']['fidelity']['off_target_drop_rate_pct']}%")

    return final_artifact


if __name__ == "__main__":
    run_c9_fidelity_scoring()
