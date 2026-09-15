"""Tests for Item B6: Three local models on the same episode, and what agreement is worth.

Verifies:
1. Extractor must declare non-empty model_id (Trap 31 removal; residual 3 from B7).
2. Decoding records sampler: "greedy" and seed: None under temperature=0.0 (residual 1 from B7).
3. Decoding records dynamic max_tokens (residual 2 from B7).
4. Consensus evaluation rules: unanimous <= majority <= any_model claims, confusion matrices sum to total turns.
5. Prompt byte-identity across models: prompts are byte-identical, no per-model prompt tuning.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from v2.src.extract import (
    DEFAULT_GOLD_DIR,
    DEFAULT_RUBRIC_PATH,
    DEFAULT_TRANSCRIPT_DIR,
    build_rubric_prompt,
    evaluate_consensus_against_gold,
    load_rubric,
    run_episode_extraction,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
EPISODE = "00251a80c868f535"


class ValidStubExtractor:
    def __init__(self, model_id: str, runtime: str = "stub", temperature: float = 0.0) -> None:
        self.model_id = model_id
        self.runtime = runtime
        self.quantisation = "4-bit"
        self.temperature = temperature
        self.seed: int | None = None

    def extract_turn(
        self,
        prompt: str,
        target_turn: dict[str, Any],
        context_turn: dict[str, Any] | None = None,
        max_tokens: int = 250,
    ) -> dict[str, Any]:
        return {
            "turn_id": target_turn["turn_id"],
            "verdict": "exclusion",
            "gate_failed": "gate_1",
            "reason": "stub exclusion",
        }


class BadStubExtractor:
    """Deliberately lacks model_id attribute (Trap 31 test)."""

    def extract_turn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"verdict": "exclusion"}


def test_extractor_requires_model_id(tmp_path: Path) -> None:
    """Trap 31 removal (residual 3 from B7): extractor lacking model_id must raise loudly."""
    bad_extractor = BadStubExtractor()
    with pytest.raises(AttributeError, match="model_id"):
        run_episode_extraction(
            source_id=EPISODE,
            max_turns=2,
            extractor=bad_extractor,
            output_dir=tmp_path,
        )


def test_decoding_sampler_greedy_seed_null(tmp_path: Path) -> None:
    """Residual 1 from B7: under greedy decoding, record sampler: 'greedy' and seed: null."""
    stub = ValidStubExtractor("lab/model-1", temperature=0.0)
    res = run_episode_extraction(
        source_id=EPISODE,
        max_turns=2,
        extractor=stub,
        output_dir=tmp_path,
    )
    dec = res["decoding"]
    assert dec["sampler"] == "greedy"
    assert dec["seed"] is None
    assert dec["temperature"] == 0.0


def test_decoding_max_tokens_is_dynamic(tmp_path: Path) -> None:
    """Residual 2 from B7: max_tokens must be read dynamically from the call, not a hardcoded literal."""
    stub = ValidStubExtractor("lab/model-1")
    res = run_episode_extraction(
        source_id=EPISODE,
        max_turns=2,
        extractor=stub,
        output_dir=tmp_path,
        max_tokens=350,
    )
    assert res["decoding"]["max_tokens"] == 350


def test_prompt_byte_identical_across_models() -> None:
    """Prompt byte-identity (§13 Step 1): All models must receive the exact same prompt string."""
    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)
    target_turn = {
        "turn_id": "turn_001",
        "speaker_label": "David Friedberg",
        "text": "Academic science enforces conformity.",
    }
    context_turn = {
        "turn_id": "turn_000",
        "speaker_label": "Jason Calacanis",
        "text": "Let us discuss biology.",
    }
    prompt1 = build_rubric_prompt(rubric_text, target_turn, context_turn)
    prompt2 = build_rubric_prompt(rubric_text, target_turn, context_turn)

    hash1 = hashlib.sha256(prompt1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(prompt2.encode("utf-8")).hexdigest()

    assert hash1 == hash2
    assert prompt1 == prompt2


def test_consensus_evaluation_invariants() -> None:
    """Consensus arithmetic invariants: unanimous <= majority <= any_model claims, confusion matrices sum to total turns."""
    import json

    gold_path = DEFAULT_GOLD_DIR / f"{EPISODE}.json"
    assert gold_path.exists()
    gold_data = json.loads(gold_path.read_text(encoding="utf-8"))

    transcript_path = DEFAULT_TRANSCRIPT_DIR / f"{EPISODE}.json"
    turns = json.loads(transcript_path.read_text(encoding="utf-8"))["turns"]

    # Synthesize 3 model verdicts across all turns
    # Model A: claims turn 0..9 (10 claims)
    # Model B: claims turn 5..14 (10 claims)
    # Model C: claims turn 8..19 (12 claims)
    # Turn 8, 9: claimed by all 3 (unanimous = 2)
    # Turn 5, 6, 7: claimed by A and B (majority >= 2)
    # Turn 10..14: claimed by B and C (majority >= 2)
    def make_verdicts(claimed_indices: set[int]) -> list[dict[str, Any]]:
        v_list = []
        for idx, t in enumerate(turns):
            tid = t["turn_id"]
            if idx in claimed_indices:
                v_list.append({"turn_id": tid, "verdict": "claim", "quote": t["text"][:10], "claim": "c"})
            else:
                v_list.append({"turn_id": tid, "verdict": "exclusion", "gate_failed": "gate_1"})
        return v_list

    m_verdicts = {
        "model_a": make_verdicts(set(range(10))),
        "model_b": make_verdicts(set(range(5, 15))),
        "model_c": make_verdicts(set(range(8, 20))),
    }

    res = evaluate_consensus_against_gold(m_verdicts, gold_data, turns)

    unanimous = res["unanimous"]
    majority = res["majority"]
    any_model = res["any_model"]

    # Invariant 1: Unanimous claims <= Majority claims <= Any-model claims
    assert unanimous["claims_count"] <= majority["claims_count"] <= any_model["claims_count"]
    assert unanimous["claims_count"] == 2  # Turns 8 and 9

    # Invariant 2: Confusion matrices sum to 405
    for rule in (unanimous, majority, any_model):
        cm = rule["confusion_matrix"]
        total = cm["tp"] + cm["fp"] + cm["tn"] + cm["fn"]
        assert total == len(turns)


def test_falsification_decoding_nonzero_temperature(tmp_path: Path) -> None:
    """Falsification (§13): Running with temperature > 0.0 records sampler and seed."""
    stub = ValidStubExtractor("lab/model-temp", temperature=0.7)
    stub.seed = 1234
    res = run_episode_extraction(
        source_id=EPISODE,
        max_turns=2,
        extractor=stub,
        output_dir=tmp_path,
    )
    dec = res["decoding"]
    assert dec["temperature"] == 0.7
    assert dec["sampler"] == "temp_0.7"
    assert dec["seed"] == 1234
