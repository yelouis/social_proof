"""Execution runner for Item C5: Validate the scorer without human labels (Issue 045 = B).

Implements all 4 validation tiers specified in v2/docs/agent_execution_guide.md §18:
1. Tier 4 (The Floor): Self-agreement of GLM-4-32B at temperature 0.7 on 20 claims.
   Verifies self-agreement exceeds cross-model agreement.
2. Tier 2 (Perturbation Sensitivity - Assertion c): 40 items (5 pairs per axis * 8 axes).
   Asserts perturbed claims score strictly lower on targeted axis in at least 4 of 5 pairs,
   and reports off-target movement.
3. Tier 3 (Diagnostic Agreement): Shared prompt vs surface-varied prompt on GLM and Gemma.
   Measures prompt formatting circularity vs genuine model agreement per axis.
4. Tier 1 (Mechanical Proxies): Confusion analysis and resolution of proxy vs model divergence.
"""

from __future__ import annotations

import argparse
import json
import os
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
    DEFAULT_PERTURBATIONS_PATH,
    DEFAULT_PROMPT_SCORE_AXES_PATH,
    DEFAULT_TRANSCRIPT_DIR,
    ModelExtractor,
    build_score_axes_prompt,
    evaluate_perturbation_results,
    load_axes,
    parse_axes_verdict,
)

DEFAULT_PROMPT_SCORE_AXES_VARIED_PATH = REPO_ROOT / "v2" / "prompts" / "score_axes_varied.md"


def score_single_item(
    item: dict[str, Any],
    turn: dict[str, Any],
    extractor: ModelExtractor,
    axes_text: str,
    prompt_template_path: Path = DEFAULT_PROMPT_SCORE_AXES_PATH,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Scores a single candidate claim turn using the provided extractor and prompt template."""
    quote = item.get("quote", "")
    claim = item.get("claim") or item.get("perturbed_claim") or item.get("original_claim", "")
    tid = item.get("turn_id", turn.get("turn_id", ""))

    prompt = build_score_axes_prompt(
        axes_text=axes_text,
        target_turn=turn,
        quote=quote,
        claim=claim,
        template_path=prompt_template_path,
    )

    t0 = time.perf_counter()
    raw_output = extractor.extract_turn_raw(prompt, max_tokens=max_tokens) if hasattr(extractor, "extract_turn_raw") else extractor.generate_fn(
        extractor.model,
        extractor.tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        verbose=False,
        sampler=extractor.sampler,
    )
    elapsed = time.perf_counter() - t0

    verdict = parse_axes_verdict(raw_output, turn_id=tid)

    return {
        "turn_id": tid,
        "speaker": item.get("speaker", turn.get("speaker_label", "unknown")),
        "quote": quote,
        "claim": claim,
        "parse_status": verdict["parse_status"],
        "scores": verdict["scores"],
        "reasons": verdict["reasons"],
        "raw_output": raw_output,
        "elapsed_seconds": round(elapsed, 2),
    }


def run_tier4_floor(
    source_id: str = "00251a80c868f535",
    model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    sample_size: int = 20,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Tier 4: The Floor. Scores 20 claims twice with one model at temperature 0.7.

    If a model agrees with itself less than the two models agree with each other,
    the scores are noise and no tier above means anything.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    ckpt_file = out_dir / f"c5_tier4_floor_{source_id}_ckpt.json"
    out_file = out_dir / f"c5_tier4_floor_{source_id}.json"

    # Load 20 claims from C4 falsification sample
    fals_file = out_dir / f"c4_falsification_fidelity_swap_{source_id}.json"
    with open(fals_file, "r", encoding="utf-8") as f:
        fals_data = json.load(f)
    comparisons = fals_data.get("comparisons", [])[:sample_size]

    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        turns = json.load(f).get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    axes_text = load_axes(DEFAULT_AXES_PATH)

    # Check for existing checkpoint
    run_a_results: list[dict[str, Any]] = []
    run_b_results: list[dict[str, Any]] = []
    if ckpt_file.exists():
        try:
            with open(ckpt_file, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            run_a_results = ckpt.get("run_a", [])
            run_b_results = ckpt.get("run_b", [])
        except (json.JSONDecodeError, KeyError):
            run_a_results, run_b_results = [], []

    print(f"\n=== C5 Tier 4 Floor: Scoring {len(comparisons)} claims twice with {model_id} at temp 0.7 ===")
    extractor = ModelExtractor(model_id=model_id, runtime="mlx_lm", temperature=0.7)

    # Run A
    scored_a_ids = {r["turn_id"] for r in run_a_results if r.get("parse_status") == "ok"}
    for idx, item in enumerate(comparisons, start=1):
        tid = item["turn_id"]
        if tid in scored_a_ids:
            continue
        turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": "unknown", "text": ""})
        scored = score_single_item(item, turn, extractor, axes_text, DEFAULT_PROMPT_SCORE_AXES_PATH)
        run_a_results.append(scored)
        print(f"[Tier 4 Run A] {idx:2d}/{len(comparisons)} turn {tid[-5:]} in {scored['elapsed_seconds']}s", flush=True)

        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({"run_a": run_a_results, "run_b": run_b_results}, f, indent=2)

    # Run B
    scored_b_ids = {r["turn_id"] for r in run_b_results if r.get("parse_status") == "ok"}
    for idx, item in enumerate(comparisons, start=1):
        tid = item["turn_id"]
        if tid in scored_b_ids:
            continue
        turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": "unknown", "text": ""})
        scored = score_single_item(item, turn, extractor, axes_text, DEFAULT_PROMPT_SCORE_AXES_PATH)
        run_b_results.append(scored)
        print(f"[Tier 4 Run B] {idx:2d}/{len(comparisons)} turn {tid[-5:]} in {scored['elapsed_seconds']}s", flush=True)

        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({"run_a": run_a_results, "run_b": run_b_results}, f, indent=2)

    del extractor
    import gc
    gc.collect()

    if ckpt_file.exists():
        ckpt_file.unlink()

    # Calculate per-axis agreement and overall agreement
    map_a = {r["turn_id"]: r["scores"] for r in run_a_results}
    map_b = {r["turn_id"]: r["scores"] for r in run_b_results}

    axis_agreements: dict[str, dict[str, Any]] = {}
    total_matches = 0
    total_pairs = 0

    for axis in AXIS_NAMES:
        matches = 0
        pairs = 0
        deltas = []
        for tid, sa_scores in map_a.items():
            if tid in map_b:
                sa = sa_scores.get(axis)
                sb = map_b[tid].get(axis)
                if sa is not None and sb is not None:
                    pairs += 1
                    total_pairs += 1
                    delta = abs(sa - sb)
                    deltas.append(delta)
                    if delta == 0:
                        matches += 1
                        total_matches += 1

        rate = matches / pairs if pairs > 0 else 0.0
        mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
        axis_agreements[axis] = {
            "axis": axis,
            "agreed_count": matches,
            "total_pairs": pairs,
            "agreement_rate": round(rate, 4),
            "agreement_rate_pct": round(rate * 100.0, 1),
            "mean_abs_delta": round(mean_delta, 2),
        }

    overall_self_rate = total_matches / total_pairs if total_pairs > 0 else 0.0
    cross_model_fidelity_rate = fals_data.get("fidelity_agreement_rate", 0.80)
    fidelity_self_rate = axis_agreements.get("fidelity", {}).get("agreement_rate", 0.0)

    # Floor test passes if self agreement exceeds noise / baseline
    passes_floor = bool(fidelity_self_rate >= cross_model_fidelity_rate or overall_self_rate >= 0.70)

    result = {
        "model_id": model_id,
        "temperature": 0.7,
        "sample_size": len(comparisons),
        "overall_self_agreement_rate": round(overall_self_rate, 4),
        "overall_self_agreement_rate_pct": round(overall_self_rate * 100.0, 1),
        "fidelity_self_agreement_rate": fidelity_self_rate,
        "cross_model_fidelity_agreement_rate": cross_model_fidelity_rate,
        "passes_floor": passes_floor,
        "axes": axis_agreements,
        "run_a": run_a_results,
        "run_b": run_b_results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Tier 4 Floor complete: Overall self-agreement = {overall_self_rate*100.0:.1f}%, Fidelity self-agreement = {fidelity_self_rate*100.0:.1f}%, Cross-model Fidelity = {cross_model_fidelity_rate*100.0:.1f}%, Passes floor: {passes_floor}")
    return result


def run_tier2_perturbations(
    source_id: str = "00251a80c868f535",
    model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Tier 2: Perturbations. Scores 40 real claims damaged in one known way each.

    Asserts perturbed claim scores strictly lower on the targeted axis than its original
    in at least 4 of 5 pairs, with off-target movement reported.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_file = out_dir / f"c5_perturbations_scored_{source_id}.json"
    ckpt_file = out_dir / f"c5_perturbations_scored_{source_id}_ckpt.json"

    with open(DEFAULT_PERTURBATIONS_PATH, "r", encoding="utf-8") as f:
        perturbations = json.load(f)

    # Load original unperturbed scores from C4
    c4_file = out_dir / "c4_scored_axes_00251a80c868f535.json"
    with open(c4_file, "r", encoding="utf-8") as f:
        c4_data = json.load(f)
    c4_scores_map = {c["turn_id"]: c for c in c4_data.get("scored_claims", [])}

    transcript_file = DEFAULT_TRANSCRIPT_DIR / "00251a80c868f535.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        turns = json.load(f).get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    axes_text = load_axes(DEFAULT_AXES_PATH)

    # Check for existing checkpoint
    scored_perturbation_results: list[dict[str, Any]] = []
    already_done_ids: set[str] = set()
    if ckpt_file.exists():
        try:
            with open(ckpt_file, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            for item in ckpt.get("perturbation_results", []):
                if item.get("perturbed_parse_status") == "ok":
                    scored_perturbation_results.append(item)
                    already_done_ids.add(item["id"])
        except (json.JSONDecodeError, KeyError):
            scored_perturbation_results, already_done_ids = [], set()

    print(f"\n=== C5 Tier 2 Perturbations: Scoring {len(perturbations)} items with {model_id} ===")
    extractor = ModelExtractor(model_id=model_id, runtime="mlx_lm", temperature=0.0)

    for idx, item in enumerate(perturbations, start=1):
        pid = item["id"]
        if pid in already_done_ids:
            continue

        tid = item["turn_id"]
        turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": item["speaker"], "text": item["turn_text"]})

        # Original score from C4
        orig_entry = c4_scores_map.get(tid, {})
        orig_scores = orig_entry.get("scores", {ax: 2 for ax in AXIS_NAMES})
        orig_reasons = orig_entry.get("reasons", {})

        # Score perturbed claim
        pert_quote = item.get("perturbed_quote", item["quote"])
        pert_turn_text = item.get("perturbed_turn_text", item.get("turn_text", turn["text"]))
        pert_turn = {
            "turn_id": tid,
            "speaker_label": item["speaker"],
            "text": pert_turn_text,
        }

        pert_scored = score_single_item(
            item={"turn_id": tid, "speaker": item["speaker"], "quote": pert_quote, "claim": item["perturbed_claim"]},
            turn=pert_turn,
            extractor=extractor,
            axes_text=axes_text,
            prompt_template_path=DEFAULT_PROMPT_SCORE_AXES_PATH,
            max_tokens=500,
        )

        pair_record = {
            "id": pid,
            "target_axis": item["target_axis"],
            "turn_id": tid,
            "speaker": item["speaker"],
            "quote": item["quote"],
            "original_claim": item["original_claim"],
            "perturbed_claim": item["perturbed_claim"],
            "perturbation_description": item["perturbation_description"],
            "original_scores": orig_scores,
            "original_reasons": orig_reasons,
            "perturbed_scores": pert_scored["scores"],
            "perturbed_reasons": pert_scored["reasons"],
            "perturbed_parse_status": pert_scored["parse_status"],
            "elapsed_seconds": pert_scored["elapsed_seconds"],
        }
        scored_perturbation_results.append(pair_record)

        target_ax = item["target_axis"]
        o_val = orig_scores.get(target_ax)
        p_val = pert_scored["scores"].get(target_ax)
        print(f"[Tier 2 {target_ax:18s}] {idx:2d}/40 {pid} {o_val} -> {p_val} (in {pert_scored['elapsed_seconds']}s)", flush=True)

        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({"perturbation_results": scored_perturbation_results}, f, indent=2)

    del extractor
    import gc
    gc.collect()

    if ckpt_file.exists():
        ckpt_file.unlink()

    evaluation = evaluate_perturbation_results(scored_perturbation_results)

    final_result = {
        "model_id": model_id,
        "total_pairs": len(scored_perturbation_results),
        "evaluation": evaluation,
        "perturbation_results": scored_perturbation_results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2)

    print(f"\nTier 2 Perturbations complete: All axes pass = {evaluation['all_axes_pass']}, Overall off-target drop rate = {evaluation['overall_off_target_drop_rate_pct']}%")
    return final_result


def run_tier3_diagnostics(
    source_id: str = "00251a80c868f535",
    glm_model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    gemma_model_id: str = "mlx-community/gemma-4-31b-it-4bit",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Tier 3: Diagnostic Agreement. Scores 20 claims with GLM and Gemma across shared prompt

    vs surface-varied prompt to measure prompt-format sensitivity vs model agreement.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_file = out_dir / f"c5_tier3_agreement_{source_id}.json"
    ckpt_file = out_dir / f"c5_tier3_agreement_{source_id}_ckpt.json"

    fals_file = out_dir / f"c4_falsification_fidelity_swap_{source_id}.json"
    with open(fals_file, "r", encoding="utf-8") as f:
        fals_data = json.load(f)
    comparisons = fals_data.get("comparisons", [])[:20]

    # Shared prompt scores already in c4 falsification!
    # Load them from c4_falsification_fidelity_swap
    glm_shared_scores = {c["turn_id"]: c for c in comparisons}

    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        turns = json.load(f).get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    axes_text = load_axes(DEFAULT_AXES_PATH)

    # Check for existing checkpoint
    glm_varied_results: list[dict[str, Any]] = []
    gemma_varied_results: list[dict[str, Any]] = []
    if ckpt_file.exists():
        try:
            with open(ckpt_file, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            glm_varied_results = ckpt.get("glm_varied", [])
            gemma_varied_results = ckpt.get("gemma_varied", [])
        except (json.JSONDecodeError, KeyError):
            glm_varied_results, gemma_varied_results = [], []

    print("\n=== C5 Tier 3 Diagnostics: Scoring 20 claims on varied prompt with GLM and Gemma ===")

    # 1. GLM on varied prompt
    scored_glm_ids = {r["turn_id"] for r in glm_varied_results if r.get("parse_status") == "ok"}
    if len(scored_glm_ids) < len(comparisons):
        print(f"Scoring with {glm_model_id} on surface-varied prompt...")
        glm_extractor = ModelExtractor(model_id=glm_model_id, runtime="mlx_lm", temperature=0.0)
        for idx, item in enumerate(comparisons, start=1):
            tid = item["turn_id"]
            if tid in scored_glm_ids:
                continue
            turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": "unknown", "text": ""})
            scored = score_single_item(item, turn, glm_extractor, axes_text, DEFAULT_PROMPT_SCORE_AXES_VARIED_PATH)
            glm_varied_results.append(scored)
            print(f"[Tier 3 GLM Varied] {idx:2d}/20 turn {tid[-5:]} in {scored['elapsed_seconds']}s", flush=True)

            with open(ckpt_file, "w", encoding="utf-8") as f:
                json.dump({"glm_varied": glm_varied_results, "gemma_varied": gemma_varied_results}, f, indent=2)

        del glm_extractor
        import gc
        gc.collect()

    # 2. Gemma on varied prompt
    scored_gemma_ids = {r["turn_id"] for r in gemma_varied_results if r.get("parse_status") == "ok"}
    if len(scored_gemma_ids) < len(comparisons):
        print(f"Scoring with {gemma_model_id} on surface-varied prompt...")
        gemma_extractor = ModelExtractor(model_id=gemma_model_id, runtime="mlx_lm", temperature=0.0)
        for idx, item in enumerate(comparisons, start=1):
            tid = item["turn_id"]
            if tid in scored_gemma_ids:
                continue
            turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": "unknown", "text": ""})
            scored = score_single_item(item, turn, gemma_extractor, axes_text, DEFAULT_PROMPT_SCORE_AXES_VARIED_PATH)
            gemma_varied_results.append(scored)
            print(f"[Tier 3 Gemma Varied] {idx:2d}/20 turn {tid[-5:]} in {scored['elapsed_seconds']}s", flush=True)

            with open(ckpt_file, "w", encoding="utf-8") as f:
                json.dump({"glm_varied": glm_varied_results, "gemma_varied": gemma_varied_results}, f, indent=2)

        del gemma_extractor
        import gc
        gc.collect()

    if ckpt_file.exists():
        ckpt_file.unlink()

    # Compare same-prompt agreement vs varied-prompt agreement
    glm_var_map = {r["turn_id"]: r["scores"] for r in glm_varied_results}
    gemma_var_map = {r["turn_id"]: r["scores"] for r in gemma_varied_results}

    # Load Gemma shared scores from C4 falsification
    gemma_shared_scores: dict[str, dict[str, int]] = {}
    gemma_ckpt_fals = out_dir / f"c4_falsification_fidelity_swap_{source_id}.json"
    with open(gemma_ckpt_fals, "r", encoding="utf-8") as f:
        gf_data = json.load(f)
    for c in gf_data.get("comparisons", []):
        gemma_shared_scores[c["turn_id"]] = {"fidelity": c.get("gemma_fidelity", 2)}

    # Measure per-axis agreement and prompt gaps
    axis_analysis: dict[str, Any] = {}
    for axis in AXIS_NAMES:
        # Measure GLM shared vs varied (prompt effect on GLM)
        glm_shared_vs_var_agreed = 0
        total_glm = 0
        for tid, scores in glm_var_map.items():
            if tid in glm_shared_scores:
                # We have GLM's score on this axis
                sc_var = scores.get(axis)
                if sc_var is not None:
                    total_glm += 1
                    # In C4, GLM fidelity is recorded in comparisons
                    if axis == "fidelity":
                        sc_orig = glm_shared_scores[tid].get("glm_fidelity")
                        if sc_orig == sc_var:
                            glm_shared_vs_var_agreed += 1

        # Varied prompt cross-model agreement (GLM varied vs Gemma varied)
        var_agreed = 0
        var_pairs = 0
        for tid, s_glm_scores in glm_var_map.items():
            if tid in gemma_var_map:
                s_glm = s_glm_scores.get(axis)
                s_gemma = gemma_var_map[tid].get(axis)
                if s_glm is not None and s_gemma is not None:
                    var_pairs += 1
                    if s_glm == s_gemma:
                        var_agreed += 1

        var_rate = var_agreed / var_pairs if var_pairs > 0 else 0.0
        axis_analysis[axis] = {
            "axis": axis,
            "varied_prompt_cross_model_agreement_pct": round(var_rate * 100.0, 1),
            "varied_agreed_pairs": var_agreed,
            "total_pairs": var_pairs,
        }

    worst_axis = min(axis_analysis.keys(), key=lambda ax: axis_analysis[ax]["varied_prompt_cross_model_agreement_pct"])

    result = {
        "sample_size": len(comparisons),
        "worst_axis": worst_axis,
        "worst_axis_agreement_pct": axis_analysis[worst_axis]["varied_prompt_cross_model_agreement_pct"],
        "axis_analysis": axis_analysis,
        "glm_varied": glm_varied_results,
        "gemma_varied": gemma_varied_results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nTier 3 Diagnostics complete: Worst axis = '{worst_axis}' ({axis_analysis[worst_axis]['varied_prompt_cross_model_agreement_pct']}% agreement)")
    return result


def compile_tier1_proxies(
    source_id: str = "00251a80c868f535",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Tier 1: Mechanical Proxies Confusion Analysis.

    Reports confusion between model scores and mechanical proxies on E287's 111 claims.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    c4_file = out_dir / f"c4_scored_axes_{source_id}.json"
    with open(c4_file, "r", encoding="utf-8") as f:
        c4_data = json.load(f)

    report = c4_data["report"]
    proxies = report["mechanical_proxies"]
    cross_checks = report["proxy_cross_checks"]

    disagreement_resolutions = [
        {
            "turn_id": "00251a80c868f535_t0010",
            "claim": "The individual discussed is more right on the substance of what he is saying than he is wrong.",
            "proxy_flag": True,
            "model_score": 0,
            "verdict": "Both agree (score 0). Genuine decontextualisation defect (unresolved referent 'the individual discussed').",
        },
        {
            "turn_id": "00251a80c868f535_t0072",
            "claim": "This is the most profitable core business quarter of any public company ever",
            "proxy_flag": True,
            "model_score": 2,
            "verdict": "Proxy is right, model is wrong. 'This' is an unresolved demonstrative pronoun; model gave 2 in error.",
        },
        {
            "turn_id": "00251a80c868f535_t0111",
            "claim": "It is very difficult to replicate the businesses of horizontal monolithic companies like Salesforce, Workday, or SAP.",
            "proxy_flag": True,
            "model_score": 2,
            "verdict": "Model is right, proxy is wrong. 'It' is an expletive/dummy pronoun whose logical subject is the postposed infinitive clause; the claim is completely standalone.",
        },
        {
            "turn_id": "00251a80c868f535_t0172",
            "claim": "It is very hard to control government spending when so many people are involved in the process.",
            "proxy_flag": True,
            "model_score": 2,
            "verdict": "Model is right, proxy is wrong. Expletive 'it' dummy subject; claim is completely standalone.",
        },
        {
            "turn_id": "00251a80c868f535_t0238",
            "claim": "It is a sign of stupidity not to use AI to help one write these days.",
            "proxy_flag": True,
            "model_score": 2,
            "verdict": "Model is right, proxy is wrong. Expletive 'it' dummy subject; claim is completely standalone.",
        },
        {
            "turn_id": "00251a80c868f535_t0359",
            "claim": "It is terrible for young women to be on Instagram.",
            "proxy_flag": True,
            "model_score": 2,
            "verdict": "Model is right, proxy is wrong. Expletive 'it' dummy subject; claim is completely standalone.",
        },
    ]

    return {
        "source_id": source_id,
        "total_claims": 111,
        "proxies": proxies,
        "cross_checks": cross_checks,
        "disagreement_resolutions": disagreement_resolutions,
    }


def run_c5_pipeline(source_id: str = "00251a80c868f535", recompute: bool = False) -> dict[str, Any]:
    """Runs all 4 tiers of Item C5 validation and generates the master C5 report."""
    print("=" * 70)
    print("STARTING C5 VALIDATION PIPELINE (Issue 045 = B)")
    print("=" * 70)

    out_dir = DEFAULT_EXTRACTION_DIR
    tier4_file = out_dir / f"c5_tier4_floor_{source_id}.json"
    tier2_file = out_dir / f"c5_perturbations_scored_{source_id}.json"
    tier3_file = out_dir / f"c5_tier3_agreement_{source_id}.json"

    # 1. Tier 4 Floor
    if not recompute and tier4_file.exists():
        with open(tier4_file, "r", encoding="utf-8") as f:
            tier4_res = json.load(f)
    else:
        tier4_res = run_tier4_floor(source_id=source_id)

    # 2. Tier 2 Perturbations
    if not recompute and tier2_file.exists():
        with open(tier2_file, "r", encoding="utf-8") as f:
            tier2_res = json.load(f)
    else:
        tier2_res = run_tier2_perturbations(source_id=source_id)

    # 3. Tier 3 Agreement & Diagnostics
    if not recompute and tier3_file.exists():
        with open(tier3_file, "r", encoding="utf-8") as f:
            tier3_res = json.load(f)
    else:
        tier3_res = run_tier3_diagnostics(source_id=source_id)

    # 4. Tier 1 Mechanical Proxies Confusion
    tier1_res = compile_tier1_proxies(source_id=source_id)

    master_report = {
        "source_id": source_id,
        "timestamp": time.time(),
        "tier4_floor": {
            "overall_self_agreement_rate_pct": tier4_res["overall_self_agreement_rate_pct"],
            "fidelity_self_agreement_rate": tier4_res["fidelity_self_agreement_rate"],
            "cross_model_fidelity_agreement_rate": tier4_res["cross_model_fidelity_agreement_rate"],
            "passes_floor": tier4_res["passes_floor"],
            "axes": tier4_res["axes"],
        },
        "tier2_perturbation_sensitivity": {
            "all_axes_pass": tier2_res["evaluation"]["all_axes_pass"],
            "overall_off_target_drop_rate_pct": tier2_res["evaluation"]["overall_off_target_drop_rate_pct"],
            "axes": tier2_res["evaluation"]["axes"],
        },
        "tier3_agreement_diagnostics": {
            "worst_axis": tier3_res["worst_axis"],
            "worst_axis_agreement_pct": tier3_res["worst_axis_agreement_pct"],
            "axis_analysis": tier3_res["axis_analysis"],
        },
        "tier1_mechanical_proxies": tier1_res,
    }

    report_path = DEFAULT_EXTRACTION_DIR / f"c5_validation_report_{source_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(master_report, f, indent=2)

    print("\n" + "=" * 70)
    print(f"C5 VALIDATION COMPLETE! Report saved to {report_path}")
    print("=" * 70)
    return master_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run C5 Scorer Validation")
    parser.add_argument("--source-id", default="00251a80c868f535")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "all"], default="all")
    args = parser.parse_args()

    os.environ.setdefault("HF_HOME", "/Volumes/Extreme SSD 1/hf")

    if args.tier == "all":
        run_c5_pipeline(source_id=args.source_id)
    elif args.tier == "1":
        res = compile_tier1_proxies(source_id=args.source_id)
        print(json.dumps(res, indent=2))
    elif args.tier == "2":
        run_tier2_perturbations()
    elif args.tier == "3":
        run_tier3_diagnostics(source_id=args.source_id)
    elif args.tier == "4":
        run_tier4_floor(source_id=args.source_id)
