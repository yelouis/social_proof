"""Execution runner for Item C4: Score every candidate on the eight axes, and report the episode.

Implements Pass 2 quality scoring:
1. Loads candidate claims from Pass 1 (Gemma-4-31B extracted 111 claims on E287).
2. Scores candidate claims across the 8 axes using independent model (GLM-4-32B-0414-4bit).
3. Generates the Episode Claim Quality Profile report (§4) separating Speaker and Extraction panels.
4. Reports mechanical proxy cross-checks (unresolved referents, compound claims, near-verbatim quotes).
5. Runs the Fidelity falsification swap test across 20 claims.
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
    DEFAULT_AXES_PATH,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PROMPT_SCORE_AXES_PATH,
    DEFAULT_TRANSCRIPT_DIR,
    ModelExtractor,
    build_score_axes_prompt,
    generate_episode_axes_report,
    load_axes,
    parse_axes_verdict,
)


def score_claims_list(
    claims: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    extractor: ModelExtractor,
    axes_text: str,
    output_checkpoint_path: Path | None = None,
    max_tokens: int = 500,
) -> list[dict[str, Any]]:
    """Scores a list of claims sequentially using the provided extractor, saving checkpoints."""
    scored_claims: list[dict[str, Any]] = []
    already_scored_ids: set[str] = set()

    # Load existing checkpoint if present
    if output_checkpoint_path and output_checkpoint_path.exists():
        try:
            with open(output_checkpoint_path, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            for sc in ckpt.get("scored_claims", []):
                if sc.get("parse_status") == "ok":
                    scored_claims.append(sc)
                    already_scored_ids.add(sc["turn_id"])
            if already_scored_ids:
                print(f"Resuming from checkpoint with {len(already_scored_ids)} already scored claims.", flush=True)
        except (json.JSONDecodeError, OSError, KeyError):
            scored_claims = []
            already_scored_ids = set()

    total = len(claims)
    for idx, c in enumerate(claims, start=1):
        tid = c["turn_id"]
        if tid in already_scored_ids:
            continue

        turn = turns_by_id.get(tid, {"turn_id": tid, "speaker_label": c.get("speaker", "unknown"), "text": ""})
        quote = c.get("quote", "")
        claim_text = c.get("claim", "")

        prompt = build_score_axes_prompt(
            axes_text=axes_text,
            target_turn=turn,
            quote=quote,
            claim=claim_text,
            template_path=DEFAULT_PROMPT_SCORE_AXES_PATH,
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

        scored_item = {
            "turn_id": tid,
            "speaker": c.get("speaker", turn.get("speaker_label", "unknown")),
            "quote": quote,
            "claim": claim_text,
            "parse_status": verdict["parse_status"],
            "scores": verdict["scores"],
            "reasons": verdict["reasons"],
            "raw_output": raw_output,
            "elapsed_seconds": round(elapsed, 2),
        }
        scored_claims.append(scored_item)

        scores_summary = " ".join(f"{k[0].upper()}:{v}" for k, v in verdict["scores"].items()) if verdict["scores"] else "UNPARSEABLE"
        print(f"[C4 SCORE] {idx:3d}/{total:3d} ({idx/total*100.0:.1f}%) turn {tid[-5:]} in {elapsed:.1f}s -> {scores_summary}", flush=True)

        # Checkpoint to disk
        if output_checkpoint_path:
            ckpt_data = {
                "checkpoint_time": time.time(),
                "scoring_model_id": extractor.model_id,
                "claims_scored": len(scored_claims),
                "total_claims": total,
                "scored_claims": scored_claims,
            }
            tmp_path = output_checkpoint_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(ckpt_data, f, indent=2)
            tmp_path.replace(output_checkpoint_path)

    return scored_claims


def run_c4_scoring(
    source_id: str = "00251a80c868f535",
    pass1_model_id: str = "mlx-community/gemma-4-31b-it-4bit",
    scoring_model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    output_dir: Path | None = None,
    max_claims: int | None = None,
) -> dict[str, Any]:
    """Runs Pass 2 axis scoring for all candidate claims of an episode."""
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"c4_scored_axes_{source_id}.json"
    ckpt_file = out_dir / f"c4_scored_axes_{source_id}_ckpt.json"

    # 1. Load Pass 1 claims
    pass1_file = out_dir / f"b6_extraction_{pass1_model_id.replace('/', '_')}_{source_id}.json"
    if not pass1_file.exists():
        raise FileNotFoundError(f"Pass 1 extraction artifact not found: {pass1_file}")

    with open(pass1_file, "r", encoding="utf-8") as f:
        pass1_data = json.load(f)

    all_verdicts = pass1_data.get("verdicts", [])
    claims = [v for v in all_verdicts if v.get("verdict") == "claim"]
    if max_claims is not None:
        claims = claims[:max_claims]

    print(f"\n=== C4 Pass 2 Scoring: {len(claims)} candidate claims on {source_id} ===")
    print(f"Extractor (Pass 1): {pass1_model_id}")
    print(f"Scorer (Pass 2):    {scoring_model_id}")

    # Assert independent scoring model
    assert scoring_model_id != pass1_model_id, (
        f"C4 Step 2 assertion failure: scoring_model_id ({scoring_model_id}) must differ from pass1_model_id ({pass1_model_id})."
    )

    # 2. Load transcript turns
    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        t_data = json.load(f)
    turns = t_data.get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    # 3. Load axes text
    axes_text = load_axes(DEFAULT_AXES_PATH)

    # 4. Load Scorer Extractor
    print(f"Loading scoring model {scoring_model_id} via MLX...")
    extractor = ModelExtractor(model_id=scoring_model_id, runtime="mlx_lm", temperature=0.0)

    # 5. Score claims
    t_start = time.perf_counter()
    scored_claims = score_claims_list(
        claims=claims,
        turns_by_id=turns_by_id,
        extractor=extractor,
        axes_text=axes_text,
        output_checkpoint_path=ckpt_file,
    )
    total_elapsed = time.perf_counter() - t_start

    # 6. Generate episode report
    report = generate_episode_axes_report(
        scored_claims=scored_claims,
        total_turns=len(turns),
        model_id=pass1_model_id,
        scoring_model_id=scoring_model_id,
        episode_id=source_id,
    )

    result = {
        "source_id": source_id,
        "model_id": pass1_model_id,
        "scoring_model_id": scoring_model_id,
        "elapsed_seconds": round(total_elapsed, 2),
        "total_claims_evaluated": len(claims),
        "report": report,
        "scored_claims": scored_claims,
    }

    # Save final artifact
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Clean up checkpoint
    if ckpt_file.exists():
        ckpt_file.unlink()

    print(f"\nCompleted C4 scoring in {total_elapsed:.1f}s. Saved to {out_file}.")
    return result


def run_c4_falsification_swap(
    source_id: str = "00251a80c868f535",
    gemma_model_id: str = "mlx-community/gemma-4-31b-it-4bit",
    glm_model_id: str = "mlx-community/GLM-4-32B-0414-4bit",
    sample_size: int = 20,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Runs C4 Falsification:
    Scores the same 20 claims twice with the two models swapped:
    - Gemma scoring what GLM extracted, and GLM scoring what Gemma extracted (or both scoring the same 20 claims).
    Measures movement in Fidelity scores across scorer swap.
    """
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_file = out_dir / f"c4_falsification_fidelity_swap_{source_id}.json"

    # Load 10 claims from Gemma and 10 claims from GLM to total 20 claims
    gemma_file = out_dir / f"b6_extraction_{gemma_model_id.replace('/', '_')}_{source_id}.json"
    glm_file = out_dir / f"b6_extraction_{glm_model_id.replace('/', '_')}_{source_id}.json"

    with open(gemma_file, "r", encoding="utf-8") as f:
        gemma_data = json.load(f)
    with open(glm_file, "r", encoding="utf-8") as f:
        glm_data = json.load(f)

    def extract_claim_items(verdicts: list[dict[str, Any]], extractor_label: str) -> list[dict[str, Any]]:
        res = []
        for v in verdicts:
            is_claim = v.get("model_verdict") == "claim" or v.get("verdict") == "claim"
            if is_claim:
                res.append({
                    "turn_id": v["turn_id"],
                    "speaker": v.get("speaker") or v.get("speaker_label", "unknown"),
                    "quote": v.get("model_quote") or v.get("quote", ""),
                    "claim": v.get("model_claim") or v.get("claim", ""),
                    "extractor_label": extractor_label,
                })
        return res

    gemma_claims = extract_claim_items(gemma_data.get("verdicts", []), "gemma")[:10]
    glm_claims = extract_claim_items(glm_data.get("verdicts", []), "glm")[:10]
    sample_claims = gemma_claims + glm_claims

    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    with open(transcript_file, "r", encoding="utf-8") as f:
        turns = json.load(f).get("turns", [])
    turns_by_id = {t["turn_id"]: t for t in turns}

    axes_text = load_axes(DEFAULT_AXES_PATH)

    print(f"\n=== Running C4 Falsification: 20 claims scored by both {glm_model_id} and {gemma_model_id} ===")
    print(f"Sample: {len(gemma_claims)} extracted by Gemma, {len(glm_claims)} extracted by GLM")

    # Check if GLM already scored the 10 Gemma claims in c4_scored_axes
    c4_scored_file = out_dir / f"c4_scored_axes_{source_id}.json"
    c4_scored_map: dict[str, dict[str, Any]] = {}
    if c4_scored_file.exists():
        with open(c4_scored_file, "r", encoding="utf-8") as f:
            c4_data = json.load(f)
        for sc in c4_data.get("scored_claims", []):
            c4_scored_map[sc["turn_id"]] = sc

    glm_claims_to_score: list[dict[str, Any]] = []
    already_glm_scored: dict[str, dict[str, Any]] = {}

    for c in sample_claims:
        tid = c["turn_id"]
        # Only reuse if it was Gemma's extraction (matching what was scored in c4)
        if c.get("extractor_label") == "gemma" and tid in c4_scored_map:
            already_glm_scored[tid] = c4_scored_map[tid]
        else:
            glm_claims_to_score.append(c)

    glm_ckpt = out_dir / f"c4_falsification_fidelity_swap_{source_id}_ckpt_glm.json"
    if glm_claims_to_score:
        print(f"Arm 1: Scoring {len(glm_claims_to_score)} claims with {glm_model_id} (reusing {len(already_glm_scored)} already scored)...")
        glm_extractor = ModelExtractor(model_id=glm_model_id, runtime="mlx_lm", temperature=0.0)
        new_glm_scored = score_claims_list(
            glm_claims_to_score,
            turns_by_id,
            glm_extractor,
            axes_text,
            output_checkpoint_path=glm_ckpt,
            max_tokens=500,
        )
        del glm_extractor
        import gc
        gc.collect()

        scored_by_glm_all = {sc["turn_id"]: sc for sc in list(already_glm_scored.values()) + new_glm_scored}
        glm_scored = [scored_by_glm_all[c["turn_id"]] for c in sample_claims]
    else:
        glm_scored = [already_glm_scored[c["turn_id"]] for c in sample_claims]

    if glm_ckpt.exists():
        glm_ckpt.unlink()

    print(f"Arm 2: Scoring 20 claims with {gemma_model_id}...")
    gemma_ckpt = out_dir / f"c4_falsification_fidelity_swap_{source_id}_ckpt_gemma.json"
    gemma_extractor = ModelExtractor(model_id=gemma_model_id, runtime="mlx_lm", temperature=0.0)
    gemma_scored = score_claims_list(
        sample_claims,
        turns_by_id,
        gemma_extractor,
        axes_text,
        output_checkpoint_path=gemma_ckpt,
        max_tokens=500,
    )
    del gemma_extractor
    import gc
    gc.collect()

    if gemma_ckpt.exists():
        gemma_ckpt.unlink()

    # Compare Fidelity scores
    comparisons: list[dict[str, Any]] = []
    fidelity_agreements = 0
    fidelity_deltas: list[int] = []

    for sc_glm, sc_gemma in zip(glm_scored, gemma_scored, strict=False):
        tid = sc_glm["turn_id"]
        f_glm = sc_glm["scores"].get("fidelity")
        f_gemma = sc_gemma["scores"].get("fidelity")
        if f_glm is not None and f_gemma is not None:
            delta = abs(f_glm - f_gemma)
            fidelity_deltas.append(delta)
            if delta == 0:
                fidelity_agreements += 1

        comparisons.append({
            "turn_id": tid,
            "quote": sc_glm["quote"],
            "claim": sc_glm["claim"],
            "glm_fidelity": f_glm,
            "glm_reason": sc_glm["reasons"].get("fidelity_reason"),
            "gemma_fidelity": f_gemma,
            "gemma_reason": sc_gemma["reasons"].get("fidelity_reason"),
            "fidelity_delta": abs(f_glm - f_gemma) if f_glm is not None and f_gemma is not None else None,
        })

    agreement_rate = fidelity_agreements / len(comparisons) if comparisons else 0.0
    mean_delta = sum(fidelity_deltas) / len(fidelity_deltas) if fidelity_deltas else 0.0

    result = {
        "source_id": source_id,
        "sample_size": len(comparisons),
        "models": [glm_model_id, gemma_model_id],
        "fidelity_agreement_count": fidelity_agreements,
        "fidelity_agreement_rate": round(agreement_rate, 4),
        "fidelity_agreement_rate_pct": round(agreement_rate * 100.0, 1),
        "fidelity_mean_abs_delta": round(mean_delta, 2),
        "comparisons": comparisons,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Falsification completed: Fidelity agreement = {fidelity_agreements}/{len(comparisons)} ({agreement_rate*100.0:.1f}%), mean delta = {mean_delta:.2f}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run C4 Pass 2 Quality Axis Scoring")
    parser.add_argument("--source-id", default="00251a80c868f535")
    parser.add_argument("--falsification", action="store_true", help="Run 20-claim swapped models falsification")
    parser.add_argument("--max-claims", type=int, default=None)
    args = parser.parse_args()

    os.environ.setdefault("HF_HOME", "/Volumes/Extreme SSD 1/hf")

    if args.falsification:
        run_c4_falsification_swap(source_id=args.source_id, sample_size=20)
    else:
        run_c4_scoring(source_id=args.source_id, max_claims=args.max_claims)
