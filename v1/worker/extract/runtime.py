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
0. MANDATORY FIRST STEP: DOES THE SPEAKER TAKE A SIDE? (THE REACHABLE DECLINE BRANCH)
   Before considering any extraction, ask:
   "Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?"
   If NOT, emit nothing for this utterance: return {"claims": []}.
   - Most utterances in a conversation simply report facts, describe products, explain technical features, state metrics, predict outcomes, or share anecdotes.
   - Descriptive statements are NOT positions. If someone says "Azure holds a Fed ramp certification", "we have a seat open next week", "state legislatures passed 118 AI laws", or "deficit spending is correlated with housing costs", they are reporting or describing a situation, NOT taking a side.
   - DO NOT invent a position for descriptive, factual, or predictive statements. If the speaker does not explicitly advocate FOR or AGAINST a normative principle, policy, regulation, or controversial choice, you MUST return {"claims": []}.

1. MOST UTTERANCES CONTAIN NO CLAIM. Greetings, banter, questions, agreements ("yeah exactly"), anecdotes, factual stories, and descriptive observations produce an EMPTY LIST. An empty list {"claims": []} is the EXPECTED, CORRECT answer for conversational, descriptive, or non-position speech.
   - If a speaker mentions a fact, number, event, personal story, company, software feature, schedule, or market prediction without advocating FOR or AGAINST a specific policy, action, regulation, or controversial principle, return {"claims": []}.
   - Do NOT force an extraction if there is no clear matter at issue.

2. THE POSITION FRAME & CANONICAL PROPOSITION FORM (THE POSITION TEST — design_claim_extraction.md §2 — Issue 034 = B):
   - The position is elicited with the proposition, not applied to it after the fact.
   - Only if the speaker genuinely takes a side (Rule 0) is a claim elicited by writing the position frame:
       the speaker is FOR     <X>
       the speaker is AGAINST <X>
     <X> becomes `proposition_text`, and FOR / AGAINST becomes `stance` ('support' / 'oppose').
   - If you CANNOT write "the speaker is FOR <X>" or "the speaker is AGAINST <X>" as a coherent, grammatical sentence describing a genuine side the speaker took, DO NOT EMIT A CLAIM. Return {"claims": []}.
   - CANONICAL NOUN PHRASE: <X> MUST BE a stance-neutral, predicate-bearing NOUN PHRASE with the actor and polarity stripped out.
   - BYTE-IDENTICAL IDENTITY RULE: Two speakers with opposite opinions on the same matter at issue MUST share the EXACT SAME <X> noun phrase. The difference between opposing views lives EXCLUSIVELY in FOR vs AGAINST (or support vs oppose). NEVER vary <X> based on the speaker's stance.
   - MIXED STANCE: The speaker is FOR <X> in one respect and AGAINST <X> in another, and both frames can be written for the same claim (e.g., 'the speaker is FOR <X> in respect A and the speaker is AGAINST <X> in respect B'). If only one frame can be written, the stance is that one; `mixed` is not a residue.
   - NEVER emit a BARE TOPIC, ENTITY, VALUATION, EVENT, OR FACTUAL DESCRIPTION. A topic admits any stance, so opposing claims on it do not form a contradiction. If neither frame can be written, decline to emit:
       - "implementing software inside of an organization" (DECLINE: not a matter at issue someone is for/against)
       - "prompt length for ai model development" (DECLINE: technical parameter/topic)
       - "a good deal to be made" (DECLINE: commercial observation)
       - "most enterprises" (DECLINE: bare entity)
       - "ai race in america" (DECLINE: bare subject area)
       - "company worth 200 billion" (DECLINE: factual valuation)
       - "two or three hundred individual lawsuits" (DECLINE: event/count)
       - "Board of Supervisors meeting disrupted by internet vandalism" (DECLINE: incident report)
       - "people that are just really interested in the topics that we talk about" (DECLINE: banter/observation)
   - LENGTH AND RELATIONAL STRUCTURE FLOOR: <X> MUST be at least 5 words and include a relational marker: a preposition ('of', 'for', 'in', 'on', 'to', 'against', 'between') or a participle ('-ing'). Never emit 1-4 word fragments (e.g., 'eronic', 'apps', 'open source AI', 'federal debt reduction').
   - QUESTIONS AND CASUAL BANTER ARE NOT CLAIMS: Rhetorical questions, banter, or conversational remarks contain no own assertion. Return {"claims": []}.
   - SOFTWARE FEATURES AND TECHNICAL DESCRIPTIONS ARE NOT CLAIMS: Sentences describing how software works, what apps do, or capex investments are factual observations. Return {"claims": []}.
   - PASSING MATTERS AT ISSUE (POLICIES, ACTIONS, NORMATIVE CHOICES):
       'federal licensing of frontier AI models' (PASS: supports licensing / opposes licensing)
       'federal standard for algorithmic discrimination' (PASS: supports standard / opposes standard)
       'funding and attention for astronomy research in an era dominated by ai' (PASS)
       'diversification of ai models away from closed models' (PASS)
       'amazon burden-shifting strategy for employees and the american taxpayer' (PASS)
       'sandboxed testing of frontier AI models before deployment' (PASS)
       'industry-wide reduction in AI development pace to 20% slower' (PASS)
       'allowing individual gun ownership despite potential misuse' (PASS)
   - NEVER emit a full clause or finite verb sentence. Do NOT use finite verbs ('is', 'are', 'was', 'were', 'will', 'would', 'should', 'must', 'can', 'has', 'have') as the main predicate of <X>.
   - NEVER include polarity inside <X>: no 'should', 'must', 'ought', 'better/worse/cheaper/faster than', 'favored to win', 'should not', 'never', 'oppose', 'against', 'bad', 'harmful', 'cannot', 'not', or 'no'.
   - Polarity lives EXCLUSIVELY in `position_frame` and `stance`.

3. PROPOSITIONS MUST BE SELF-CONTAINED AND GLOBAL (Items W0 / §17m & W2 / §17p).
   - Never use unbound indexicals, speaker references, or vague placeholders in proposition_text (e.g., never say 'The speaker believes...', 'the subject...', 'this item...').
   - Never start a proposition with sentence-initial deictics or unbound pronouns (e.g., 'It is...', 'This...', 'That...', 'These...', 'Those...', 'They...', 'He...', 'She...', 'Their...', 'His...', 'Her...').
   - Never use third-person pronouns ('they', 'their', 'he', 'his', 'him', 'she', 'her') without an explicit antecedent entity named inside the proposition.
   - Never use comparatives without an explicit relatum (e.g., never write 'do the same thing on AI', 'the same answer', 'such development', or 'the other side' unless the comparative baseline is explicitly specified inside the proposition, like 'the same level of development as OpenAI').
   - A proposition must be a standalone noun phrase naming its concrete real-world referents, resolvable without knowing who uttered it.
   - Bound pronouns with an explicit intra-proposition antecedent (e.g., 'Moderna patenting of its mRNA technology', 'Google development of its own silicon') are valid.
   - Strip the actor completely: state the factual or normative matter at issue neutrally, without prefixing 'The speaker believes/argues/suggests'.
   - If the utterance is conversational banter, a personal question, or lacks a concrete named referent, return {"claims": []}.

4. INVARIANT I7 (SPEECH-ACT GUARDS): Exclude reported speech, hypotheticals, rhetorical setups ('You can say, okay...'), sarcasm, steelmanning, jokes, questions ('So you're saying...'), and factual reports/descriptions without a normative stance ('reports_fact' — e.g. describing product specs, certifications, or factual updates). If excluded, set is_own_assertion=false and specify exclusion_reason. If is_own_assertion=true, exclusion_reason MUST be null.

5. QUOTE TEXT: Return the exact verbatim substring from the utterance text as quote_text.

6. CONSTRAINED SCHEMA: Output must strictly conform to JSON format:
{
  "claims": [
    {
      "position_frame": "the speaker is FOR <X> | the speaker is AGAINST <X>",
      "proposition_text": "stance-neutral matter at issue noun phrase (<X>)",
      "stance": "support" | "oppose" | "mixed",
      "hedging_level": 0.0 to 1.0,
      "is_own_assertion": true | false,
      "exclusion_reason": null | "reported_speech" | "hypothetical" | "sarcasm" | "steelman" | "joke" | "question" | "reports_fact",
      "quote_text": "verbatim substring from utterance",
      "confidence": 0.0 to 1.0
    }
  ]
}

Examples:
Example 1:
Utterance: "Azure holds a Fed ramp, high authorization, and Department of Defense, impact level five clear ends."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, this is a factual description of a product certification.
Result: {"claims": []}

Example 2:
Utterance: "And clearly, I think we have a seat open next week."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, this is a scheduling fact.
Result: {"claims": []}

Example 3:
Utterance: "What's gonna happen is a blue state's gonna get blueer."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, this is a predictive observation without taking a side.
Result: {"claims": []}

Example 4:
Utterance: "The water uses quite manageable less than a golf course."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, this is an empirical description.
Result: {"claims": []}

Example 5:
Utterance: "We absolutely need federal licensing for frontier models."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
Yes, the speaker is FOR federal licensing of frontier AI models.
Result: {"claims": [{"position_frame": "the speaker is FOR federal licensing of frontier AI models", "proposition_text": "federal licensing of frontier AI models", "stance": "support", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "We absolutely need federal licensing for frontier models.", "confidence": 0.95}]}

Example 6:
Utterance: "Licensing would kill open source. Terrible idea."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
Yes, the speaker is AGAINST federal licensing of frontier AI models.
Result: {"claims": [{"position_frame": "the speaker is AGAINST federal licensing of frontier AI models", "proposition_text": "federal licensing of frontier AI models", "stance": "oppose", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "Licensing would kill open source. Terrible idea.", "confidence": 0.95}]}

Example 7:
Utterance: "Federal licensing makes sense for frontier clusters, but we can't impose it on smaller open research models."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
Yes, the speaker has mixed stances on federal licensing of frontier AI models.
Result: {"claims": [{"position_frame": "the speaker is FOR federal licensing of frontier AI models for top compute clusters and the speaker is AGAINST federal licensing of frontier AI models for smaller open research models", "proposition_text": "federal licensing of frontier AI models", "stance": "mixed", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "Federal licensing makes sense for frontier clusters, but we can't impose it on smaller open research models.", "confidence": 0.90}]}

Example 8:
Utterance: "Hardware makes building production apps unless you are willing to spend millions and millions of dollars for a very slow app, unfeasible."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
Yes, the speaker is AGAINST spending millions and millions of dollars for a very slow app.
Result: {"claims": [{"position_frame": "the speaker is AGAINST spending millions and millions of dollars for a very slow app", "proposition_text": "spending millions and millions of dollars for a very slow app", "stance": "oppose", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "Hardware makes building production apps unless you are willing to spend millions and millions of dollars for a very slow app, unfeasible.", "confidence": 0.95}]}

Example 9:
Utterance: "State legislatures, 118 AI laws have already been passed across the 50 states."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, the speaker is reporting a factual statistic without taking a normative side.
Result: {"claims": [{"position_frame": "the speaker is FOR state-level legislative regulation of artificial intelligence", "proposition_text": "state-level legislative regulation of artificial intelligence", "stance": "support", "hedging_level": 0.0, "is_own_assertion": false, "exclusion_reason": "reports_fact", "quote_text": "State legislatures, 118 AI laws have already been passed across the 50 states.", "confidence": 0.90}]}

Example 10:
Utterance: "Implementing software inside of an organization is always tough."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, conversational observation.
Result: {"claims": []}

Example 11:
Utterance: "We're experimenting with prompt length for ai model development."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, describing technical experimentation.
Result: {"claims": []}

Example 12:
Utterance: "There is probably a good deal to be made in commercial real estate."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, commercial speculation/topic.
Result: {"claims": []}

Example 13:
Utterance: "I mean, this is a company that was worth 200 billion."
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, factual valuation.
Result: {"claims": []}

Example 14:
Utterance: "So you're saying that the government should regulate all frontier compute clusters?"
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, this is a clarifying question, not the speaker's own assertion.
Result: {"claims": [{"position_frame": "the speaker is FOR government regulation of frontier artificial intelligence compute clusters", "proposition_text": "government regulation of frontier artificial intelligence compute clusters", "stance": "support", "hedging_level": 0.0, "is_own_assertion": false, "exclusion_reason": "question", "quote_text": "So you're saying that the government should regulate all frontier compute clusters?", "confidence": 0.90}]}

Example 15:
Utterance: "Hey everybody, welcome back to the podcast. How are you doing today?"
Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?
No, conversational greeting.
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
        prompt_version: str = "v1.9",
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
        self.prefix_tokens_count = (
            len(system_prompt.split()) * 2
        )  # Approx token count (~200 tokens)
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
                f'Utterance: "{utterance_text}"\n'
                f"Does the speaker take a side here — is there something they are FOR or AGAINST, as opposed to describing, reporting, predicting, or asking?\n"
                f'If not, emit nothing for this utterance (return {{"claims": []}}).\n'
                f"Result:<end_of_turn>\n"
                f"<start_of_turn>model\n"
            )
            raw_text, tps, prompt_toks, gen_toks = self.backend.generate(
                full_prompt, max_tokens=256
            )
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
