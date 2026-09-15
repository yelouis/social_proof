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

    print(f"Saved consensus artifact to {out_file}")
    for rule_name in ("unanimous", "majority", "any_model"):
        r = consensus[rule_name]
        print(f"Rule [{rule_name:10s}]: Claims={r['claims_count']:3d} | Recall={r['recall_pct']:5.2f}% | Precision={r['precision_pct']:5.2f}% | TP={r['confusion_matrix']['tp']:2d}, FP={r['confusion_matrix']['fp']:3d}")

    print(f"Shared False Positives Count: {consensus['shared_false_positives_count']}")
    return consensus


def main() -> None:
    parser = argparse.ArgumentParser(description="B6 Multi-Model Extraction and Consensus Runner")
    parser.add_argument("--model", type=str, help="Model ID to run")
    parser.add_argument("--runtime", type=str, default="ollama", choices=["mlx_lm", "ollama"])
    parser.add_argument("--max-turns", type=int, default=None, help="Max turns to process")
    parser.add_argument("--consensus", nargs="+", help="Compute consensus across specified artifact files")
    parser.add_argument("--source-id", type=str, default="00251a80c868f535")
    args = parser.parse_args()

    if args.consensus:
        files = [Path(p) for p in args.consensus]
        compute_b6_consensus(files, source_id=args.source_id)
    elif args.model:
        run_single_model(args.model, args.runtime, source_id=args.source_id, max_turns=args.max_turns)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
