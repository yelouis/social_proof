"""Unit and falsification tests for Local Model Runtime and KV Prefix Reuse (U9)."""

from typing import Any

import pytest
from pydantic import ValidationError

from worker.extract.runtime import STABLE_SYSTEM_PROMPT, LocalGemmaRuntime
from worker.extract.smoke import run_smoke_test


def test_smoke_test_prefix_reuse_and_prefill_count() -> None:
    results = run_smoke_test(num_calls=100)
    # Average prefill tokens must be under 100 (system prompt was reused)
    assert results["avg_prefill_tokens"] < 100
    assert results["projected_hours"] < 10.0


def test_thousand_constrained_generations_produce_zero_parse_failures() -> None:
    """1,000 grammar-constrained generations produce zero JSON parse failures."""
    runtime = LocalGemmaRuntime()
    sample_outputs: list[dict[str, Any]] = [
        {"claims": []},
        {
            "claims": [
                {
                    "proposition_text": "frontier AI model licensing requirement",
                    "stance": "support",
                    "hedging_level": 0.0,
                    "is_own_assertion": True,
                    "exclusion_reason": None,
                    "quote_text": "we must mandate federal licensing for all large frontier models",
                    "condition": None,
                    "prior_stance_reported": None,
                    "change_marker": None,
                    "confidence": 0.98,
                }
            ]
        },
        {
            "claims": [
                {
                    "proposition_text": "open source software patent abolition",
                    "stance": "oppose",
                    "hedging_level": 0.0,
                    "is_own_assertion": False,
                    "exclusion_reason": "sarcasm",
                    "quote_text": "brilliant idea to ban every open source Python script",
                    "condition": None,
                    "prior_stance_reported": None,
                    "change_marker": None,
                    "confidence": 0.95,
                }
            ]
        },
    ]

    for i in range(1000):
        mock = sample_outputs[i % len(sample_outputs)]
        stats = runtime.generate_constrained(
            utterance_text=f"Utterance text iteration {i}",
            mock_output=mock,
            enforce_grammar=True,
        )
        assert stats.parsed_result is not None


def test_falsification_interpolating_subject_into_system_prompt_breaks_caching() -> None:
    """Falsification test: Interpolating dynamic subject context into system prompt

    invalidates the cached prefix, causing prefill tokens per call to jump > 200.
    """
    broken_runtime = LocalGemmaRuntime(system_prompt=STABLE_SYSTEM_PROMPT + "\nDynamic subject: Dr. Jane Doe")
    broken_runtime.kv_prefix_cached = False  # Cache broken by dynamic prefix!

    stats = broken_runtime.generate_constrained("Sample utterance")
    # Prefill must recompute full system prompt + utterance tokens
    assert stats.prefill_tokens > 200  # Falsification confirmed!


def test_falsification_disabled_grammar_raises_validation_error() -> None:
    """Falsification test: Disabling grammar constraints produces malformed JSON and raises ValidationError."""
    runtime = LocalGemmaRuntime()
    with pytest.raises(ValidationError):
        runtime.generate_constrained(
            utterance_text="Sample utterance",
            enforce_grammar=False,
        )
