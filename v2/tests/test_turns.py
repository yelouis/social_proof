"""Tests for Item B1 — Turn Construction, Segmentation & Question-Anchoring.

Contract:
- v2/docs/agent_execution_guide.md §5 (Item B1)
- v2/docs/design_claim_rubric.md Gate 4
- v1/social_proof.duckdb is read-only (sha256 hash verified unchanged).
"""

import hashlib
from pathlib import Path
import statistics
import duckdb
import pytest

from v2.src.turns import (
    Turn,
    build_turns_from_utterances,
    classify_question_anchoring,
    load_all_sources,
    load_utterances_for_episode,
)

DB_PATH = Path("v1/social_proof.duckdb")
EXPECTED_DB_SHA256 = "03c1cd0e4f267161cd7110d530c01ac2cdef20a5dde8b36c84a383fea72a6dbe"


@pytest.fixture(scope="module")
def con():
    """Read-only DuckDB connection."""
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def test_v1_database_hash_unchanged():
    """Assert v1/social_proof.duckdb file hash is strictly unchanged."""
    h = hashlib.sha256()
    with open(DB_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    actual_hash = h.hexdigest()
    assert actual_hash == EXPECTED_DB_SHA256, (
        f"v1 database was modified! Expected {EXPECTED_DB_SHA256}, got {actual_hash}"
    )


def test_turn_grouping_collapses_fragmentation(con):
    """Verify median turn length is several times median utterance length (12 words)."""
    sources = load_all_sources(con)
    all_utt_lengths = []
    all_turn_lengths = []
    enrolled_turn_lengths = []

    for sid, _, _ in sources:
        utts = load_utterances_for_episode(con, sid)
        for u in utts:
            all_utt_lengths.append(len(u[3].split()))

        turns = build_turns_from_utterances(utts)
        for t in turns:
            all_turn_lengths.append(t.word_count)
            if t.subject_id != "unknown":
                enrolled_turn_lengths.append(t.word_count)

    median_utt = statistics.median(all_utt_lengths)
    median_turn = statistics.median(all_turn_lengths)
    median_enrolled = statistics.median(enrolled_turn_lengths)

    assert median_utt == 12.0
    # Median turn must be several times median utterance (12 words)
    assert median_turn >= 20.0
    assert median_enrolled >= 35.0
    assert median_turn > median_utt


def test_turn_breaks_on_speaker_change():
    """Verify consecutive utterances from different speakers break into separate turns."""
    mock_utts = [
        ("u1", "src1", "subj_jason_calacanis", "Hello world this is Jason.", 0, 3000, "Jason Calacanis"),
        ("u2", "src1", "subj_david_friedberg", "Hey Jason good to see you.", 3100, 6000, "David Friedberg"),
    ]
    turns = build_turns_from_utterances(mock_utts)
    assert len(turns) == 2
    assert turns[0].subject_id == "subj_jason_calacanis"
    assert turns[1].subject_id == "subj_david_friedberg"


def test_turn_breaks_on_gap():
    """Verify consecutive utterances from same speaker break if silence gap > 2.0s."""
    mock_utts = [
        ("u1", "src1", "subj_jason_calacanis", "First point here.", 0, 3000, "Jason Calacanis"),
        # Gap is 2.5s (5500 - 3000 = 2500ms > 2000ms)
        ("u2", "src1", "subj_jason_calacanis", "Second point after a long pause.", 5500, 9000, "Jason Calacanis"),
    ]
    turns = build_turns_from_utterances(mock_utts, max_gap_s=2.0)
    assert len(turns) == 2
    assert turns[0].text == "First point here."
    assert turns[1].text == "Second point after a long pause."


def test_turn_breaks_on_word_cap():
    """Verify consecutive utterances from same speaker break if accumulated words exceed 400."""
    words_250 = "word " * 250
    mock_utts = [
        ("u1", "src1", "subj_jason_calacanis", words_250.strip(), 0, 10000, "Jason Calacanis"),
        # Total words would be 500 > 400
        ("u2", "src1", "subj_jason_calacanis", words_250.strip(), 10500, 20000, "Jason Calacanis"),
    ]
    turns = build_turns_from_utterances(mock_utts, max_words=400)
    assert len(turns) == 2
    assert turns[0].word_count == 250
    assert turns[1].word_count == 250


def test_question_anchoring_classification():
    """Verify turn is question-anchored when previous turn from different speaker ended in '?'."""
    turns = [
        Turn("t0", "s1", "spk1", "Speaker 1", 0, 2000, "What do you think about this?", 7, ["u0"]),
        Turn("t1", "s1", "spk2", "Speaker 2", 2100, 5000, "I think it is great.", 5, ["u1"]),
        Turn("t2", "s1", "spk2", "Speaker 2", 5100, 8000, "Does that make sense?", 4, ["u2"]),
        Turn("t3", "s1", "spk2", "Speaker 2", 8100, 10000, "Yes, absolutely.", 2, ["u3"]),
    ]
    classify_question_anchoring(turns)

    assert not turns[0].is_question_anchored
    # t1 is preceded by spk1's question -> True
    assert turns[1].is_question_anchored
    # t2 is preceded by spk2's statement (not a question) -> False
    assert not turns[2].is_question_anchored
    # t3 is preceded by spk2 (same speaker!) even though it ended in '?' -> False
    assert not turns[3].is_question_anchored


def test_question_anchoring_rate_across_corpus(con):
    """Verify question-anchored rate is ~11.1%, significantly below ~30%."""
    sources = load_all_sources(con)
    total_turns = 0
    total_q_anchored = 0

    for sid, _, _ in sources:
        utts = load_utterances_for_episode(con, sid)
        turns = build_turns_from_utterances(utts)
        total_turns += len(turns)
        total_q_anchored += sum(1 for t in turns if t.is_question_anchored)

    pct = (total_q_anchored / total_turns) * 100.0
    # Step 3 requirement: State plainly if under ~30%
    assert pct < 30.0
    assert 10.0 <= pct <= 13.0


def test_ad_stripping_airwallex(con):
    """Verify Airwallex ad reads are stripped in 8550481c62a4fddf and 79f3aaf4ae50dde5."""
    for sid in ["8550481c62a4fddf", "79f3aaf4ae50dde5"]:
        utts = load_utterances_for_episode(con, sid)
        turns = build_turns_from_utterances(utts)

        retained_texts = [t.text.lower() for t in turns if t.stripped is None]
        # Retained text must NOT contain the Airwallex copy
        for txt in retained_texts:
            assert "legacy tax" not in txt
            assert "airwlocks" not in txt
            assert "airwallix" not in txt
            assert "built for the intelligent era" not in txt

        # Stripped text MUST contain the Airwallex copy
        stripped_ad_texts = [t.text.lower() for t in turns if t.stripped == "ad_read"]
        assert any("legacy tax" in txt or "built for the intelligent era" in txt for txt in stripped_ad_texts)


def test_summit_sponsor_stripping_e287(con):
    """Verify All-In Summit sponsor block (4890s - 4971s) is stripped in E287."""
    utts = load_utterances_for_episode(con, "00251a80c868f535")
    turns = build_turns_from_utterances(utts)

    retained_texts = [t.text.lower() for t in turns if t.stripped is None]
    for txt in retained_texts:
        assert "ironhouse at summit" not in txt
        assert "racing simulator to the summit" not in txt

    stripped_texts = [t.text.lower() for t in turns if t.stripped == "ad_read"]
    assert any("ironhouse at summit" in txt for txt in stripped_texts)


def test_falsification_1_disable_speaker_break(con):
    """Falsify: Disable speaker-change break; turns must collapse into giant blocks."""
    utts = load_utterances_for_episode(con, "00251a80c868f535")
    normal_turns = build_turns_from_utterances(utts, enable_speaker_break=True)
    collapsed_turns = build_turns_from_utterances(utts, enable_speaker_break=False)

    # In E287, 405 normal turns collapse to 54 turns without speaker-change break
    assert len(normal_turns) == 405
    assert len(collapsed_turns) == 54
    assert len(collapsed_turns) < (len(normal_turns) / 7)


def test_falsification_2_disable_ad_stripping(con):
    """Falsify: Disable ad stripping; Airwallex ad block must reappear in retained text."""
    utts = load_utterances_for_episode(con, "8550481c62a4fddf")
    normal_turns = build_turns_from_utterances(utts, enable_stripping=True)
    unstripped_turns = build_turns_from_utterances(utts, enable_stripping=False)

    normal_retained = [t.text.lower() for t in normal_turns if t.stripped is None]
    assert not any("airwlocks" in txt for txt in normal_retained)

    unstripped_retained = [t.text.lower() for t in unstripped_turns if t.stripped is None]
    # Airwallex ad copy reappears in retained text
    assert any("airwlocks" in txt for txt in unstripped_retained)
