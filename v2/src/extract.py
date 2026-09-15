"""Claim extraction against the written claim rubric.

Implements B3 from v2/docs/agent_execution_guide.md §7.
Zero post-processing validators: runs the rubric alone and measures it.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Standing requirement Step 4: validators added = 0
VALIDATORS_ADDED: int = 0

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUBRIC_PATH = ROOT_DIR / "docs" / "design_claim_rubric.md"
DEFAULT_TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
DEFAULT_GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
DEFAULT_EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"
MODEL_ID = "mlx-community/gemma-2-2b-it-4bit"
QUANTISATION = "4-bit"
RUNTIME = "mlx_lm"
PROMPT_VERSION_RUBRIC = "rubric_prompt_v1"
PROMPT_VERSION_FALSIFICATION = "falsification_prompt_v1"
RUBRIC_COMMIT = "23da31c"


def load_rubric(path: Path | str = DEFAULT_RUBRIC_PATH) -> str:
    """Loads the rubric markdown file verbatim."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_rubric_sections(rubric_text: str) -> dict[str, str]:
    """Extracts §2 and §3 from the rubric text for verbatim assertion verification."""
    s2_match = re.search(r"(## 2\. The four gates.*?)## 3\. Claim types", rubric_text, re.DOTALL)
    if not s2_match:
        raise ValueError("Could not find section 2 in rubric text")
    s2 = s2_match.group(1).strip()

    s3_match = re.search(r"(## 3\. Claim types.*?)## 4\. What is recorded", rubric_text, re.DOTALL)
    if not s3_match:
        raise ValueError("Could not find section 3 in rubric text")
    s3 = s3_match.group(1).strip()

    return {
        "section_2": s2,
        "section_3": s3,
    }


def build_rubric_prompt(
    rubric_text: str,
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
) -> str:
    """Builds the extraction prompt interpolating the rubric verbatim.

    Preceding context turn is provided for reference only (context is read, never quoted from).
    Target turn is evaluated against the 4 rubric gates in order.
    """
    ctx_speaker = context_turn.get("speaker_label", "None") if context_turn else "None"
    ctx_text = context_turn.get("text", "None") if context_turn else "None"
    ctx_turn_id = context_turn.get("turn_id", "None") if context_turn else "None"

    target_turn_id = target_turn["turn_id"]
    target_speaker = target_turn.get("speaker_label", "unknown")
    target_text = target_turn.get("text", "")

    prompt = f"""<start_of_turn>user
You are an expert claim extraction engine applying the official claim rubric.

{rubric_text}

---
TASK:
Analyze the target turn from the transcript and determine whether it contains a defensible claim under the rubric, or must be excluded under Gate 1, 2, 3, or 4.

Context turn (preceding turn {ctx_turn_id}, for reference only — DO NOT quote or extract from context):
Speaker: {ctx_speaker}
Text: {ctx_text}

Target turn to evaluate:
Turn ID: {target_turn_id}
Speaker: {target_speaker}
Text: {target_text}

INSTRUCTIONS:
1. Apply the four gates in order:
   - Gate 1 (Attributable): Is the speaker asserting it in their own voice? (Fails if guest, unknown speaker, reporting what others said, asking a question, banter, reading ad copy, or hypothetical).
   - Gate 2 (About the world): Is it about something outside the podcast recording? (Fails if show mechanics, schedule, tickets, greetings, banter).
   - Gate 3 (Contestable): Could a reasonable person disagree? (Fails on tautologies, undisputed facts, product specs).
   - Gate 4 (Standalone): Can a reader tell what is being asserted without conversational context?
2. If ANY gate fails, output an exclusion JSON with that gate:
```json
{{
  "verdict": "exclusion",
  "turn_id": "{target_turn_id}",
  "gate_failed": "gate_1" | "gate_2" | "gate_3" | "gate_4",
  "reason": "<one sentence reason>"
}}
```
3. If ALL four gates pass, output a claim JSON:
```json
{{
  "verdict": "claim",
  "turn_id": "{target_turn_id}",
  "speaker": "{target_speaker}",
  "type": "position" | "prediction" | "causal" | "evaluative" | "contested fact",
  "quote": "<exact verbatim substring from target turn text, NEVER from context>",
  "claim": "<the assertion as a standalone sentence with pronouns resolved>",
  "offset": <character start offset of quote in target turn text>
}}
```
Respond strictly with a JSON object.
<end_of_turn>
<start_of_turn>model
"""
    return prompt


def build_falsification_prompt(
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
) -> str:
    """Builds the falsification prompt with the rubric stripped, leaving only 'extract claims'."""
    ctx_speaker = context_turn.get("speaker_label", "None") if context_turn else "None"
    ctx_text = context_turn.get("text", "None") if context_turn else "None"
    ctx_turn_id = context_turn.get("turn_id", "None") if context_turn else "None"

    target_turn_id = target_turn["turn_id"]
    target_speaker = target_turn.get("speaker_label", "unknown")
    target_text = target_turn.get("text", "")

    prompt = f"""<start_of_turn>user
You are a claim extraction tool. Extract claims from the following speaking turn.

Context turn (preceding turn {ctx_turn_id}):
Speaker: {ctx_speaker}
Text: {ctx_text}

Target turn to evaluate:
Turn ID: {target_turn_id}
Speaker: {target_speaker}
Text: {target_text}

If the target turn contains a claim, output:
```json
{{
  "verdict": "claim",
  "turn_id": "{target_turn_id}",
  "speaker": "{target_speaker}",
  "type": "position" | "prediction" | "causal" | "evaluative" | "contested fact",
  "quote": "<verbatim quote>",
  "claim": "<statement of claim>",
  "offset": 0
}}
```

If the target turn does not contain a claim, output:
```json
{{
  "verdict": "exclusion",
  "turn_id": "{target_turn_id}",
  "gate_failed": "gate_1",
  "reason": "No claim found"
}}
```
<end_of_turn>
<start_of_turn>model
"""
    return prompt


def parse_model_verdict(
    raw_output: str,
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parses model output JSON into a standardized verdict dictionary.

    Enforces zero validators: does not suppress, discard, or rewrite model output.
    Computes diagnostic fields: verbatim quote match, context quote leak check, offset.
    """
    turn_id = target_turn["turn_id"]
    target_text = target_turn.get("text", "")
    ctx_text = context_turn.get("text", "") if context_turn else ""

    # Extract JSON string from code block or regex
    clean_json = raw_output.strip()
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if json_match:
        clean_json = json_match.group(1)
    else:
        obj_match = re.search(r"(\{.*\})", raw_output, re.DOTALL)
        if obj_match:
            clean_json = obj_match.group(1)

    parsed_obj: dict[str, Any] = {}
    try:
        parsed_obj = json.loads(clean_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: attempt to salvage verdict and gate_failed if JSON was slightly malformed
        verdict = "claim" if '"verdict": "claim"' in raw_output else "exclusion"
        gate = "gate_1"
        for g in ["gate_1", "gate_2", "gate_3", "gate_4"]:
            if g in raw_output:
                gate = g
                break
        parsed_obj = {
            "verdict": verdict,
            "turn_id": turn_id,
            "gate_failed": gate,
            "reason": f"Malformed JSON parsed from model: {raw_output[:120]}",
        }

    # Normalize verdict
    verdict = parsed_obj.get("verdict", "exclusion").lower()
    if verdict not in ("claim", "exclusion"):
        verdict = "claim" if "claim" in verdict else "exclusion"

    if verdict == "claim":
        quote = str(parsed_obj.get("quote", "")).strip()
        claim_text = str(parsed_obj.get("claim", "")).strip()
        claim_type = str(parsed_obj.get("type", "position")).lower()
        speaker = str(parsed_obj.get("speaker", target_turn.get("speaker_label", "")))

        # Verbatim resolution checks
        quote_in_target = bool(quote and quote in target_text)
        quote_in_context = bool(quote and ctx_text and quote in ctx_text)
        resolves_to_context_only = bool(quote and (not quote_in_target) and quote_in_context)

        offset = target_text.find(quote) if quote_in_target else int(parsed_obj.get("offset", 0))

        return {
            "turn_id": turn_id,
            "verdict": "claim",
            "speaker": speaker,
            "type": claim_type,
            "quote": quote,
            "claim": claim_text,
            "offset": offset,
            "quote_resolves_verbatim": quote_in_target,
            "quote_resolves_to_context_only": resolves_to_context_only,
            "raw_output": raw_output.strip(),
        }
    else:
        # Exclusion
        gate_raw = str(parsed_obj.get("gate_failed", "gate_1")).lower()
        # Normalize gate string: e.g. "gate 1" -> "gate_1"
        gate_match = re.search(r"gate[_\s]?([1-4])", gate_raw)
        if gate_match:
            gate_failed = f"gate_{gate_match.group(1)}"
        else:
            gate_failed = "gate_1"

        reason = str(parsed_obj.get("reason", "Excluded by rubric gate"))

        return {
            "turn_id": turn_id,
            "verdict": "exclusion",
            "gate_failed": gate_failed,
            "reason": reason,
            "raw_output": raw_output.strip(),
        }


def evaluate_against_gold(
    extracted_verdicts: list[dict[str, Any]],
    gold_data: dict[str, Any],
    turns_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Computes precision, recall, confusion matrix, gate distributions, and quote resolutions."""
    gold_verdicts = {v["turn_id"]: v for v in gold_data["verdicts"]}
    turns_by_id = {t["turn_id"]: t for t in turns_data}

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    disagreements = []
    gate_counts_model = {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0}
    gate_counts_gold = gold_data.get("gate_failure_counts", {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0})

    verbatim_quote_matches = 0
    total_model_claims = 0
    context_leak_quotes = 0

    for ext in extracted_verdicts:
        tid = ext["turn_id"]
        gold_entry = gold_verdicts.get(tid)
        if not gold_entry:
            continue

        pred_verdict = ext["verdict"]
        gold_verdict = gold_entry["verdict"]

        if pred_verdict == "claim":
            total_model_claims += 1
            if ext.get("quote_resolves_verbatim", False):
                verbatim_quote_matches += 1
            if ext.get("quote_resolves_to_context_only", False):
                context_leak_quotes += 1

            if gold_verdict == "claim":
                tp += 1
            else:
                fp += 1
                disagreements.append({
                    "turn_id": tid,
                    "type": "false_positive",
                    "speaker": turns_by_id.get(tid, {}).get("speaker_label", ""),
                    "model_verdict": "claim",
                    "gold_verdict": "exclusion",
                    "gold_gate": gold_entry.get("gate_failed", ""),
                    "model_quote": ext.get("quote", ""),
                    "model_claim": ext.get("claim", ""),
                    "turn_text": turns_by_id.get(tid, {}).get("text", "")[:150],
                })
        else:
            # Model predicted exclusion
            gate = ext.get("gate_failed", "gate_1")
            if gate in gate_counts_model:
                gate_counts_model[gate] += 1
            else:
                gate_counts_model["gate_1"] += 1

            if gold_verdict == "exclusion":
                tn += 1
            else:
                fn += 1
                disagreements.append({
                    "turn_id": tid,
                    "type": "false_negative",
                    "speaker": turns_by_id.get(tid, {}).get("speaker_label", ""),
                    "model_verdict": "exclusion",
                    "model_gate": ext.get("gate_failed", ""),
                    "model_reason": ext.get("reason", ""),
                    "gold_verdict": "claim",
                    "gold_quote": gold_entry.get("quote", ""),
                    "gold_claim": gold_entry.get("claim", ""),
                    "turn_text": turns_by_id.get(tid, {}).get("text", "")[:150],
                })

    total = tp + fp + tn + fn
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    verbatim_quote_rate = (verbatim_quote_matches / total_model_claims * 100.0) if total_model_claims > 0 else 100.0

    gate_rates_model = {
        k: round(v / total * 100.0, 2) if total > 0 else 0.0
        for k, v in gate_counts_model.items()
    }
    gate_rates_gold = {
        k: round(v / total * 100.0, 2) if total > 0 else 0.0
        for k, v in gate_counts_gold.items()
    }

    return {
        "total_turns": total,
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        },
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "precision_pct": round(precision * 100.0, 2),
        "recall_pct": round(recall * 100.0, 2),
        "f1_pct": round(f1 * 100.0, 2),
        "gold_claims_count": tp + fn,
        "model_claims_count": total_model_claims,
        "verbatim_quote_matches": verbatim_quote_matches,
        "verbatim_quote_rate": round(verbatim_quote_rate, 2),
        "context_leak_quotes": context_leak_quotes,
        "gate_failure_counts_model": gate_counts_model,
        "gate_failure_rates_model": gate_rates_model,
        "gate_failure_counts_gold": gate_counts_gold,
        "gate_failure_rates_gold": gate_rates_gold,
        "disagreements_count": len(disagreements),
        "disagreements": disagreements,
        "validators_added": VALIDATORS_ADDED,
    }


class ModelExtractor:
    """Extractor runtime running local MLX inference."""

    def __init__(self, model_id: str = MODEL_ID) -> None:
        from mlx_lm import generate, load
        self.model_id = model_id
        loaded = load(model_id)
        self.model = loaded[0]
        self.tokenizer = loaded[1]
        self.generate_fn = generate

    def extract_turn(
        self,
        prompt: str,
        target_turn: dict[str, Any],
        context_turn: dict[str, Any] | None = None,
        max_tokens: int = 150,
    ) -> dict[str, Any]:
        """Runs generation for a single turn and parses verdict."""
        raw_output = self.generate_fn(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
        )
        return parse_model_verdict(raw_output, target_turn, context_turn)


def run_episode_extraction(
    source_id: str = "00251a80c868f535",
    is_falsification: bool = False,
    max_turns: int | None = None,
    progress_callback: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Runs extraction across all turns of an episode and saves the artifact."""
    transcript_file = DEFAULT_TRANSCRIPT_DIR / f"{source_id}.json"
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_file}")

    with open(transcript_file, "r", encoding="utf-8") as f:
        t_data = json.load(f)

    turns = t_data["turns"]
    if max_turns is not None:
        turns = turns[:max_turns]

    rubric_text = load_rubric()
    extractor = ModelExtractor()

    verdicts: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for idx, target in enumerate(turns):
        context = turns[idx - 1] if idx > 0 else None
        if is_falsification:
            prompt = build_falsification_prompt(target, context)
        else:
            prompt = build_rubric_prompt(rubric_text, target, context)

        verdict = extractor.extract_turn(prompt, target, context)
        verdicts.append(verdict)

        if progress_callback:
            progress_callback(idx + 1, len(turns), verdict)

    elapsed = time.perf_counter() - t0

    # Evaluate against gold if available
    gold_file = DEFAULT_GOLD_DIR / f"{source_id}.json"
    metrics = {}
    if gold_file.exists():
        with open(gold_file, "r", encoding="utf-8") as f:
            gold_data = json.load(f)
        metrics = evaluate_against_gold(verdicts, gold_data, turns)

    prompt_version = PROMPT_VERSION_FALSIFICATION if is_falsification else PROMPT_VERSION_RUBRIC
    rubric_commit = gold_data.get("rubric_commit", RUBRIC_COMMIT) if gold_file.exists() else RUBRIC_COMMIT

    result = {
        "source_id": source_id,
        "is_falsification": is_falsification,
        "model_id": MODEL_ID,
        "quantisation": QUANTISATION,
        "runtime": RUNTIME,
        "prompt_version": prompt_version,
        "rubric_commit": rubric_commit,
        "turns_processed": len(verdicts),
        "total_turns": len(turns),
        "elapsed_seconds": round(elapsed, 2),
        "validators_added": VALIDATORS_ADDED,
        "metrics": metrics,
        "verdicts": verdicts,
    }

    # Save artifact
    DEFAULT_EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "falsification" if is_falsification else "rubric"
    out_file = DEFAULT_EXTRACTION_DIR / f"{suffix}_extraction_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result
