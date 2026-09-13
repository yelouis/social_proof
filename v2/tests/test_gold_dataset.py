"""Tests for Item B2 — Gold Standard Labelled Dataset.

Contract:
- v2/docs/agent_execution_guide.md §6 (Item B2)
- v2/docs/design_claim_rubric.md in full
- Assertion (c): Every turn has a verdict; count matches B1 exactly (405);
  all four gate-failure rates are non-zero.
"""

import hashlib
import json
from pathlib import Path
import pytest

from v2.src.evaluate_agreement import evaluate_20_turns

GOLD_PATH = Path("v2/fixtures/gold/00251a80c868f535.json")
TRANSCRIPT_PATH = Path("v2/artifacts/transcripts/00251a80c868f535.json")
DB_PATH = Path("v1/social_proof.duckdb")
EXPECTED_DB_SHA256 = "03c1cd0e4f267161cd7110d530c01ac2cdef20a5dde8b36c84a383fea72a6dbe"
VALID_CLAIM_TYPES = {"position", "prediction", "causal", "evaluative", "contested_fact"}
ENROLLED_SPEAKERS = {"Jason Calacanis", "David Friedberg", "Chamath Palihapitiya", "David Sacks"}


@pytest.fixture(scope="module")
def gold_data():
    assert GOLD_PATH.exists(), f"Gold file missing at {GOLD_PATH}"
    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def transcript_data():
    assert TRANSCRIPT_PATH.exists(), f"Transcript file missing at {TRANSCRIPT_PATH}"
    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_v1_database_hash_strictly_unchanged():
    """Assert v1 database is unmodified."""
    h = hashlib.sha256()
    with open(DB_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    assert h.hexdigest() == EXPECTED_DB_SHA256


def test_gold_metadata(gold_data):
    """Verify gold dataset records rubric commit, rubric file, and episode source id."""
    assert "rubric_commit" in gold_data
    assert "rubric_file" in gold_data
    assert gold_data["episode_source_id"] == "00251a80c868f535"
    assert gold_data["total_turns"] == 405


def test_assertion_c_every_turn_has_verdict_and_count_matches_b1(gold_data, transcript_data):
    """Assertion (c): Count matches B1 exactly (405), and every turn has a verdict."""
    turns_b1 = transcript_data["turns"]
    verdicts = gold_data["verdicts"]

    assert len(turns_b1) == 405
    assert len(verdicts) == 405
    assert gold_data["total_turns"] == 405

    b1_turn_ids = [t["turn_id"] for t in turns_b1]
    gold_turn_ids = [v["turn_id"] for v in verdicts]
    assert b1_turn_ids == gold_turn_ids

    for v in verdicts:
        assert v["verdict"] in {"claim", "exclusion"}
        if v["verdict"] == "exclusion":
            assert v.get("gate_failed") in {"gate_1", "gate_2", "gate_3", "gate_4"}
        elif v["verdict"] == "claim":
            assert "quote" in v
            assert "claim" in v
            assert v.get("type") in VALID_CLAIM_TYPES
            assert v.get("speaker") in ENROLLED_SPEAKERS


def test_assertion_c_four_gate_failure_rates_all_nonzero(gold_data):
    """Assertion (c): The four gate-failure rates are all non-zero."""
    counts = gold_data["gate_failure_counts"]
    rates = gold_data["gate_failure_rates"]

    assert counts["gate_1"] > 0
    assert counts["gate_2"] > 0
    assert counts["gate_3"] > 0
    assert counts["gate_4"] > 0

    assert rates["gate_1"] > 0.0
    assert rates["gate_2"] > 0.0
    assert rates["gate_3"] > 0.0
    assert rates["gate_4"] > 0.0


def test_quotes_resolve_verbatim_to_transcript(gold_data, transcript_data):
    """Verify every claim quote is an exact verbatim substring of the target turn."""
    turns_by_id = {t["turn_id"]: t["text"] for t in transcript_data["turns"]}
    claims = [v for v in gold_data["verdicts"] if v["verdict"] == "claim"]

    assert len(claims) == gold_data["claims_count"]
    for c in claims:
        tid = c["turn_id"]
        turn_text = turns_by_id[tid]
        quote = c["quote"]
        assert quote in turn_text, f"Quote '{quote}' failed to resolve in turn {tid}!"
        assert turn_text[c["offset"]:c["offset"] + len(quote)] == quote


def test_inter_annotator_agreement_reported():
    """Verify second-reader agreement is evaluated and reported over 20 random turns."""
    res = evaluate_20_turns(seed=42)
    assert res["sample_size"] == 20
    assert 0.0 <= res["verdict_agreement_pct"] <= 100.0
    assert 0.0 <= res["gate_agreement_pct"] <= 100.0
    # High agreement demonstrates rubric decidability
    assert res["verdict_agreement_pct"] >= 80.0
