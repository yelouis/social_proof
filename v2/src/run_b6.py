"""Execution runner for Item B6: Three local models on the same episode.

Evaluates:
1. Local model extraction on E287 (00251a80c868f535) using byte-identical rubric prompt.
2. Supports MLX and Ollama runtimes.
3. Computes unanimous, majority, and any-model consensus rules against B2 gold set.
4. Generates consensus artifacts and disagreement analysis.
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
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_GOLD_DIR,
    DEFAULT_TRANSCRIPT_DIR,
    ModelExtractor,
    evaluate_consensus_against_gold,
    run_episode_extraction,
)


def progress_logger(current: int, total: int, verdict: dict[str, Any]) -> None:
    if current == 1 or current % 10 == 0 or current == total:
        v_type = verdict.get("verdict", "unknown")
        detail = verdict.get("type", "") if v_type == "claim" else verdict.get("gate_failed", "")
        print(f"[B6 EXTRACT] Turn {current:3d}/{total:3d} ({current/total*100.0:.1f}%) -> {v_type} ({detail})", flush=True)


def clean_model_name(model_id: str) -> str:
    return model_id.replace("/", "_").replace(":", "_").replace(".", "_")


def run_single_model(
    model_id: str,
    runtime: str,
    source_id: str = "00251a80c868f535",
    max_turns: int | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    print(f"\n=== Running B6 Extraction: {model_id} ({runtime}) on {source_id} ===")
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    out_filename = f"b6_extraction_{clean_model_name(model_id)}_{source_id}.json"

    extractor = ModelExtractor(model_id=model_id, runtime=runtime)

    t0 = time.perf_counter()
    result = run_episode_extraction(
        source_id=source_id,
        is_falsification=False,
        max_turns=max_turns,
        extractor=extractor,
        output_dir=out_dir,
        output_filename=out_filename,
        progress_callback=progress_logger,
    )
    elapsed = time.perf_counter() - t0
    turns_done = result["turns_processed"]
    print(f"Completed {turns_done} turns in {elapsed:.1f}s ({elapsed / turns_done:.2f}s/turn)")
    metrics = result.get("metrics", {})
    print(f"Metrics: Recall={metrics.get('recall_pct')}%, Precision={metrics.get('precision_pct')}%, Claims={metrics.get('model_claims_count')}")
    return result


def compute_b6_consensus(
    model_files: list[Path],
    source_id: str = "00251a80c868f535",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    print(f"\n=== Computing Consensus Across {len(model_files)} Models on {source_id} ===")
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR

    gold_path = DEFAULT_GOLD_DIR / f"{source_id}.json"
    transcript_path = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    with open(transcript_path, "r", encoding="utf-8") as f:
        turns = json.load(f)["turns"]

    model_verdicts: dict[str, list[dict[str, Any]]] = {}
    model_metadata: dict[str, dict[str, Any]] = {}

    for mf in model_files:
        with open(mf, "r", encoding="utf-8") as f:
            data = json.load(f)
        mid = data["model_id"]
        model_verdicts[mid] = data["verdicts"]
        model_metadata[mid] = {
            "runtime": data["runtime"],
            "quantisation": data["quantisation"],
            "prompt_content_hash": data["prompt_content_hash"],
            "rubric_commit": data["rubric_commit"],
            "elapsed_seconds": data["elapsed_seconds"],
            "metrics": data["metrics"],
        }

    consensus = evaluate_consensus_against_gold(model_verdicts, gold_data, turns)
    consensus["source_id"] = source_id
    consensus["model_metadata"] = model_metadata

    out_file = out_dir / f"b6_agreement_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(consensus, f, indent=2)

    for rule_name in ("unanimous", "majority", "any_model"):
        r = consensus[rule_name]
        n = r["claims_count"]
        if n < 20:
            r["report_as"] = "count"
            r["precision_pct"] = None
        else:
            r["report_as"] = "percentage"
        prec_str = f"{r['precision_pct']:5.2f}%" if r.get("precision_pct") is not None else "N/A (count)"
        print(f"Rule [{rule_name:10s}]: Claims={r['claims_count']:3d} (report_as={r['report_as']}) | Recall={r['recall_pct']:5.2f}% | Precision={prec_str} | TP={r['confusion_matrix']['tp']:2d}, FP={r['confusion_matrix']['fp']:3d}")

    out_file = out_dir / f"b6_agreement_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(consensus, f, indent=2)

    print(f"Saved consensus artifact to {out_file}")
    print(f"Shared False Positives Count: {consensus['shared_false_positives_count']}")
    return consensus


def run_b6_self_agreement(
    model_id: str,
    runtime: str = "mlx_lm",
    source_id: str = "00251a80c868f535",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    print(f"\n=== Running B6 Self-Agreement: {model_id} ({runtime}) on {source_id} (gold_claim_turns) ===")
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    gold_path = DEFAULT_GOLD_DIR / f"{source_id}.json"
    transcript_path = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    with open(transcript_path, "r", encoding="utf-8") as f:
        all_turns = json.load(f)["turns"]

    from v2.src.extract import DEFAULT_RUBRIC_PATH, build_rubric_prompt, load_rubric
    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)

    gold_claim_tids = {
        v["turn_id"] for v in gold_data["verdicts"] if v.get("verdict") == "claim"
    }
    claim_turns = [t for t in all_turns if t["turn_id"] in gold_claim_tids]
    turn_by_id = {t["turn_id"]: t for t in all_turns}
    turn_ids = [t["turn_id"] for t in all_turns]

    def run_population(extractor: ModelExtractor, run_label: str) -> list[dict[str, Any]]:
        verdicts = []
        for idx, target in enumerate(claim_turns):
            tid = target["turn_id"]
            turn_idx = turn_ids.index(tid)
            context = turn_by_id[turn_ids[turn_idx - 1]] if turn_idx > 0 else None
            prompt = build_rubric_prompt(rubric_text, target, context)
            v = extractor.extract_turn(prompt, target, context)
            verdicts.append(v)
            if (idx + 1) % 10 == 0 or (idx + 1) == len(claim_turns):
                print(f"[{run_label}] Turn {idx + 1:2d}/{len(claim_turns)}: {v.get('verdict')}", flush=True)
        return verdicts

    print(f"Running pass 1 for {len(claim_turns)} gold claim turns (temp=0.7, seed=42)...")
    ext1 = ModelExtractor(model_id=model_id, runtime=runtime, temperature=0.7, seed=42)
    verdicts1 = run_population(ext1, "PASS 1")

    print(f"Running pass 2 for {len(claim_turns)} gold claim turns (temp=0.7, seed=999)...")
    ext2 = ModelExtractor(model_id=model_id, runtime=runtime, temperature=0.7, seed=999)
    verdicts2 = run_population(ext2, "PASS 2")

    n_total = len(claim_turns)
    agreed_overall = sum(
        1 for v1, v2 in zip(verdicts1, verdicts2, strict=False)
        if v1.get("verdict") == v2.get("verdict")
    )
    agreement_overall = round(agreed_overall / n_total * 100.0, 2) if n_total > 0 else 100.0

    claim_indices = [
        i for i, (v1, v2) in enumerate(zip(verdicts1, verdicts2, strict=False))
        if v1.get("verdict") == "claim" or v2.get("verdict") == "claim"
    ]
    claim_bearing_turns_n = len(claim_indices)
    if claim_bearing_turns_n > 0:
        claim_agreed = sum(
            1 for i in claim_indices
            if verdicts1[i].get("verdict") == verdicts2[i].get("verdict")
        )
        agreement_on_claim_bearing = round(claim_agreed / claim_bearing_turns_n * 100.0, 2)
    else:
        claim_agreed = 0
        agreement_on_claim_bearing = 100.0

    res = {
        "source_id": source_id,
        "model_id": model_id,
        "runtime": runtime,
        "temperature": 0.7,
        "population": "gold_claim_turns",
        "total_turns": n_total,
        "agreement_overall": agreement_overall,
        "agreement_overall_count": f"{agreed_overall}/{n_total}",
        "claim_bearing_turns_n": claim_bearing_turns_n,
        "agreement_on_claim_bearing_turns": agreement_on_claim_bearing,
        "agreement_on_claim_bearing_count": f"{claim_agreed}/{claim_bearing_turns_n}",
        "run1_verdicts": verdicts1,
        "run2_verdicts": verdicts2,
    }
    out_file = out_dir / f"b6_self_agreement_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"Saved self-agreement artifact to {out_file}")
    print(f"Self-Agreement: overall={agreement_overall}% ({agreed_overall}/{n_total}), on claim-bearing={agreement_on_claim_bearing}% ({claim_agreed}/{claim_bearing_turns_n})")
    return res


SPECIFIED_MODELS = [
    "mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit",
    "mlx-community/GLM-4-32B-0414-4bit",
    "mlx-community/gemma-4-31b-it-4bit",
]


def run_all_b6(source_id: str = "00251a80c868f535", output_dir: Path | None = None) -> None:
    print("\n============================================================")
    print("Running B6 Re-Run (Issue 043 = A) for All 3 Specified Models")
    print("============================================================")
    out_dir = output_dir or DEFAULT_EXTRACTION_DIR
    artifact_files: list[Path] = []

    for model_id in SPECIFIED_MODELS:
        run_single_model(model_id, runtime="mlx_lm", source_id=source_id, output_dir=out_dir)
        fname = f"b6_extraction_{clean_model_name(model_id)}_{source_id}.json"
        artifact_files.append(out_dir / fname)

    print("\nComputing consensus across all three arms...")
    compute_b6_consensus(artifact_files, source_id=source_id, output_dir=out_dir)

    print("\nRunning self-agreement falsification (GLM-4-32B on gold_claim_turns)...")
    run_b6_self_agreement("mlx-community/GLM-4-32B-0414-4bit", runtime="mlx_lm", source_id=source_id, output_dir=out_dir)
    print("\nAll B6 models and artifacts successfully completed!")


def main() -> None:
    parser = argparse.ArgumentParser(description="B6 Multi-Model Extraction and Consensus Runner")
    parser.add_argument("--all", action="store_true", help="Run all 3 specified models and compute consensus")
    parser.add_argument("--model", type=str, help="Model ID to run")
    parser.add_argument("--runtime", type=str, default="mlx_lm", choices=["mlx_lm", "ollama"])
    parser.add_argument("--max-turns", type=int, default=None, help="Max turns to process")
    parser.add_argument("--consensus", nargs="+", help="Compute consensus across specified artifact files")
    parser.add_argument("--self-agreement", type=str, help="Run self-agreement on gold claim turns for given model")
    parser.add_argument("--source-id", type=str, default="00251a80c868f535")
    args = parser.parse_args()

    if args.all:
        run_all_b6(source_id=args.source_id)
    elif args.consensus:
        files = [Path(p) for p in args.consensus]
        compute_b6_consensus(files, source_id=args.source_id)
    elif args.self_agreement:
        run_b6_self_agreement(args.self_agreement, args.runtime, source_id=args.source_id)
    elif args.model:
        run_single_model(args.model, args.runtime, source_id=args.source_id, max_turns=args.max_turns)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
