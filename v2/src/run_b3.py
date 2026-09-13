"""Execution driver for B3: Extract Against the Rubric & Falsification Run.

Executes both:
1. Rubric prompt extraction on all 405 turns of All-In E287 (00251a80c868f535).
2. Falsification run on all 405 turns with stripped prompt ("extract claims").
Generates comprehensive evaluation metrics, confusion matrix, disagreement tables,
gate distributions, and quote provenance checks.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v2.src.extract import (
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_GOLD_DIR,
    DEFAULT_TRANSCRIPT_DIR,
    MODEL_ID,
    VALIDATORS_ADDED,
    evaluate_against_gold,
    load_rubric,
    run_episode_extraction,
)


def progress_logger(run_name: str):
    def callback(current: int, total: int, verdict: dict):
        if current == 1 or current % 25 == 0 or current == total:
            v_type = verdict.get("verdict", "unknown")
            detail = verdict.get("type", "") if v_type == "claim" else verdict.get("gate_failed", "")
            print(f"[{run_name}] Turn {current:3d}/{total:3d} ({current/total*100.1:.1f}%) -> {v_type} ({detail})", flush=True)
    return callback


def main() -> None:
    source_id = "00251a80c868f535"
    print(f"=== Starting B3 Extraction Run on episode {source_id} ===")
    print(f"Model ID: {MODEL_ID}")
    print(f"Validators added: {VALIDATORS_ADDED}")

    # 1. Rubric Extraction Run
    print("\n--- 1. Running Rubric Prompt Extraction (405 turns) ---")
    t0 = time.perf_counter()
    rubric_result = run_episode_extraction(
        source_id=source_id,
        is_falsification=False,
        progress_callback=progress_logger("RUBRIC"),
    )
    rubric_elapsed = time.perf_counter() - t0
    print(f"Rubric run completed in {rubric_elapsed:.2f}s")

    # 2. Falsification Run (Stripped prompt)
    print("\n--- 2. Running Falsification Extraction (Stripped Rubric, 405 turns) ---")
    t1 = time.perf_counter()
    fals_result = run_episode_extraction(
        source_id=source_id,
        is_falsification=True,
        progress_callback=progress_logger("FALSIFICATION"),
    )
    fals_elapsed = time.perf_counter() - t1
    print(f"Falsification run completed in {fals_elapsed:.2f}s")

    # 3. Compile Comparison Report
    rubric_metrics = rubric_result["metrics"]
    fals_metrics = fals_result["metrics"]

    report_lines = [
        f"# B3 Extraction & Falsification Report — Episode {source_id}",
        "",
        f"- **Model**: `{MODEL_ID}`",
        f"- **Episode**: `{source_id}` (All-In E287: Nvidia's Historic Quarter, SaaS Comeback)",
        f"- **Total Turns Processed**: {rubric_result['total_turns']}",
        f"- **Rubric Run Duration**: {rubric_elapsed:.1f}s ({rubric_elapsed / rubric_result['total_turns']:.2f}s / turn)",
        f"- **Falsification Run Duration**: {fals_elapsed:.1f}s ({fals_elapsed / fals_result['total_turns']:.2f}s / turn)",
        f"- **Validators Added**: {VALIDATORS_ADDED} (strictly zero)",
        "",
        "## 1. Primary Metrics Against B2 Gold Standard",
        "",
        "| Metric | Rubric Prompt | Falsification (Stripped) | Delta |",
        "|---|---|---|---|",
        f"| **Gold Claims (P)** | {rubric_metrics['gold_claims_count']} | {fals_metrics['gold_claims_count']} | 0 |",
        f"| **Model Claims** | {rubric_metrics['model_claims_count']} | {fals_metrics['model_claims_count']} | {rubric_metrics['model_claims_count'] - fals_metrics['model_claims_count']:+d} |",
        f"| **True Positives (TP)** | {rubric_metrics['confusion_matrix']['tp']} | {fals_metrics['confusion_matrix']['tp']} | {rubric_metrics['confusion_matrix']['tp'] - fals_metrics['confusion_matrix']['tp']:+d} |",
        f"| **False Positives (FP)** | {rubric_metrics['confusion_matrix']['fp']} | {fals_metrics['confusion_matrix']['fp']} | {rubric_metrics['confusion_matrix']['fp'] - fals_metrics['confusion_matrix']['fp']:+d} |",
        f"| **False Negatives (FN)** | {rubric_metrics['confusion_matrix']['fn']} | {fals_metrics['confusion_matrix']['fn']} | {rubric_metrics['confusion_matrix']['fn'] - fals_metrics['confusion_matrix']['fn']:+d} |",
        f"| **True Negatives (TN)** | {rubric_metrics['confusion_matrix']['tn']} | {fals_metrics['confusion_matrix']['tn']} | {rubric_metrics['confusion_matrix']['tn'] - fals_metrics['confusion_matrix']['tn']:+d} |",
        f"| **Precision** | **{rubric_metrics['precision_pct']}%** | **{fals_metrics['precision_pct']}%** | **{rubric_metrics['precision_pct'] - fals_metrics['precision_pct']:+.2f}%** |",
        f"| **Recall** | **{rubric_metrics['recall_pct']}%** | **{fals_metrics['recall_pct']}%** | **{rubric_metrics['recall_pct'] - fals_metrics['recall_pct']:+.2f}%** |",
        f"| **F1 Score** | **{rubric_metrics['f1_pct']}%** | **{fals_metrics['f1_pct']}%** | **{rubric_metrics['f1_pct'] - fals_metrics['f1_pct']:+.2f}%** |",
        "",
        "## 2. Gate Failure Distribution",
        "",
        "Comparison of model exclusions vs human gold exclusions on B2 reference episode:",
        "",
        "| Gate | Gold Set Count (Rate) | Rubric Model Count (Rate) | Falsification Count (Rate) |",
        "|---|---|---|---|",
    ]

    for g in ["gate_1", "gate_2", "gate_3", "gate_4"]:
        g_name = g.replace("_", " ").title()
        g_cnt = rubric_metrics["gate_failure_counts_gold"].get(g, 0)
        g_rate = rubric_metrics["gate_failure_rates_gold"].get(g, 0.0)
        m_cnt = rubric_metrics["gate_failure_counts_model"].get(g, 0)
        m_rate = rubric_metrics["gate_failure_rates_model"].get(g, 0.0)
        f_cnt = fals_metrics["gate_failure_counts_model"].get(g, 0)
        f_rate = fals_metrics["gate_failure_rates_model"].get(g, 0.0)
        report_lines.append(f"| **{g_name}** | {g_cnt} ({g_rate:.2f}%) | {m_cnt} ({m_rate:.2f}%) | {f_cnt} ({f_rate:.2f}%) |")

    report_lines.extend([
        "",
        "## 3. Quote Integrity & Provenance",
        "",
        f"- **Model Claims Emitted**: {rubric_metrics['model_claims_count']}",
        f"- **Quotes Resolving Verbatim in Target Turn**: {rubric_metrics['verbatim_quote_matches']} / {rubric_metrics['model_claims_count']} ({rubric_metrics['verbatim_quote_rate']}%)",
        f"- **Quotes Resolving to Context Turn Only (Hallucinated Context Leaks)**: {rubric_metrics['context_leak_quotes']}",
        "",
        "## 4. Disagreements by Turn ID (Rubric Run vs Gold Standard)",
        "",
        f"Total disagreements: {rubric_metrics['disagreements_count']} turns out of 405.",
        "",
        "### False Positives (Model emitted Claim, Gold excluded)",
        "",
        "| Turn ID | Speaker | Gold Gate | Model Type | Quote Snippet | Claim Stated |",
        "|---|---|---|---|---|---|",
    ])

    fps = [d for d in rubric_metrics["disagreements"] if d["type"] == "false_positive"]
    for d in fps:
        q = d["model_quote"].replace("\n", " ")[:60]
        c = d["model_claim"].replace("\n", " ")[:60]
        report_lines.append(f"| `{d['turn_id']}` | {d['speaker']} | `{d['gold_gate']}` | `{d.get('type', 'claim')}` | *\"{q}\"* | {c} |")

    report_lines.extend([
        "",
        "### False Negatives (Gold had Claim, Model excluded)",
        "",
        "| Turn ID | Speaker | Model Gate | Gold Claim | Turn Text Snippet |",
        "|---|---|---|---|---|",
    ])

    fns = [d for d in rubric_metrics["disagreements"] if d["type"] == "false_negative"]
    for d in fns:
        c = d["gold_claim"].replace("\n", " ")[:60]
        t_snippet = d["turn_text"].replace("\n", " ")[:60]
        report_lines.append(f"| `{d['turn_id']}` | {d['speaker']} | `{d['model_gate']}` | {c} | *\"{t_snippet}\"* |")

    report_content = "\n".join(report_lines) + "\n"
    report_file = DEFAULT_EXTRACTION_DIR / "README.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport written to {report_file}")
    print("\n=== SUMMARY METRICS ===")
    print(f"Rubric Precision: {rubric_metrics['precision_pct']}%")
    print(f"Rubric Recall:    {rubric_metrics['recall_pct']}%")
    print(f"Rubric F1:        {rubric_metrics['f1_pct']}%")
    print(f"Falsification Precision: {fals_metrics['precision_pct']}%")
    print(f"Falsification Recall:    {fals_metrics['recall_pct']}%")
    print(f"Falsification F1:        {fals_metrics['f1_pct']}%")
    print(f"Verbatim Quote Matches:  {rubric_metrics['verbatim_quote_matches']}/{rubric_metrics['model_claims_count']} ({rubric_metrics['verbatim_quote_rate']}%)")
    print(f"Context Leaks:           {rubric_metrics['context_leak_quotes']}")
    print(f"Validators Added:        {VALIDATORS_ADDED}")


if __name__ == "__main__":
    main()
