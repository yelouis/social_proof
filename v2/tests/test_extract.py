"""Tests for B3 claim extraction against the written claim rubric.

Verifies:
1. Rubric §2 and §3 appear verbatim in the prompt.
2. Context turn is read, never quoted from (quote provenance checks).
3. Every turn receives an explicit verdict (claim or exclusion), never silence.
4. Exactly zero post-processing validators are added.
5. Falsification prompt strips the rubric.
"""

from __future__ import annotations

import json
from typing import Any

from v2.src.extract import (
    DEFAULT_RUBRIC_PATH,
    VALIDATORS_ADDED,
    build_falsification_prompt,
    build_rubric_prompt,
    evaluate_against_gold,
    extract_rubric_sections,
    load_rubric,
    parse_model_verdict,
)


def test_validators_added_count() -> None:
    """Standing constraint: B3 had zero validators; C2 authorized exactly 1 (Quote Validation Guard)."""
    assert VALIDATORS_ADDED == 1


def test_rubric_sections_2_and_3_appear_verbatim_in_prompt() -> None:
    """Step 1 verify: assert in a test that the rubric file's §2 and §3 appear verbatim in the prompt."""
    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)
    sections = extract_rubric_sections(rubric_text)

    s2 = sections["section_2"]
    s3 = sections["section_3"]

    assert len(s2) > 500, "Section 2 text too short"
    assert len(s3) > 300, "Section 3 text too short"

    target_turn = {
        "turn_id": "test_t001",
        "speaker_label": "David Friedberg",
        "text": "Nvidia has an impenetrable moat because of CUDA.",
    }
    context_turn = {
        "turn_id": "test_t000",
        "speaker_label": "Jason Calacanis",
        "text": "Let us talk about chips.",
    }

    prompt = build_rubric_prompt(rubric_text, target_turn, context_turn)

    # Verbatim assertion: exact substring match
    assert s2 in prompt, "Rubric section 2 does not appear verbatim in prompt!"
    assert s3 in prompt, "Rubric section 3 does not appear verbatim in prompt!"


def test_context_turn_quote_provenance_check() -> None:
    """Step 2 verify: assert no emitted quote resolves to the context turn rather than the target turn."""
    target_turn = {
        "turn_id": "test_t001",
        "speaker_label": "David Friedberg",
        "text": "Academic science enforces conformity around mainstream theories.",
    }
    context_turn = {
        "turn_id": "test_t000",
        "speaker_label": "Jason Calacanis",
        "text": "Let us talk about string theory.",
    }

    # Case 1: Valid quote from target turn
    valid_output = json.dumps({
        "verdict": "claim",
        "turn_id": "test_t001",
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "Academic science enforces conformity",
        "claim": "Academic science enforces conformity.",
        "offset": 0,
    })
    verdict1 = parse_model_verdict(valid_output, target_turn, context_turn)
    assert verdict1["verdict"] == "claim"
    assert verdict1["quote_resolves_verbatim"] is True
    assert verdict1["quote_resolves_to_context_only"] is False

    # Case 2: Quote hallucinated from context turn (rejected under C2 validator)
    leak_output = json.dumps({
        "verdict": "claim",
        "turn_id": "test_t001",
        "speaker": "Jason Calacanis",
        "type": "evaluative",
        "quote": "Let us talk about string theory",
        "claim": "We should talk about string theory.",
        "offset": 0,
    })
    verdict2 = parse_model_verdict(leak_output, target_turn, context_turn)
    assert verdict2["verdict"] == "exclusion"
    assert verdict2["validator_rejected"] is True
    assert verdict2["rejection_reason"] == "context_leak"
    assert verdict2["quote_resolves_to_context_only"] is True

    # Unvalidated diagnostic mode still detects without rejecting
    verdict_unval = parse_model_verdict(leak_output, target_turn, context_turn, apply_validator=False)
    assert verdict_unval["verdict"] == "claim"
    assert verdict_unval["quote_resolves_verbatim"] is False
    assert verdict_unval["quote_resolves_to_context_only"] is True


def test_parse_model_verdict_exclusion_and_normalization() -> None:
    """Step 3 verify: model emits exclusions, not silence; handles gate normalization."""
    target_turn = {
        "turn_id": "test_t002",
        "speaker_label": "Jason Calacanis",
        "text": "A couple of tickets left.",
    }

    output = json.dumps({
        "verdict": "exclusion",
        "turn_id": "test_t002",
        "gate_failed": "Gate 2",
        "reason": "Show tickets and logistics.",
    })
    verdict = parse_model_verdict(output, target_turn)
    assert verdict["verdict"] == "exclusion"
    assert verdict["gate_failed"] == "gate_2"
    assert verdict["turn_id"] == "test_t002"


def test_parse_model_verdict_malformed_json_fallback() -> None:
    """Robustness check: unparseable output falls back to explicit exclusion rather than silence."""
    target_turn = {
        "turn_id": "test_t003",
        "speaker_label": "unknown",
        "text": "muffled noise",
    }
    raw = "I think this turn should be excluded under gate 1 because speaker is unknown."
    verdict = parse_model_verdict(raw, target_turn)
    assert verdict["verdict"] == "exclusion"
    assert verdict["gate_failed"] == "gate_1"
    assert verdict["turn_id"] == "test_t003"


def test_falsification_prompt_strips_rubric() -> None:
    """Falsification test: stripped prompt has no rubric sections."""
    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)
    sections = extract_rubric_sections(rubric_text)

    target_turn = {
        "turn_id": "test_t004",
        "speaker_label": "David Sacks",
        "text": "The leading open source models come from China.",
    }
    fals_prompt = build_falsification_prompt(target_turn)

    assert "The Claim Rubric" not in fals_prompt
    assert sections["section_2"] not in fals_prompt
    assert sections["section_3"] not in fals_prompt
    assert "You are a claim extraction tool." in fals_prompt


def test_evaluate_against_gold_confusion_matrix() -> None:
    """Verifies metrics computation against mock gold data."""
    gold_data = {
        "gate_failure_counts": {"gate_1": 2, "gate_2": 1, "gate_3": 0, "gate_4": 0},
        "verdicts": [
            {"turn_id": "t1", "verdict": "claim", "type": "causal", "quote": "quote 1", "claim": "claim 1"},
            {"turn_id": "t2", "verdict": "claim", "type": "position", "quote": "quote 2", "claim": "claim 2"},
            {"turn_id": "t3", "verdict": "exclusion", "gate_failed": "gate_1"},
            {"turn_id": "t4", "verdict": "exclusion", "gate_failed": "gate_2"},
        ],
    }
    turns_data = [
        {"turn_id": "t1", "speaker_label": "Host A", "text": "This is quote 1 here."},
        {"turn_id": "t2", "speaker_label": "Host B", "text": "This is quote 2 here."},
        {"turn_id": "t3", "speaker_label": "Host A", "text": "Banter text."},
        {"turn_id": "t4", "speaker_label": "Host B", "text": "More banter."},
    ]

    # Extracted: t1 is TP, t2 is FN (model said exclusion), t3 is TN, t4 is FP (model said claim)
    extracted: list[dict[str, Any]] = [
        {"turn_id": "t1", "verdict": "claim", "quote": "quote 1", "claim": "claim 1", "quote_resolves_verbatim": True},
        {"turn_id": "t2", "verdict": "exclusion", "gate_failed": "gate_1", "reason": "missed"},
        {"turn_id": "t3", "verdict": "exclusion", "gate_failed": "gate_1", "reason": "banter"},
        {"turn_id": "t4", "verdict": "claim", "quote": "More banter", "claim": "banter claim", "quote_resolves_verbatim": True},
    ]

    metrics = evaluate_against_gold(extracted, gold_data, turns_data)
    cm = metrics["confusion_matrix"]
    assert cm["tp"] == 1
    assert cm["fn"] == 1
    assert cm["tn"] == 1
    assert cm["fp"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["disagreements_count"] == 2
