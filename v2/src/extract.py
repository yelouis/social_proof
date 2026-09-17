"""Claim extraction against the written claim rubric.

Implements B3 from v2/docs/agent_execution_guide.md §7.
Zero post-processing validators: runs the rubric alone and measures it.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Standing requirement: validators added = 1 (C2 Quote Validation Guard)
VALIDATORS_ADDED: int = 1
MAX_UNPARSEABLE_RATE: float = 0.05


class UnparseableRateError(ValueError):
    """Raised when the rate of unparseable model generations exceeds the allowable threshold."""


ROOT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT_DIR.parent
DEFAULT_RUBRIC_PATH = ROOT_DIR / "docs" / "design_claim_rubric.md"
DEFAULT_AXES_PATH = ROOT_DIR / "docs" / "design_claim_axes.md"
DEFAULT_TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
DEFAULT_GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
DEFAULT_EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"
DEFAULT_PROMPTS_DIR = ROOT_DIR / "prompts"
DEFAULT_PROMPT_CLAIM_PATH = DEFAULT_PROMPTS_DIR / "extract_claim.md"
DEFAULT_PROMPT_FALSIFY_PATH = DEFAULT_PROMPTS_DIR / "extract_falsify.md"
DEFAULT_PROMPT_SCORE_AXES_PATH = DEFAULT_PROMPTS_DIR / "score_axes.md"
MODEL_ID = "mlx-community/gemma-2-2b-it-4bit"
DEFAULT_SCORING_MODEL_ID = "mlx-community/GLM-4-32B-0414-4bit"


def get_rubric_commit(rubric_path: Path = DEFAULT_RUBRIC_PATH) -> str:
    """Computes the git short commit hash of the rubric file at run time."""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", str(rubric_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        commit = res.stdout.strip()
        if commit:
            return commit
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"


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


def load_prompt_template(path: Path | str) -> str:
    """Loads a prompt template file verbatim."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def format_context_turn(context_turn: dict[str, Any] | None, is_falsification: bool = False) -> str:
    """Formats preceding context turn block."""
    ctx_speaker = context_turn.get("speaker_label", "None") if context_turn else "None"
    ctx_text = context_turn.get("text", "None") if context_turn else "None"
    ctx_turn_id = context_turn.get("turn_id", "None") if context_turn else "None"
    if is_falsification:
        return f"Context turn (preceding turn {ctx_turn_id}):\nSpeaker: {ctx_speaker}\nText: {ctx_text}"
    return (
        f"Context turn (preceding turn {ctx_turn_id}, for reference only — DO NOT quote or extract from context):\n"
        f"Speaker: {ctx_speaker}\n"
        f"Text: {ctx_text}"
    )


def format_target_turn(target_turn: dict[str, Any]) -> str:
    """Formats target turn block to evaluate."""
    target_turn_id = target_turn["turn_id"]
    target_speaker = target_turn.get("speaker_label", "unknown")
    target_text = target_turn.get("text", "")
    return f"Target turn to evaluate:\nTurn ID: {target_turn_id}\nSpeaker: {target_speaker}\nText: {target_text}"


def build_rubric_prompt(
    rubric_text: str,
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
    template_path: Path | str = DEFAULT_PROMPT_CLAIM_PATH,
) -> str:
    """Builds the extraction prompt interpolating rubric and turn blocks into template."""
    template = load_prompt_template(template_path)
    ctx_block = format_context_turn(context_turn, is_falsification=False)
    target_block = format_target_turn(target_turn)
    target_turn_id = str(target_turn["turn_id"])
    target_speaker = str(target_turn.get("speaker_label", "unknown"))

    return (
        template.replace("{rubric}", rubric_text)
        .replace("{context_turn}", ctx_block)
        .replace("{target_turn}", target_block)
        .replace("{target_turn_id}", target_turn_id)
        .replace("{target_speaker}", target_speaker)
    )


def build_falsification_prompt(
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
    template_path: Path | str = DEFAULT_PROMPT_FALSIFY_PATH,
) -> str:
    """Builds the falsification prompt interpolating turn blocks into stripped template."""
    template = load_prompt_template(template_path)
    ctx_block = format_context_turn(context_turn, is_falsification=True)
    target_block = format_target_turn(target_turn)
    target_turn_id = str(target_turn["turn_id"])
    target_speaker = str(target_turn.get("speaker_label", "unknown"))

    return (
        template.replace("{context_turn}", ctx_block)
        .replace("{target_turn}", target_block)
        .replace("{target_turn_id}", target_turn_id)
        .replace("{target_speaker}", target_speaker)
    )


def load_axes(path: Path | str = DEFAULT_AXES_PATH) -> str:
    """Loads the axes markdown file verbatim."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_score_axes_prompt(
    axes_text: str,
    target_turn: dict[str, Any],
    quote: str,
    claim: str,
    template_path: Path | str = DEFAULT_PROMPT_SCORE_AXES_PATH,
) -> str:
    """Builds the Pass 2 scoring prompt interpolating axes and candidate claim into template."""
    template = load_prompt_template(template_path)
    target_turn_id = str(target_turn["turn_id"])
    target_speaker = str(target_turn.get("speaker_label", target_turn.get("speaker", "unknown")))
    target_text = str(target_turn.get("text", ""))

    return (
        template.replace("{axes}", axes_text)
        .replace("{turn_id}", target_turn_id)
        .replace("{speaker}", target_speaker)
        .replace("{turn_text}", target_text)
        .replace("{quote}", quote)
        .replace("{claim}", claim)
    )


AXIS_NAMES: list[str] = [
    "voice",
    "target",
    "propositionality",
    "contestability",
    "typing",
    "decontextualisation",
    "fidelity",
    "granularity",
]

SPEAKER_PANEL_AXES: list[str] = [
    "voice",
    "target",
    "propositionality",
    "contestability",
    "typing",
]

EXTRACTION_PANEL_AXES: list[str] = [
    "decontextualisation",
    "fidelity",
    "granularity",
]


def parse_axes_verdict(raw_output: str, turn_id: str) -> dict[str, Any]:
    """Parses model output JSON for Pass 2 quality axis scoring.

    Extracts scores for all 8 axes (0, 1, or 2) and their one-line reasons.
    If any axis is missing or output is unparseable JSON, flags parse_status='unparseable'.
    """
    clean_json = raw_output.strip()
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if json_match:
        clean_json = json_match.group(1)
    else:
        obj_match = re.search(r"(\{.*\})", raw_output, re.DOTALL)
        if obj_match:
            clean_json = obj_match.group(1)

    parsed_obj: dict[str, Any] = {}
    is_valid_json = False
    try:
        loaded = json.loads(clean_json)
        if isinstance(loaded, dict):
            parsed_obj = loaded
            is_valid_json = True
    except (json.JSONDecodeError, ValueError, TypeError):
        is_valid_json = False

    if not is_valid_json:
        # Regex fallback: try to extract all 8 axes and reasons directly from raw_output
        extracted_scores: dict[str, int] = {}
        extracted_reasons: dict[str, str] = {}
        for axis in AXIS_NAMES:
            s_match = re.search(rf'"{axis}"\s*:\s*([0-2])\b', raw_output)
            if not s_match:
                break
            extracted_scores[axis] = int(s_match.group(1))
            r_match = re.search(rf'"{axis}_reason"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"?', raw_output)
            extracted_reasons[f"{axis}_reason"] = r_match.group(1).replace('\\"', '"') if r_match else ""

        if len(extracted_scores) == len(AXIS_NAMES):
            return {
                "turn_id": turn_id,
                "parse_status": "ok",
                "scores": extracted_scores,
                "reasons": extracted_reasons,
                "raw_output": raw_output.strip(),
            }

        return {
            "turn_id": turn_id,
            "parse_status": "unparseable",
            "scores": {},
            "reasons": {},
            "raw_output": raw_output.strip(),
        }

    scores: dict[str, int] = {}
    reasons: dict[str, str] = {}

    for axis in AXIS_NAMES:
        if axis not in parsed_obj:
            return {
                "turn_id": turn_id,
                "parse_status": "unparseable",
                "scores": {},
                "reasons": {},
                "raw_output": raw_output.strip(),
            }
        val = parsed_obj[axis]
        try:
            int_val = int(val)
        except (ValueError, TypeError):
            return {
                "turn_id": turn_id,
                "parse_status": "unparseable",
                "scores": {},
                "reasons": {},
                "raw_output": raw_output.strip(),
            }
        if int_val not in (0, 1, 2):
            return {
                "turn_id": turn_id,
                "parse_status": "unparseable",
                "scores": {},
                "reasons": {},
                "raw_output": raw_output.strip(),
            }
        scores[axis] = int_val
        reason_key = f"{axis}_reason"
        reasons[reason_key] = str(parsed_obj.get(reason_key, parsed_obj.get("reason", "")))

    return {
        "turn_id": turn_id,
        "parse_status": "ok",
        "scores": scores,
        "reasons": reasons,
        "raw_output": raw_output.strip(),
    }


def compute_mechanical_proxies(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes the three mechanical proxies defined in C4 / C5:
    1. Unresolved referents: claim opens with an unbound referent
       ('it', 'this', 'they', 'the individual', 'the speaker').
       Measured on E287: 6 of 111 (5.4%) (turns t0010, t0072, t0111, t0172, t0238, t0359).
    2. Compound claims over 35 words: len(claim.split()) > 35.
       Measured on E287: 3 of 111 (2.7%) (turns t0016, t0255, t0389).
    3. Claims that restate their quote near-verbatim: difflib ratio >= 0.83.
       Measured on E287: 39 of 111 (35.1%).
    """
    total = len(claims)
    if total == 0:
        return {
            "total_claims": 0,
            "unresolved_referents": {"count": 0, "rate_pct": 0.0, "turn_ids": []},
            "compound_claims": {"count": 0, "rate_pct": 0.0, "turn_ids": []},
            "near_verbatim_quotes": {"count": 0, "rate_pct": 0.0, "turn_ids": []},
        }

    ref_pattern = re.compile(r"^(it\b|this\b|they\b|the individual\b|the speaker\b)", re.IGNORECASE)

    unresolved_tids: list[str] = []
    compound_tids: list[str] = []
    near_verbatim_tids: list[str] = []

    for c in claims:
        tid = str(c.get("turn_id", ""))
        c_text = str(c.get("claim", "")).strip()
        q_text = str(c.get("quote", "")).strip()

        if ref_pattern.search(c_text):
            unresolved_tids.append(tid)

        if len(c_text.split()) > 35:
            compound_tids.append(tid)

        ratio = difflib.SequenceMatcher(None, q_text.lower(), c_text.lower()).ratio()
        if ratio >= 0.83:
            near_verbatim_tids.append(tid)

    return {
        "total_claims": total,
        "unresolved_referents": {
            "count": len(unresolved_tids),
            "rate_pct": round(len(unresolved_tids) / total * 100.0, 1),
            "turn_ids": unresolved_tids,
        },
        "compound_claims": {
            "count": len(compound_tids),
            "rate_pct": round(len(compound_tids) / total * 100.0, 1),
            "turn_ids": compound_tids,
        },
        "near_verbatim_quotes": {
            "count": len(near_verbatim_tids),
            "rate_pct": round(len(near_verbatim_tids) / total * 100.0, 1),
            "turn_ids": near_verbatim_tids,
        },
    }


def generate_episode_axes_report(
    scored_claims: list[dict[str, Any]],
    total_turns: int,
    model_id: str,
    scoring_model_id: str,
    episode_id: str = "00251a80c868f535",
    axes_path: Path = DEFAULT_AXES_PATH,
    prompt_path: Path = DEFAULT_PROMPT_SCORE_AXES_PATH,
) -> dict[str, Any]:
    """Generates the Episode Claim Quality Profile report across 8 axes (§4).

    Strict structural requirements:
    1. Speaker panel and Extraction panel reported separately, NEVER blended into a composite scalar score.
    2. Distribution (counts and percentages of 0, 1, 2) reported for each axis.
    3. Every 0-score resolvable by turn id.
    4. Mechanical proxies reported beside model Decontextualisation, Granularity and Fidelity scores with overlap.
    5. Asserts scoring_model_id != model_id (independent scoring model requirement).
    """
    if scoring_model_id == model_id:
        raise ValueError(
            f"Extraction panel must be scored by an independent model distinct from the extractor. "
            f"Got scoring_model_id == model_id ({model_id})."
        )

    claims_count = len(scored_claims)
    claim_density_pct = round(claims_count / total_turns * 100.0, 1) if total_turns > 0 else 0.0

    # Calculate distributions per axis
    axis_reports: dict[str, dict[str, Any]] = {}
    for axis in AXIS_NAMES:
        scores_list: list[int] = []
        zeros_tids: list[str] = []
        for c in scored_claims:
            tid = str(c.get("turn_id", ""))
            s = c.get("scores", {}).get(axis)
            if s is not None:
                scores_list.append(s)
                if s == 0:
                    zeros_tids.append(tid)

        count = len(scores_list)
        count_0 = sum(1 for s in scores_list if s == 0)
        count_1 = sum(1 for s in scores_list if s == 1)
        count_2 = sum(1 for s in scores_list if s == 2)
        mean_score = round(sum(scores_list) / count, 2) if count > 0 else 0.0
        pct_0 = round(count_0 / count * 100.0, 1) if count > 0 else 0.0
        pct_1 = round(count_1 / count * 100.0, 1) if count > 0 else 0.0
        pct_2 = round(count_2 / count * 100.0, 1) if count > 0 else 0.0

        has_zero_variance = bool(count > 0 and (count_0 == count or count_1 == count or count_2 == count))

        axis_reports[axis] = {
            "axis": axis,
            "mean": mean_score,
            "counts": {"0": count_0, "1": count_1, "2": count_2},
            "percentages": {"0": pct_0, "1": pct_1, "2": pct_2},
            "zero_scores_count": len(zeros_tids),
            "zero_scores_turn_ids": zeros_tids,
            "has_zero_variance": has_zero_variance,
        }

    # Mechanical proxies
    proxies = compute_mechanical_proxies(scored_claims)

    # Overlaps
    decontext_zeros = set(axis_reports["decontextualisation"]["zero_scores_turn_ids"])
    proxy_ref_tids = set(proxies["unresolved_referents"]["turn_ids"])
    ref_overlap = sorted(decontext_zeros & proxy_ref_tids)

    granularity_zeros = set(axis_reports["granularity"]["zero_scores_turn_ids"])
    proxy_compound_tids = set(proxies["compound_claims"]["turn_ids"])
    compound_overlap = sorted(granularity_zeros & proxy_compound_tids)

    near_verbatim_tids = proxies["near_verbatim_quotes"]["turn_ids"]
    fidelity_map: dict[str, int | None] = {}
    for tid in near_verbatim_tids:
        sc = next((c for c in scored_claims if c.get("turn_id") == tid), None)
        fidelity_map[tid] = sc.get("scores", {}).get("fidelity") if sc else None

    # Provenance
    axes_text = load_axes(axes_path)
    axes_content_hash = hashlib.sha256(axes_text.encode("utf-8")).hexdigest()
    axes_commit = get_rubric_commit(axes_path)

    prompt_text = load_prompt_template(prompt_path)
    prompt_content_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    prompt_version = f"{prompt_path.stem}:{prompt_content_hash[:12]}"

    speaker_panel = {axis: axis_reports[axis] for axis in SPEAKER_PANEL_AXES}
    extraction_panel = {axis: axis_reports[axis] for axis in EXTRACTION_PANEL_AXES}

    report = {
        "episode_id": episode_id,
        "claims_found": claims_count,
        "total_turns": total_turns,
        "claim_density_pct": claim_density_pct,
        "provenance": {
            "model_id": model_id,
            "scoring_model_id": scoring_model_id,
            "axes_commit": axes_commit,
            "axes_path": str(axes_path.relative_to(REPO_ROOT)),
            "axes_content_hash": axes_content_hash,
            "prompt_version": prompt_version,
            "prompt_path": str(prompt_path.relative_to(REPO_ROOT)),
            "prompt_content_hash": prompt_content_hash,
        },
        "speaker_panel": speaker_panel,
        "extraction_panel": extraction_panel,
        "mechanical_proxies": proxies,
        "proxy_cross_checks": {
            "decontextualisation": {
                "proxy_unresolved_referents_count": proxies["unresolved_referents"]["count"],
                "proxy_turn_ids": proxies["unresolved_referents"]["turn_ids"],
                "model_zero_count": len(decontext_zeros),
                "model_zero_turn_ids": sorted(decontext_zeros),
                "overlap_count": len(ref_overlap),
                "overlap_turn_ids": ref_overlap,
                "overlap_rate_pct": round(len(ref_overlap) / len(proxy_ref_tids) * 100.0, 1) if proxy_ref_tids else 0.0,
            },
            "granularity": {
                "proxy_compound_claims_count": proxies["compound_claims"]["count"],
                "proxy_turn_ids": proxies["compound_claims"]["turn_ids"],
                "model_zero_count": len(granularity_zeros),
                "model_zero_turn_ids": sorted(granularity_zeros),
                "overlap_count": len(compound_overlap),
                "overlap_turn_ids": compound_overlap,
                "overlap_rate_pct": round(len(compound_overlap) / len(proxy_compound_tids) * 100.0, 1) if proxy_compound_tids else 0.0,
            },
            "fidelity": {
                "near_verbatim_quotes_count": proxies["near_verbatim_quotes"]["count"],
                "near_verbatim_turn_ids": near_verbatim_tids,
                "fidelity_scores_for_near_verbatim": fidelity_map,
            },
        },
    }

    # Explicit assertion that NO composite scalar score exists
    assert "composite_score" not in report
    assert "composite_quality" not in report
    assert "quality_score" not in report

    return report


def parse_model_verdict(
    raw_output: str,
    target_turn: dict[str, Any],
    context_turn: dict[str, Any] | None = None,
    apply_validator: bool = True,
) -> dict[str, Any]:
    """Parses model output JSON into a standardized verdict dictionary.

    Under C2 (VALIDATORS_ADDED=1), applies the Quote Validation Guard:
    - Guard 1: Empty quote payloads are rejected as exclusions (gate_4).
    - Guard 2: Quotes that do not resolve as a verbatim substring in target turn are rejected
      (context leaks -> gate_1, non-verbatim / hallucinations -> gate_4).
    Emitted claims are guaranteed to have a non-empty quote that resolves verbatim in the target turn.
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
    is_valid_json = False
    try:
        loaded = json.loads(clean_json)
        if isinstance(loaded, dict) and "verdict" in loaded:
            v_raw = str(loaded["verdict"]).lower().strip()
            if "claim" in v_raw or "exclusion" in v_raw:
                parsed_obj = loaded
                is_valid_json = True
    except (json.JSONDecodeError, ValueError, TypeError):
        is_valid_json = False

    if not is_valid_json:
        return {
            "turn_id": turn_id,
            "verdict": "unparseable",
            "parse_status": "unparseable",
            "gate_failed": None,
            "reason": f"Unparseable output from model: {raw_output[:120]}",
            "raw_output": raw_output.strip(),
        }

    # Normalize verdict
    verdict = parsed_obj.get("verdict", "exclusion").lower().strip()
    if "claim" in verdict:
        verdict = "claim"
    else:
        verdict = "exclusion"

    if verdict == "claim":
        quote = str(parsed_obj.get("quote", "")).strip()
        claim_text = str(parsed_obj.get("claim", "")).strip()
        claim_type = str(parsed_obj.get("type", "position")).lower()
        speaker = str(parsed_obj.get("speaker", target_turn.get("speaker_label", "")))

        # Verbatim resolution checks
        quote_in_target = bool(quote and quote in target_text)
        quote_in_context = bool(quote and ctx_text and quote in ctx_text)
        resolves_to_context_only = bool(quote and (not quote_in_target) and quote_in_context)

        # C2 Quote Validation Guard (VALIDATORS_ADDED = 1)
        if apply_validator:
            # Guard 1: Empty quote
            if not quote:
                return {
                    "turn_id": turn_id,
                    "verdict": "exclusion",
                    "parse_status": "ok",
                    "gate_failed": "gate_4",
                    "reason": "Rejected by quote validator: empty quote payload",
                    "validator_rejected": True,
                    "rejection_reason": "empty_quote",
                    "quote": "",
                    "claim": claim_text,
                    "offset": 0,
                    "quote_resolves_verbatim": False,
                    "quote_resolves_to_context_only": False,
                    "raw_output": raw_output.strip(),
                }

            # Guard 2: Quote does not resolve verbatim as a substring of target turn
            if not quote_in_target:
                gate_failed = "gate_1" if resolves_to_context_only else "gate_4"
                rej_reason = "context_leak" if resolves_to_context_only else "non_verbatim"
                detail = "quote resolves to context turn only (context leak)" if resolves_to_context_only else "quote does not resolve as a substring of target turn"
                return {
                    "turn_id": turn_id,
                    "verdict": "exclusion",
                    "parse_status": "ok",
                    "gate_failed": gate_failed,
                    "reason": f"Rejected by quote validator: {detail}",
                    "validator_rejected": True,
                    "rejection_reason": rej_reason,
                    "quote": quote,
                    "claim": claim_text,
                    "offset": 0,
                    "quote_resolves_verbatim": False,
                    "quote_resolves_to_context_only": resolves_to_context_only,
                    "raw_output": raw_output.strip(),
                }

        offset = target_text.find(quote) if quote_in_target else int(parsed_obj.get("offset", 0))

        return {
            "turn_id": turn_id,
            "verdict": "claim",
            "parse_status": "ok",
            "speaker": speaker,
            "type": claim_type,
            "quote": quote,
            "claim": claim_text,
            "offset": offset,
            "quote_resolves_verbatim": quote_in_target,
            "quote_resolves_to_context_only": resolves_to_context_only,
            "validator_rejected": False,
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
            "parse_status": "ok",
            "gate_failed": gate_failed,
            "reason": reason,
            "raw_output": raw_output.strip(),
        }


def evaluate_against_gold(
    extracted_verdicts: list[dict[str, Any]],
    gold_data: dict[str, Any],
    turns_data: list[dict[str, Any]],
    max_unparseable_rate: float = MAX_UNPARSEABLE_RATE,
    raise_on_high_unparseable: bool = False,
) -> dict[str, Any]:
    """Computes precision, recall, confusion matrix, gate distributions, quote resolutions,

    and parse status integrity metrics.

    Under C3:
    - Excludes unparseable turns from precision, recall, and confusion matrix.
    - If unparseable rate exceeds max_unparseable_rate (default 5%):
      fails loudly by raising UnparseableRateError if raise_on_high_unparseable is True,
      or returning a result marked is_valid=False with confusion_matrix=None.
    """
    gold_verdicts = {v["turn_id"]: v for v in gold_data["verdicts"]}
    turns_by_id = {t["turn_id"]: t for t in turns_data}

    total_turns = len(extracted_verdicts)
    unparseable_count = sum(
        1 for ext in extracted_verdicts
        if ext.get("parse_status") == "unparseable" or ext.get("verdict") == "unparseable"
    )
    unparseable_rate = (unparseable_count / total_turns) if total_turns > 0 else 0.0
    unparseable_rate_pct = round(unparseable_rate * 100.0, 2)

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    disagreements: list[dict[str, Any]] = []
    gate_counts_model = {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0}
    gate_counts_gold = gold_data.get("gate_failure_counts", {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0})

    verbatim_quote_matches = 0
    total_model_claims = 0
    context_leak_quotes = 0
    guard_rejections = {
        "empty_quote": 0,
        "non_verbatim": 0,
        "context_leak": 0,
        "total": 0,
    }

    for ext in extracted_verdicts:
        if ext.get("validator_rejected", False):
            guard_rejections["total"] += 1
            rej_reason = str(ext.get("rejection_reason", "empty_quote"))
            if rej_reason in guard_rejections:
                guard_rejections[rej_reason] += 1

        tid = ext["turn_id"]
        gold_entry = gold_verdicts.get(tid)
        if not gold_entry:
            continue

        # C3: Exclude unparseable turns from precision, recall, and confusion matrix
        if ext.get("parse_status") == "unparseable" or ext.get("verdict") == "unparseable":
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

    parseable_turns = tp + fp + tn + fn
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    verbatim_quote_rate = (verbatim_quote_matches / total_model_claims * 100.0) if total_model_claims > 0 else 100.0

    gate_rates_model = {
        k: round(v / total_turns * 100.0, 2) if total_turns > 0 else 0.0
        for k, v in gate_counts_model.items()
    }
    gate_rates_gold = {
        k: round(v / total_turns * 100.0, 2) if total_turns > 0 else 0.0
        for k, v in gate_counts_gold.items()
    }
    guard_rejection_rates = {
        k: round(v / total_turns * 100.0, 2) if total_turns > 0 else 0.0
        for k, v in guard_rejections.items()
    }

    # High unparseable rate check (> 5%)
    if unparseable_rate > max_unparseable_rate:
        err_msg = (
            f"Unparseable generation rate {unparseable_rate_pct:.2f}% ({unparseable_count}/{total_turns}) "
            f"exceeds allowable threshold of {max_unparseable_rate * 100.0:.1f}%. "
            f"Run marked invalid; confusion matrix suppressed."
        )
        if raise_on_high_unparseable:
            raise UnparseableRateError(err_msg)

        return {
            "is_valid": False,
            "status": "invalid",
            "error": err_msg,
            "total_turns": total_turns,
            "parseable_turns": parseable_turns,
            "unparseable_count": unparseable_count,
            "unparseable_rate": round(unparseable_rate, 4),
            "unparseable_rate_pct": unparseable_rate_pct,
            "confusion_matrix": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "precision_pct": None,
            "recall_pct": None,
            "f1_pct": None,
            "gold_claims_count": sum(1 for v in gold_data.get("verdicts", []) if v.get("verdict") == "claim"),
            "model_claims_count": total_model_claims,
            "verbatim_quote_matches": verbatim_quote_matches,
            "verbatim_quote_rate": None,
            "context_leak_quotes": context_leak_quotes,
            "gate_failure_counts_model": gate_counts_model,
            "gate_failure_rates_model": gate_rates_model,
            "gate_failure_counts_gold": gate_counts_gold,
            "gate_failure_rates_gold": gate_rates_gold,
            "disagreements_count": len(disagreements),
            "disagreements": disagreements,
            "validators_added": VALIDATORS_ADDED,
            "guard_rejections": guard_rejections,
            "guard_rejection_rates": guard_rejection_rates,
        }

    return {
        "is_valid": True,
        "status": "ok",
        "total_turns": total_turns,
        "parseable_turns": parseable_turns,
        "unparseable_count": unparseable_count,
        "unparseable_rate": round(unparseable_rate, 4),
        "unparseable_rate_pct": unparseable_rate_pct,
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
        "guard_rejections": guard_rejections,
        "guard_rejection_rates": guard_rejection_rates,
    }


def rescore_extraction_artifact(
    artifact_path: Path | str,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
    max_unparseable_rate: float = MAX_UNPARSEABLE_RATE,
    raise_on_high_unparseable: bool = False,
) -> dict[str, Any]:
    """Re-scores an extraction artifact from disk, re-parsing raw outputs under current parser.

    Used for audit and verification of unparseable generation rates across historical artifacts.
    """
    path = Path(artifact_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    source_id = data.get("source_id", "00251a80c868f535")
    gold_file = gold_dir / f"{source_id}.json"
    transcript_file = transcript_dir / f"{source_id}.json"

    with open(gold_file, "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)

    turns = transcript_data["turns"]
    turns_by_id = {t["turn_id"]: t for t in turns}

    rescored_verdicts: list[dict[str, Any]] = []
    for idx, v in enumerate(data.get("verdicts", [])):
        tid = v["turn_id"]
        target = turns_by_id.get(tid, {"turn_id": tid, "text": ""})
        context = turns[idx - 1] if idx > 0 else None
        raw_output = v.get("raw_output", "")

        if "raw_output" in v:
            new_v = parse_model_verdict(raw_output, target, context, apply_validator=True)
            rescored_verdicts.append(new_v)
        else:
            rescored_verdicts.append(v)

    return evaluate_against_gold(
        rescored_verdicts,
        gold_data,
        turns,
        max_unparseable_rate=max_unparseable_rate,
        raise_on_high_unparseable=raise_on_high_unparseable,
    )


class ModelExtractor:
    """Extractor runtime running local MLX or Ollama inference."""

    def __init__(
        self,
        model_id: str = MODEL_ID,
        runtime: str = "mlx_lm",
        quantisation: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        base_url: str = "http://127.0.0.1:11434",
    ) -> None:
        self.model_id = model_id
        self.runtime = runtime
        self.temperature = temperature
        self.seed = seed
        self.base_url = base_url

        if runtime == "mlx_lm":
            from mlx_lm import generate, load
            from mlx_lm.sample_utils import make_sampler

            loaded = load(model_id, return_config=True)
            self.model = loaded[0]
            self.tokenizer = loaded[1]
            config: dict[str, Any] = loaded[2] if len(loaded) > 2 and isinstance(loaded[2], dict) else {}
            self.generate_fn = generate
            self.sampler = make_sampler(temp=temperature)

            if quantisation is not None:
                self.quantisation = quantisation
            else:
                if "quantization" in config and isinstance(config["quantization"], dict):
                    q = config["quantization"]
                    bits = q.get("bits")
                    self.quantisation = f"{bits}-bit" if bits is not None else "unknown"
                elif config.get("torch_dtype"):
                    self.quantisation = str(config["torch_dtype"])
                else:
                    self.quantisation = "unknown"
        elif runtime == "ollama":
            self.quantisation = quantisation or "Q4_K_M"
        else:
            raise ValueError(f"Unsupported runtime: {runtime}")

    def extract_turn(
        self,
        prompt: str,
        target_turn: dict[str, Any],
        context_turn: dict[str, Any] | None = None,
        max_tokens: int = 250,
    ) -> dict[str, Any]:
        """Runs generation for a single turn and parses verdict."""
        if self.runtime == "mlx_lm":
            raw_output = self.generate_fn(
                self.model,
                self.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                verbose=False,
                sampler=self.sampler,
            )
        elif self.runtime == "ollama":
            req_data: dict[str, Any] = {
                "model": self.model_id,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": max_tokens,
                },
            }
            if self.temperature > 0.0 and self.seed is not None:
                req_data["options"]["seed"] = self.seed

            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            raw_output = str(resp_data.get("response", ""))
        else:
            raise ValueError(f"Unsupported runtime: {self.runtime}")

        return parse_model_verdict(raw_output, target_turn, context_turn, apply_validator=True)


def run_episode_extraction(
    source_id: str = "00251a80c868f535",
    is_falsification: bool = False,
    max_turns: int | None = None,
    progress_callback: Callable[[int, int, dict[str, Any]], None] | None = None,
    extractor: Any | None = None,
    output_dir: Path | None = None,
    output_filename: str | None = None,
    max_tokens: int = 250,
    max_unparseable_rate: float = MAX_UNPARSEABLE_RATE,
    raise_on_high_unparseable: bool = False,
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

    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)
    active_extractor = extractor if extractor is not None else ModelExtractor()

    # Trap 31 removal (residual 3 from B7): extractor must declare non-empty model_id
    if not hasattr(active_extractor, "model_id") or not active_extractor.model_id:
        raise AttributeError("Extractor must declare a non-empty 'model_id' attribute (silent default prohibited).")

    # Decoding parameters pinned and recorded (residuals 1 & 2 from B7)
    temp = float(getattr(active_extractor, "temperature", 0.0))
    seed = getattr(active_extractor, "seed", None) if temp > 0.0 else None
    sampler = "greedy" if temp == 0.0 else f"temp_{temp}"
    tokens_val = int(max_tokens) if max_tokens is not None else 250

    decoding: dict[str, Any] = {
        "temperature": temp,
        "sampler": sampler,
        "max_tokens": tokens_val,
        "seed": seed,
    }

    verdicts: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for idx, target in enumerate(turns):
        context = turns[idx - 1] if idx > 0 else None
        if is_falsification:
            prompt = build_falsification_prompt(target, context)
        else:
            prompt = build_rubric_prompt(rubric_text, target, context)

        verdict = active_extractor.extract_turn(
            prompt, target, context, max_tokens=tokens_val
        )
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
        metrics = evaluate_against_gold(
            verdicts,
            gold_data,
            turns,
            max_unparseable_rate=max_unparseable_rate,
            raise_on_high_unparseable=raise_on_high_unparseable,
        )

    # Provenance fields off the active extractor
    model_id = str(active_extractor.model_id)
    runtime = getattr(active_extractor, "runtime", "unknown")
    quantisation = getattr(active_extractor, "quantisation", "unknown")

    # Rubric commit dynamically derived from git log of rubric file
    rubric_commit = get_rubric_commit(DEFAULT_RUBRIC_PATH)
    rubric_content_hash = hashlib.sha256(rubric_text.encode("utf-8")).hexdigest()

    prompt_file = DEFAULT_PROMPT_FALSIFY_PATH if is_falsification else DEFAULT_PROMPT_CLAIM_PATH
    prompt_content = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
    prompt_content_hash = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()
    prompt_version = f"{prompt_file.stem}:{prompt_content_hash[:12]}"

    result = {
        "source_id": source_id,
        "is_falsification": is_falsification,
        "model_id": model_id,
        "quantisation": quantisation,
        "runtime": runtime,
        "prompt_version": prompt_version,
        "prompt_path": str(prompt_file.relative_to(REPO_ROOT)),
        "prompt_content_hash": prompt_content_hash,
        "rubric_commit": rubric_commit,
        "rubric_path": str(DEFAULT_RUBRIC_PATH.relative_to(REPO_ROOT)),
        "rubric_content_hash": rubric_content_hash,
        "decoding": decoding,
        "provenance_source": "recorded",
        "turns_processed": len(verdicts),
        "total_turns": len(turns),
        "elapsed_seconds": round(elapsed, 2),
        "validators_added": VALIDATORS_ADDED,
        "metrics": metrics,
        "verdicts": verdicts,
    }

    # Save artifact
    target_dir = output_dir if output_dir is not None else DEFAULT_EXTRACTION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    if output_filename is not None:
        out_file = target_dir / output_filename
    else:
        suffix = "falsification" if is_falsification else "rubric"
        out_file = target_dir / f"{suffix}_extraction_{source_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def evaluate_consensus_against_gold(
    model_verdicts: dict[str, list[dict[str, Any]]],
    gold_data: dict[str, Any],
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Computes consensus metrics across multiple models against B2 gold set.

    Evaluates:
    - Unanimous rule (all models agree claim)
    - Majority rule (>= 2 models agree claim for 3 models)
    - Any-model rule (>= 1 model agree claim)
    """
    model_ids = list(model_verdicts.keys())
    n_models = len(model_ids)
    gold_by_id: dict[str, dict[str, Any]] = {
        v["turn_id"]: v for v in gold_data.get("verdicts", [])
    }

    def score_rule(rule_name: str, pred_is_claim_fn: Callable[[list[str]], bool]) -> dict[str, Any]:
        tp = fp = tn = fn = 0
        disagreements: list[dict[str, Any]] = []
        rule_claims = 0

        for turn in turns:
            tid = turn["turn_id"]
            gold_entry = gold_by_id.get(tid)
            if not gold_entry:
                continue
            gold_is_claim = bool(gold_entry.get("verdict") == "claim")

            # Collect model predictions for this turn
            preds: list[str] = []
            for mid in model_ids:
                m_map = {v["turn_id"]: v for v in model_verdicts[mid]}
                preds.append(m_map.get(tid, {}).get("verdict", "exclusion"))

            pred_is_claim = pred_is_claim_fn(preds)
            if pred_is_claim:
                rule_claims += 1

            if pred_is_claim and gold_is_claim:
                tp += 1
            elif pred_is_claim and not gold_is_claim:
                fp += 1
                disagreements.append({
                    "turn_id": tid,
                    "type": "false_positive",
                    "speaker": turn.get("speaker_label", ""),
                    "rule": rule_name,
                    "model_verdicts": dict(zip(model_ids, preds, strict=False)),
                    "gold_verdict": "exclusion",
                    "gold_gate": gold_entry.get("gate_failed", ""),
                    "turn_text": turn.get("text", "")[:150],
                })
            elif not pred_is_claim and not gold_is_claim:
                tn += 1
            else:
                fn += 1
                disagreements.append({
                    "turn_id": tid,
                    "type": "false_negative",
                    "speaker": turn.get("speaker_label", ""),
                    "rule": rule_name,
                    "model_verdicts": dict(zip(model_ids, preds, strict=False)),
                    "gold_verdict": "claim",
                    "gold_quote": gold_entry.get("quote", ""),
                    "gold_claim": gold_entry.get("claim", ""),
                    "turn_text": turn.get("text", "")[:150],
                })

        total = tp + fp + tn + fn
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        return {
            "rule": rule_name,
            "total_turns": total,
            "claims_count": rule_claims,
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "precision_pct": round(prec * 100.0, 2),
            "recall_pct": round(rec * 100.0, 2),
            "f1_pct": round(f1 * 100.0, 2),
            "disagreements_count": len(disagreements),
            "disagreements": disagreements,
        }

    unanimous = score_rule("unanimous", lambda preds: all(p == "claim" for p in preds))
    majority = score_rule("majority", lambda preds: sum(1 for p in preds if p == "claim") >= (n_models // 2 + 1))
    any_model = score_rule("any_model", lambda preds: any(p == "claim" for p in preds))

    # Shared false positives (all models called claim, gold says exclusion)
    shared_fps = [
        d for d in unanimous["disagreements"] if d["type"] == "false_positive"
    ]

    return {
        "models": model_ids,
        "total_turns": len(turns),
        "unanimous": unanimous,
        "majority": majority,
        "any_model": any_model,
        "shared_false_positives_count": len(shared_fps),
        "shared_false_positives": shared_fps,
    }


DEFAULT_FIXTURES_AXES_DIR: Path = REPO_ROOT / "v2" / "fixtures" / "axes"
DEFAULT_PERTURBATIONS_PATH: Path = DEFAULT_FIXTURES_AXES_DIR / "perturbations.json"


def evaluate_perturbation_results(
    perturbation_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluates the Tier 2 perturbation sensitivity property.

    Assertion (c): for each of the eight axes, perturbed items score strictly lower
    on that axis than their unperturbed originals in at least 4 of 5 pairs,
    with off-target movement reported.
    """
    by_axis: dict[str, list[dict[str, Any]]] = {ax: [] for ax in AXIS_NAMES}
    for item in perturbation_results:
        ax = item["target_axis"]
        if ax in by_axis:
            by_axis[ax].append(item)

    axis_results: dict[str, Any] = {}
    all_axes_pass = True

    total_off_target_drops = 0
    total_off_target_comparisons = 0

    for axis in AXIS_NAMES:
        pairs = by_axis[axis]
        total_pairs = len(pairs)
        target_drops = 0
        axis_off_target_drops = 0
        axis_off_target_comparisons = 0

        pair_details: list[dict[str, Any]] = []

        for p in pairs:
            orig_scores = p.get("original_scores", {})
            pert_scores = p.get("perturbed_scores", {})

            orig_val = orig_scores.get(axis)
            pert_val = pert_scores.get(axis)

            target_fell = bool(orig_val is not None and pert_val is not None and pert_val < orig_val)
            if target_fell:
                target_drops += 1

            # Check off-target movements
            off_target_changes = {}
            for other_ax in AXIS_NAMES:
                if other_ax == axis:
                    continue
                o_val = orig_scores.get(other_ax)
                p_val = pert_scores.get(other_ax)
                if o_val is not None and p_val is not None:
                    axis_off_target_comparisons += 1
                    total_off_target_comparisons += 1
                    if p_val < o_val:
                        axis_off_target_drops += 1
                        total_off_target_drops += 1
                        off_target_changes[other_ax] = {"orig": o_val, "pert": p_val}

            pair_details.append({
                "id": p.get("id"),
                "turn_id": p.get("turn_id"),
                "target_axis": axis,
                "orig_target_score": orig_val,
                "pert_target_score": pert_val,
                "target_fell": target_fell,
                "target_delta": (orig_val - pert_val) if orig_val is not None and pert_val is not None else None,
                "off_target_drops_count": len(off_target_changes),
                "off_target_changes": off_target_changes,
            })

        axis_pass = bool(target_drops >= 4 and total_pairs >= 4)
        if not axis_pass:
            all_axes_pass = False

        off_target_rate = round(axis_off_target_drops / axis_off_target_comparisons * 100.0, 1) if axis_off_target_comparisons > 0 else 0.0

        axis_results[axis] = {
            "axis": axis,
            "total_pairs": total_pairs,
            "target_drops_count": target_drops,
            "target_sensitivity_rate_pct": round(target_drops / total_pairs * 100.0, 1) if total_pairs > 0 else 0.0,
            "passes_target_threshold": axis_pass,
            "off_target_drops_count": axis_off_target_drops,
            "off_target_comparisons_count": axis_off_target_comparisons,
            "off_target_drop_rate_pct": off_target_rate,
            "pairs": pair_details,
        }

    overall_off_target_rate = round(total_off_target_drops / total_off_target_comparisons * 100.0, 1) if total_off_target_comparisons > 0 else 0.0

    return {
        "all_axes_pass": all_axes_pass,
        "axes": axis_results,
        "total_pairs_evaluated": len(perturbation_results),
        "total_off_target_drops": total_off_target_drops,
        "total_off_target_comparisons": total_off_target_comparisons,
        "overall_off_target_drop_rate_pct": overall_off_target_rate,
    }

