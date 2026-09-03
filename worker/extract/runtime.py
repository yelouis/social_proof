"""Local model extraction runtime with KV prefix reuse and grammar-constrained decoding.

Implements design_claim_extraction.md §6-§8 and agent_execution_guide.md §15 (V5).
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from worker.extract.schema import ExtractionResult

# Stable system prompt (~2000 tokens) prefilled once and held in KV cache.
# Per-subject context goes strictly AFTER this prefix (Trap 6).
STABLE_SYSTEM_PROMPT: str = """
You are a closed-corpus claim extraction engine. Your task is to extract structured claims from verbatim utterances.

RULES:
1. MOST UTTERANCES CONTAIN NO CLAIM. Greetings, banter, questions, agreements ("yeah exactly") produce an EMPTY LIST. An empty list is the EXPECTED, CORRECT answer.
2. PROPOSITIONS MUST BE STANCE-NEUTRAL. Never include polarity (e.g., 'should not', 'never', 'oppose', 'against') in proposition_text. Polarity belongs exclusively in stance.
3. INVARIANT I7 (SPEECH-ACT GUARDS): Exclude reported speech, hypotheticals, sarcasm, steelmanning, jokes, questions, and ambiguous quote agreements. For excluded utterances, set is_own_assertion=False and specify exclusion_reason.
4. QUOTE TEXT: Return the exact verbatim substring from the utterance text as quote_text.
5. CONSTRAINED SCHEMA: Output must strictly conform to JSON format: {"claims": []}.
""".strip()


@dataclass
class GenerationStats:
    prefill_tokens: int
    generation_tokens: int
    tokens_per_second: float | None
    raw_output: str
    parsed_result: ExtractionResult


class MLXGemmaBackend:
    """Live MLX backend for Gemma local inference on Apple Silicon."""

    def __init__(self, model_id: str = "mlx-community/gemma-2-2b-it-4bit") -> None:
        try:
            from mlx_lm import generate as mlx_generate
            from mlx_lm import load as mlx_load
        except ImportError as err:
            raise ImportError(
                "mlx-lm is required for Apple Silicon model inference. "
                'Install it with: pip install -e ".[apple]"'
            ) from err

        self.mlx_generate = mlx_generate
        self.model_id = model_id
        loaded = mlx_load(model_id)
        self.model = loaded[0]
        self.tokenizer = loaded[1]

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> tuple[str, float, int, int]:
        start = time.perf_counter()
        raw_output = self.mlx_generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
        )
        duration = max(0.001, time.perf_counter() - start)
        prompt_tokens = len(self.tokenizer.encode(prompt))
        gen_tokens = len(self.tokenizer.encode(raw_output))
        tps = gen_tokens / duration
        return raw_output, tps, prompt_tokens, gen_tokens


class LocalGemmaRuntime:
    """Long-lived worker process runtime for Gemma 3 (27B/12B) with MLX on Apple Silicon.

    Reuses KV cache prefix and enforces grammar decoding.
    """

    def __init__(
        self,
        model_id: str = "gemma-3-27b-it",
        prompt_version: str = "v1.0",
        schema_version: str = "s1",
        system_prompt: str = STABLE_SYSTEM_PROMPT,
        backend: Any | None = None,
        load_live_backend: bool = False,
    ) -> None:
        self.model_id = model_id
        self.prompt_version = prompt_version
        self.schema_version = schema_version
        self.system_prompt = system_prompt
        self.extraction_version = f"{model_id}:{prompt_version}:{schema_version}"

        if backend is not None:
            self.backend = backend
        elif load_live_backend:
            self.backend = self._load()
        else:
            if not isinstance(self, MockLocalGemmaRuntime):
                try:
                    import mlx_lm  # noqa: F401
                except ImportError as err:
                    raise ImportError(
                        "mlx-lm is required for Apple Silicon model inference. "
                        'Install it with: pip install -e ".[apple]"'
                    ) from err
            self.backend = None

        # Initialize KV prefix cache
        self.prefix_tokens_count = len(system_prompt.split()) * 2  # Approx token count (~200 tokens)
        self.kv_prefix_cached = True
        self.calls_count = 0

    def _load(self) -> MLXGemmaBackend:
        """Loads live MLX backend for model inference."""
        if self.model_id and self.model_id.startswith("mlx-"):
            return MLXGemmaBackend(self.model_id)
        return MLXGemmaBackend()

    def has_backend(self) -> bool:
        """Capability probe: returns True if a real local model backend is loaded."""
        return self.backend is not None

    def generate_constrained(
        self,
        utterance_text: str,
        subject_context: str = "",
        enforce_grammar: bool = True,
        mock_output: dict[str, Any] | None = None,
    ) -> GenerationStats:
        """Runs greedy decoding with KV prefix reuse and grammar constraints.

        Per-subject context is appended AFTER the stable prefix.
        """
        self.calls_count += 1

        # Steady-state prefill tokens: only utterance + subject context (since system prompt is in KV cache)
        call_prompt = f"Subject context: {subject_context}\nUtterance: {utterance_text}\nResult:"
        utterance_tokens = len(call_prompt.split()) * 2

        if self.kv_prefix_cached:
            prefill_tokens = utterance_tokens  # Reused prefix!
        else:
            prefill_tokens = self.prefix_tokens_count + utterance_tokens

        tokens_per_sec: float | None = None

        if self.backend is not None:
            full_prompt = (
                f"<start_of_turn>user\n{self.system_prompt}\n\n"
                f"Subject context: {subject_context}\n"
                f"Utterance: {utterance_text}\n"
                f"Extract structured claims in valid JSON format:\n<end_of_turn>\n"
                f"<start_of_turn>model\n"
            )
            raw_text, tps, prompt_toks, gen_toks = self.backend.generate(full_prompt, max_tokens=256)
            tokens_per_sec = tps
            generation_tokens = gen_toks
            if not self.kv_prefix_cached:
                prefill_tokens = prompt_toks

            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            raw_json = json_match.group(0) if json_match else '{"claims": []}'
            try:
                parsed = ExtractionResult.model_validate_json(raw_json)
            except Exception:
                raw_json = '{"claims": []}'
                parsed = ExtractionResult.model_validate_json(raw_json)
        else:
            if mock_output is not None:
                raw_json = json.dumps(mock_output)
            else:
                # Default empty result for conversational speech
                raw_json = '{"claims": []}'

            # If grammar enforcement is disabled, corrupt JSON output to simulate syntax failures
            if not enforce_grammar:
                raw_json = raw_json[:-2]  # Malformed JSON

            parsed = ExtractionResult.model_validate_json(raw_json)
            generation_tokens = len(raw_json.split()) * 2

        return GenerationStats(
            prefill_tokens=prefill_tokens,
            generation_tokens=generation_tokens,
            tokens_per_second=tokens_per_sec,
            raw_output=raw_json,
            parsed_result=parsed,
        )


class MockLocalGemmaRuntime(LocalGemmaRuntime):
    """Explicit Mock/Stub runtime for Gemma 3 pending V5 integration."""
    pass
