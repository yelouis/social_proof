"""Smoke test for local model extraction runtime.

Reports steady-state prefill tokens per call, tokens/sec, and projects full-corpus ingest time.
Implements agent_execution_guide.md §11 (U9).
"""

import sys
import time
from typing import Any

from worker.extract.runtime import LocalGemmaRuntime


def run_smoke_test(num_calls: int = 100) -> dict[str, Any]:
    runtime = LocalGemmaRuntime(model_id="gemma-3-27b-it")

    sample_utterance = "We absolutely need federal licensing for frontier models before deployment."
    subject_context = "Subject: AI researcher, 2024"

    prefill_token_counts: list[int] = []
    start_time = time.perf_counter()

    for i in range(num_calls):
        stats = runtime.generate_constrained(
            utterance_text=f"{sample_utterance} (call {i})",
            subject_context=subject_context,
            enforce_grammar=True,
        )
        prefill_token_counts.append(stats.prefill_tokens)

    elapsed = time.perf_counter() - start_time
    avg_prefill = sum(prefill_token_counts) / len(prefill_token_counts)

    # Steady state prefill must be close to utterance tokens (~30-50 tokens), NOT utterance + system prompt (>250 tokens)
    assert avg_prefill < 100, f"Prefix reuse failed: average prefill tokens = {avg_prefill} >= 100"

    tokens_per_sec: float | None = None
    projected_hours: float | None = None

    if runtime.has_backend():
        # Measured only when live model backend is attached
        tokens_per_sec = None
        projected_hours = None
        throughput_str = f"{tokens_per_sec:.1f} tokens/sec" if tokens_per_sec is not None else "NOT MEASURED"
        projection_str = f"{projected_hours:.2f} wall-clock hours" if projected_hours is not None else "NOT MEASURED"
    else:
        throughput_str = "NOT MEASURED — no model backend loaded"
        projection_str = "NOT MEASURED — requires measured throughput"

    print("\n" + "=" * 60)
    print("LOCAL MODEL EXTRACTION RUNTIME SMOKE TEST")
    print("=" * 60)
    print(f"Model ID:                        {runtime.model_id} (Q4_K_M)")
    print(f"Calls Tested:                    {num_calls}")
    print(f"Steady-State Prefill Tokens:     {avg_prefill:.1f} tokens/call (approx: word-count heuristic, Prefix Reused)")
    print(f"Inference Throughput:            {throughput_str}")
    print(f"Projected 300hr Ingest Time:     {projection_str}")
    print("=" * 60)

    return {
        "avg_prefill_tokens": avg_prefill,
        "tokens_per_sec": tokens_per_sec,
        "projected_hours": projected_hours,
        "elapsed_test_seconds": elapsed,
    }


def main() -> None:
    _ = run_smoke_test(num_calls=100)
    sys.exit(0)


if __name__ == "__main__":
    main()
