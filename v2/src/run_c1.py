"""Execution driver for C1: Run extraction on E287 with the positive rubric and prompts.

Evaluates:
1. Full 405-turn extraction with positive rubric on All-In E287 (00251a80c868f535).
2. Comparison against B3 baseline (old rubric: 0 claims) and stripped control (393 claims).
3. Gate distribution comparison against B2 human gold standard.
4. Updates v2/artifacts/extraction/README.md.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v2.src.extract import (
    DEFAULT_EXTRACTION_DIR,
    MODEL_ID,
    VALIDATORS_ADDED,
    run_episode_extraction,
)


def progress_logger(current: int, total: int, verdict: dict):
    if current == 1 or current % 10 == 0 or current == total:
        v_type = verdict.get("verdict", "unknown")
        detail = verdict.get("type", "") if v_type == "claim" else verdict.get("gate_failed", "")
        print(f"[C1 EXTRACT] Turn {current:3d}/{total:3d} ({current/total*100.1:.1f}%) -> {v_type} ({detail})", flush=True)


def main() -> None:
    source_id = "00251a80c868f535"
    print(f"=== Starting C1 Extraction Run on episode {source_id} ===")
    print(f"Model ID: {MODEL_ID}")
    print(f"Validators added: {VALIDATORS_ADDED}")

    t0 = time.perf_counter()
    new_result = run_episode_extraction(
        source_id=source_id,
        is_falsification=False,
        output_filename=f"c1_rubric_extraction_{source_id}.json",
        progress_callback=progress_logger,
    )
    elapsed = time.perf_counter() - t0
    print(f"\nExtraction completed in {elapsed:.1f}s ({elapsed / new_result['total_turns']:.2f}s / turn)")

    # Load baseline runs
    fals_file = DEFAULT_EXTRACTION_DIR / f"falsification_extraction_{source_id}.json"
    with open(fals_file, "r", encoding="utf-8") as f:
        fals_result = json.load(f)

    new_metrics = new_result["metrics"]
    fals_metrics = fals_result["metrics"]

    # 3-column table
    print("\n" + "=" * 60)
    print("=== THREE-COLUMN COMPARISON TABLE (C1) ===")
    print("=" * 60)
    header = f"| {'Metric':<25} | {'Old Rubric':<12} | {'Stripped Control':<18} | {'New Rubric (C1)':<18} |"
    sep = f"|{'-'*27}|{'-'*14}|{'-'*20}|{'-'*20}|"
    print(header)
    print(sep)
    print(f"| {'Claims emitted':<25} | {'0':<12} | {fals_metrics['model_claims_count']:<18} | {new_metrics['model_claims_count']:<18} |")
    print(f"| {'Recall':<25} | {'0.0%':<12} | {fals_metrics['recall_pct']:<17}% | {new_metrics['recall_pct']:<17}% |")
    precision_old = "—"
    print(f"| {'Precision':<25} | {precision_old:<12} | {fals_metrics['precision_pct']:<17}% | {new_metrics['precision_pct']:<17}% |")
    print(f"| {'F1':<25} | {'0.0%':<12} | {fals_metrics['f1_pct']:<17}% | {new_metrics['f1_pct']:<17}% |")
    print(f"| {'TP':<25} | {'0':<12} | {fals_metrics['confusion_matrix']['tp']:<18} | {new_metrics['confusion_matrix']['tp']:<18} |")
    print(f"| {'FP':<25} | {'0':<12} | {fals_metrics['confusion_matrix']['fp']:<18} | {new_metrics['confusion_matrix']['fp']:<18} |")
    print(f"| {'FN':<25} | {'33':<12} | {fals_metrics['confusion_matrix']['fn']:<18} | {new_metrics['confusion_matrix']['fn']:<18} |")
    print(f"| {'TN':<25} | {'372':<12} | {fals_metrics['confusion_matrix']['tn']:<18} | {new_metrics['confusion_matrix']['tn']:<18} |")

    # Gate distributions
    print("\n" + "=" * 60)
    print("=== GATE FAILURE DISTRIBUTIONS (Share of 405 turns) ===")
    print("=" * 60)
    g_header = f"| {'Gate':<10} | {'B2 Gold':<16} | {'Old Rubric':<16} | {'Stripped':<16} | {'New Rubric (C1)':<16} |"
    g_sep = f"|{'-'*12}|{'-'*18}|{'-'*18}|{'-'*18}|{'-'*18}|"
    print(g_header)
    print(g_sep)

    b2_counts = {"gate_1": 302, "gate_2": 8, "gate_3": 6, "gate_4": 56}
    old_counts = {"gate_1": 405, "gate_2": 0, "gate_3": 0, "gate_4": 0}
    total = 405

    for g in ["gate_1", "gate_2", "gate_3", "gate_4"]:
        b2_c = b2_counts[g]
        b2_r = b2_c / total * 100
        old_c = old_counts[g]
        old_r = old_c / total * 100
        f_c = fals_metrics["gate_failure_counts_model"].get(g, 0)
        f_r = f_c / total * 100
        n_c = new_metrics["gate_failure_counts_model"].get(g, 0)
        n_r = n_c / total * 100
        print(f"| {g:<10} | {b2_c:>3} ({b2_r:5.2f}%)   | {old_c:>3} ({old_r:5.2f}%)   | {f_c:>3} ({f_r:5.2f}%)   | {n_c:>3} ({n_r:5.2f}%)   |")

    print("\nQuote provenance:")
    print(f"  Verbatim quote rate: {new_metrics['verbatim_quote_matches']}/{new_metrics['model_claims_count']} ({new_metrics['verbatim_quote_rate']}%)")
    print(f"  Context leaks: {new_metrics['context_leak_quotes']}")


if __name__ == "__main__":
    main()
