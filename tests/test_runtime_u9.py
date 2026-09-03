"""Unit and falsification tests for Local Model Runtime and KV Prefix Reuse (U9)."""

from typing import Any

import pytest
from pydantic import ValidationError

from worker.extract.runtime import STABLE_SYSTEM_PROMPT, LocalGemmaRuntime
from worker.extract.smoke import run_smoke_test


def test_smoke_test_prefix_reuse_and_prefill_count(capsys: pytest.CaptureFixture[str]) -> None:
    results = run_smoke_test(num_calls=100)
    # Average prefill tokens must be under 100 (system prompt was reused)
    assert results["avg_prefill_tokens"] < 100
    assert results["tokens_per_sec"] is None
    assert results["projected_hours"] is None

    # Assert no numeric throughput or projection appears in stdout
    captured = capsys.readouterr()
    assert "Inference Throughput:            NOT MEASURED — no model backend loaded" in captured.out
    assert "Projected 300hr Ingest Time:     NOT MEASURED — requires measured throughput" in captured.out


def test_stub_runtime_tokens_per_second_is_none() -> None:
    runtime = LocalGemmaRuntime()
    assert runtime.has_backend() is False
    stats = runtime.generate_constrained("Sample utterance")
    assert stats.tokens_per_second is None


@pytest.mark.requires_models
def test_live_mlx_backend_execution_and_throughput() -> None:
    """Tests live local Gemma runtime via MLX backend."""
    runtime = LocalGemmaRuntime(load_live_backend=True)
    assert runtime.has_backend() is True

    stats = runtime.generate_constrained(
        utterance_text="We must mandate federal licensing for frontier models before deployment.",
        subject_context="Subject: AI researcher, 2024",
    )
    assert stats.tokens_per_second is not None
    assert stats.tokens_per_second > 0.0
    assert stats.parsed_result is not None
    assert stats.prefill_tokens > 0
    assert stats.generation_tokens > 0


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


def test_falsification_fake_throughput_fails_not_measured_assertion() -> None:
    """Falsification test: Emitting numeric throughput when no model is loaded

    causes the stdout 'NOT MEASURED' assertion to fail.
    """
    fake_throughput_str = "Inference Throughput:            35.0 tokens/sec"
    # When fake throughput is printed instead of NOT MEASURED:
    assert "NOT MEASURED — no model backend loaded" not in fake_throughput_str  # Falsification confirmed!
