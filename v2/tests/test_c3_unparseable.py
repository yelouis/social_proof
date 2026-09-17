"""Tests for Item C3: A generation we could not read is not a verdict.

Verifies:
1. parse_model_verdict assigns parse_status: "ok" | "unparseable".
2. Unparseable generations are NOT recorded as exclusions / gate_1.
3. evaluate_against_gold excludes unparseable turns from confusion matrix.
4. A run with > 5% unparseable rate fails loudly (raises UnparseableRateError or marks invalid with confusion_matrix=None).
5. Existing Nemotron artifact is flagged at 401/405 unparseable when re-scored, while Gemma-4-31B and GLM-4-32B score 0.
6. Template v2/prompts/extract_claim.md has offset field removed and prompt hash changed.
7. Offset continues to be computed deterministically in code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from v2.src.extract import (
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PROMPT_CLAIM_PATH,
    UnparseableRateError,
    evaluate_against_gold,
    parse_model_verdict,
    rescore_extraction_artifact,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_parse_model_verdict_records_parse_status_ok_for_valid_json() -> None:
    """Valid JSON outputs receive parse_status: 'ok' for both claims and exclusions."""
    target_turn = {
        "turn_id": "t001",
        "speaker_label": "David Friedberg",
        "text": "Academic science enforces conformity around mainstream theory.",
    }

    # Valid claim
    raw_claim = json.dumps({
        "verdict": "claim",
        "turn_id": "t001",
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "Academic science enforces conformity",
        "claim": "Academic science enforces conformity.",
    })
    res_claim = parse_model_verdict(raw_claim, target_turn)
    assert res_claim["verdict"] == "claim"
    assert res_claim["parse_status"] == "ok"
    assert res_claim["offset"] == 0

    # Valid exclusion
    raw_excl = json.dumps({
        "verdict": "exclusion",
        "turn_id": "t001",
        "gate_failed": "gate_2",
        "reason": "Show logistics.",
    })
    res_excl = parse_model_verdict(raw_excl, target_turn)
    assert res_excl["verdict"] == "exclusion"
    assert res_excl["parse_status"] == "ok"
    assert res_excl["gate_failed"] == "gate_2"


def test_parse_model_verdict_records_unparseable_without_defaulting_to_exclusion() -> None:
    """Unparseable generations receive parse_status: 'unparseable' and verdict: 'unparseable'.

    They must NOT be recorded as exclusion or gate_1.
    """
    target_turn = {
        "turn_id": "t002",
        "speaker_label": "Jason Calacanis",
        "text": "Let us discuss the latest round of inflation data.",
    }

    # Model thought in prose and never produced valid JSON
    prose_output = "I believe the speaker is discussing economic data. This fails gate 1 because it is an introductory statement."
    res = parse_model_verdict(prose_output, target_turn)

    assert res["verdict"] == "unparseable"
    assert res["parse_status"] == "unparseable"
    assert res.get("gate_failed") is None
    assert "Unparseable output from model" in res["reason"]


def test_evaluate_against_gold_excludes_unparseable_from_confusion_matrix() -> None:
    """Unparseable turns are excluded from precision, recall, and the confusion matrix."""
    gold_data = {
        "gate_failure_counts": {"gate_1": 1, "gate_2": 1, "gate_3": 0, "gate_4": 0},
        "verdicts": [
            {"turn_id": "t1", "verdict": "claim", "quote": "quote 1", "claim": "claim 1"},
            {"turn_id": "t2", "verdict": "claim", "quote": "quote 2", "claim": "claim 2"},
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

    # t1: TP, t2: unparseable (was gold claim), t3: TN, t4: FP
    extracted: list[dict[str, Any]] = [
        {"turn_id": "t1", "verdict": "claim", "parse_status": "ok", "quote": "quote 1", "claim": "claim 1", "quote_resolves_verbatim": True},
        {"turn_id": "t2", "verdict": "unparseable", "parse_status": "unparseable"},
        {"turn_id": "t3", "verdict": "exclusion", "parse_status": "ok", "gate_failed": "gate_1", "reason": "banter"},
        {"turn_id": "t4", "verdict": "claim", "parse_status": "ok", "quote": "More banter", "claim": "banter", "quote_resolves_verbatim": True},
    ]

    # With max_unparseable_rate=0.50 (since 1/4 = 25%), run is valid
    metrics = evaluate_against_gold(extracted, gold_data, turns_data, max_unparseable_rate=0.50)
    assert metrics["is_valid"] is True
    assert metrics["unparseable_count"] == 1
    assert metrics["unparseable_rate_pct"] == 25.0

    cm = metrics["confusion_matrix"]
    # t1 is TP, t4 is FP, t3 is TN. t2 is unparseable and excluded from fn!
    assert cm["tp"] == 1
    assert cm["fp"] == 1
    assert cm["tn"] == 1
    assert cm["fn"] == 0
    # Precision: 1/(1+1) = 0.5, Recall: 1/(1+0) = 1.0 (over parseable turns)
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 1.0


def test_evaluate_against_gold_fails_loudly_above_threshold() -> None:
    """When unparseable rate exceeds 5%, evaluate_against_gold marks invalid or raises."""
    gold_data = {
        "verdicts": [
            {"turn_id": f"t{i}", "verdict": "exclusion", "gate_failed": "gate_1"}
            for i in range(20)
        ]
    }
    turns_data = [{"turn_id": f"t{i}", "text": f"text {i}"} for i in range(20)]

    # 2 out of 20 unparseable = 10% > 5% threshold
    extracted: list[dict[str, Any]] = [
        {"turn_id": f"t{i}", "verdict": "unparseable", "parse_status": "unparseable"}
        if i < 2
        else {"turn_id": f"t{i}", "verdict": "exclusion", "parse_status": "ok", "gate_failed": "gate_1"}
        for i in range(20)
    ]

    # Non-raising mode: marks invalid and suppresses confusion matrix
    metrics = evaluate_against_gold(extracted, gold_data, turns_data, max_unparseable_rate=0.05, raise_on_high_unparseable=False)
    assert metrics["is_valid"] is False
    assert metrics["status"] == "invalid"
    assert metrics["confusion_matrix"] is None
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["unparseable_count"] == 2
    assert metrics["unparseable_rate_pct"] == 10.0

    # Raising mode: raises UnparseableRateError
    with pytest.raises(UnparseableRateError, match="exceeds allowable threshold"):
        evaluate_against_gold(extracted, gold_data, turns_data, max_unparseable_rate=0.05, raise_on_high_unparseable=True)


def test_rescore_b6_artifacts_assertion_c() -> None:
    """Assertion (c):

    The existing Nemotron artifact is flagged at 401/405 when re-scored,
    while gemma-4-31b and GLM-4-32B are flagged at 0.
    """
    nemotron_path = DEFAULT_EXTRACTION_DIR / "b6_extraction_mlx-community_NVIDIA-Nemotron-3-Nano-30B-A3B-4bit_00251a80c868f535.json"
    gemma_path = DEFAULT_EXTRACTION_DIR / "b6_extraction_mlx-community_gemma-4-31b-it-4bit_00251a80c868f535.json"
    glm_path = DEFAULT_EXTRACTION_DIR / "b6_extraction_mlx-community_GLM-4-32B-0414-4bit_00251a80c868f535.json"

    assert nemotron_path.exists(), f"Missing Nemotron artifact: {nemotron_path}"
    assert gemma_path.exists(), f"Missing Gemma artifact: {gemma_path}"
    assert glm_path.exists(), f"Missing GLM artifact: {glm_path}"

    # Re-score Nemotron artifact
    nemotron_rescored = rescore_extraction_artifact(nemotron_path, raise_on_high_unparseable=False)
    assert nemotron_rescored["unparseable_count"] == 401
    assert nemotron_rescored["total_turns"] == 405
    assert nemotron_rescored["is_valid"] is False
    assert nemotron_rescored["confusion_matrix"] is None

    # Re-score Gemma artifact
    gemma_rescored = rescore_extraction_artifact(gemma_path, raise_on_high_unparseable=False)
    assert gemma_rescored["unparseable_count"] == 0
    assert gemma_rescored["total_turns"] == 405
    assert gemma_rescored["is_valid"] is True
    assert gemma_rescored["confusion_matrix"] is not None

    # Re-score GLM artifact
    glm_rescored = rescore_extraction_artifact(glm_path, raise_on_high_unparseable=False)
    assert glm_rescored["unparseable_count"] == 0
    assert glm_rescored["total_turns"] == 405
    assert glm_rescored["is_valid"] is True
    assert glm_rescored["confusion_matrix"] is not None


def test_prompt_template_offset_field_removed() -> None:
    """Gap 1: Verify 'offset' field is deleted from v2/prompts/extract_claim.md and prompt hash changed."""
    content = DEFAULT_PROMPT_CLAIM_PATH.read_text(encoding="utf-8")
    assert '"offset":' not in content, "The 'offset' field must be removed from extract_claim.md"

    # Must differ from B6's recorded hash
    b6_hash = "738f12858fbf903efd56c00a32128ba3c59ce267eedeae59da6333ca2eda282a"
    import hashlib
    curr_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert curr_hash != b6_hash, f"Prompt hash must change from {b6_hash}"


def test_offset_computed_in_code_unaffected() -> None:
    """Gap 1: Verify emitted offset is computed in code even when omitted from model JSON."""
    target_turn = {
        "turn_id": "t010",
        "speaker_label": "David Sacks",
        "text": "Enterprise software multiples have compressed by fifty percent.",
    }
    # JSON output omitting 'offset'
    raw = json.dumps({
        "verdict": "claim",
        "turn_id": "t010",
        "speaker": "David Sacks",
        "type": "position",
        "quote": "Enterprise software multiples have compressed",
        "claim": "Enterprise software multiples have compressed substantially.",
    })
    res = parse_model_verdict(raw, target_turn)
    assert res["verdict"] == "claim"
    assert res["offset"] == 0
    assert res["quote_resolves_verbatim"] is True
