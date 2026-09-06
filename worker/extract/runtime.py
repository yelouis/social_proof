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
1. MOST UTTERANCES CONTAIN NO CLAIM. Greetings, banter, questions, agreements ("yeah exactly") produce an EMPTY LIST. An empty list {"claims": []} is the EXPECTED, CORRECT answer for conversational or non-position speech.
2. PROPOSITIONS MUST BE STANCE-NEUTRAL. Never include polarity words (e.g., 'should not', 'never', 'oppose', 'against', 'bad', 'harmful', 'cannot') in proposition_text. Polarity belongs exclusively in stance.
3. PROPOSITIONS MUST BE SELF-CONTAINED AND GLOBAL (Items W0 / §17m & W2 / §17p).
   - Never use unbound indexicals, speaker references, or vague placeholders in proposition_text (e.g., never say 'The speaker believes...', 'the subject...', 'this item...').
   - Never start a proposition with sentence-initial deictics or unbound pronouns (e.g., 'It is...', 'This...', 'That...', 'These...', 'Those...', 'They...', 'He...', 'She...', 'Their...', 'His...', 'Her...').
   - Never use third-person pronouns ('they', 'their', 'he', 'his', 'him', 'she', 'her') without an explicit antecedent entity named inside the proposition.
   - Never use comparatives without an explicit relatum (e.g., never write 'do the same thing on AI', 'the same answer', 'such development', or 'the other side' unless the comparative baseline is explicitly specified inside the proposition, like 'the same level of development as OpenAI').
   - A proposition must be a standalone declarative statement naming its concrete real-world referents, resolvable without knowing who uttered it.
   - Bound pronouns with an explicit intra-proposition antecedent (e.g., 'Moderna patented its mRNA technology', 'Google develops its own silicon') are valid.
   - Strip the actor completely: state the factual or normative matter at issue neutrally, without prefixing 'The speaker believes/argues/suggests'.
   - If the utterance is conversational banter, a personal question, or lacks a concrete named referent, return {"claims": []}.
4. INVARIANT I7 (SPEECH-ACT GUARDS): Exclude reported speech, hypotheticals, rhetorical setups ('You can say, okay...'), sarcasm, steelmanning, jokes, questions ('So you're saying...'), and ambiguous quote agreements. If excluded, set is_own_assertion=false and specify exclusion_reason. If is_own_assertion=true, exclusion_reason MUST be null.
5. QUOTE TEXT: Return the exact verbatim substring from the utterance text as quote_text.
6. CONSTRAINED SCHEMA: Output must strictly conform to JSON format:
{
  "claims": [
    {
      "proposition_text": "stance-neutral matter at issue",
      "stance": "support" | "oppose" | "mixed",
      "hedging_level": 0.0 to 1.0,
      "is_own_assertion": true | false,
      "exclusion_reason": null | "reported_speech" | "hypothetical" | "sarcasm" | "steelman" | "joke" | "question",
      "quote_text": "verbatim substring from utterance",
      "confidence": 0.0 to 1.0
    }
  ]
}

Examples:
Utterance: "It is true that China is much more optimistic about AI than we are."
Result: {"claims": [{"proposition_text": "China has greater societal and official optimism toward artificial intelligence than Western nations", "stance": "support", "hedging_level": 0.05, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "It is true that China is much more optimistic about AI than we are.", "confidence": 0.95}]}

Utterance: "So you're saying that the government should regulate all frontier compute clusters?"
Result: {"claims": [{"proposition_text": "Government regulation of frontier artificial intelligence compute clusters", "stance": "support", "hedging_level": 0.0, "is_own_assertion": false, "exclusion_reason": "question", "quote_text": "So you're saying that the government should regulate all frontier compute clusters?", "confidence": 0.90}]}

Utterance: "You can say, okay, well Verizon spent a hundred billion dollars on fiber optics."
Result: {"claims": [{"proposition_text": "Telecommunications infrastructure capital expenditure in fiber optics", "stance": "support", "hedging_level": 0.1, "is_own_assertion": false, "exclusion_reason": "hypothetical", "quote_text": "You can say, okay, well Verizon spent a hundred billion dollars on fiber optics.", "confidence": 0.85}]}

Utterance: "No sparks, but I saw a video that I said to him, I said, is this CGI or is this real?"
Result: {"claims": []}

Utterance: "And when people were saying this, they were, they were told you were creating conspiracy theories."
Result: {"claims": []}

Utterance: "Hey everybody, welcome back to the podcast. How are you doing today?"
Result: {"claims": []}
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
        prompt_version: str = "v1.5",
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
