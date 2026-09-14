"""Social Proof V2 — Turn Construction & Show Segmentation (Item B1).

Builds coherent speaking turns from raw 12-word ASR utterances in v1/social_proof.duckdb,
strips non-show material (sponsor ad reads, cold open teasers, and outro remix songs),
and classifies question-anchored turns.

Contract:
- v2/docs/agent_execution_guide.md §5 (Item B1)
- v2/docs/design_claim_rubric.md Gate 4
- v1/social_proof.duckdb is read-only (sha256 hash must remain unchanged).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import duckdb

# Known sponsor ad intervals (start_ms, end_ms) per source_id.
# These represent contiguous sponsor copy reads (Airwallex, AppLovin, Creative Planning,
# Nasdaq, Numerals, Oracle Cloud, Northwest Registered Agent, 8090 Promo, Summit Sponsors).
AD_SPANS: dict[str, list[tuple[int, int]]] = {
    "00251a80c868f535": [(4890000, 4971000)],  # All-In Summit sponsor block (Ironhouse, merch.com, Oracle, EY)
    "04ff0000906a6d10": [(50000, 83500), (960000, 998000)],  # AppLovin, Northwest Registered Agent
    "0da89e82768a50ca": [(41000, 68500), (1252000, 1283500)],  # Creative Planning, Northwest Registered Agent
    "601ab4063555d485": [(25000, 48500)],  # Creative Planning
    "6244e2a46bed1e89": [(75000, 108500), (2432000, 2451000)],  # AppLovin, Nasdaq
    "79e5cda81c5740e9": [(20000, 56500)],  # AppLovin
    "79f3aaf4ae50dde5": [(72500, 99500)],  # Airwallex
    "842461fade162070": [(2740000, 2759000)],  # 8090 Promo code / consultation
    "8550481c62a4fddf": [(16000, 60900), (1877000, 1902500)],  # Airwallex, Oracle Cloud Infrastructure
    "9f0b2524821a07d1": [(99500, 136500), (1560000, 1598500)],  # AppLovin, Numerals sales tax
    "ef1c1f5096bc9d01": [(3464000, 3493500)],  # Summit swag suite / merch.com
}

# Cold open teaser soundbites preceding the show introduction.
COLD_OPEN_SPANS: dict[str, tuple[int, int]] = {
    "3db1487d23e98021": (0, 44200),
    "601ab4063555d485": (0, 24500),
    "8550481c62a4fddf": (0, 15000),
}

# Patterns characteristic of the terminal outro music/remix collage.
OUTRO_PATTERNS: list[re.Pattern] = [
    re.compile(r"what you're (the|that)?\s?bee?f", re.IGNORECASE),
    re.compile(r"what you're that beat", re.IGNORECASE),
    re.compile(r"what you're here", re.IGNORECASE),
    re.compile(r"sexual tension that we just need to release", re.IGNORECASE),
    re.compile(r"doing all of (you|it)", re.IGNORECASE),
    re.compile(r"doing all in", re.IGNORECASE),
    re.compile(r"going all the way up", re.IGNORECASE),
    re.compile(r"going out for a lead", re.IGNORECASE),
    re.compile(r"besties are gone", re.IGNORECASE),
    re.compile(r"beef, beef, beef", re.IGNORECASE),
    re.compile(r"i'm going to the toilet", re.IGNORECASE),
    re.compile(r"i squeak up in the water", re.IGNORECASE),
]

SPEAKER_NAME_MAP = {
    "subj_jason_calacanis": "Jason Calacanis",
    "subj_david_friedberg": "David Friedberg",
    "subj_david_sacks": "David Sacks",
    "subj_chamath_palihapitiya": "Chamath Palihapitiya",
    "unknown": "Unknown",
}


@dataclass
class Turn:
    turn_id: str
    source_id: str
    subject_id: str
    speaker_label: str
    start_ms: int
    end_ms: int
    text: str
    word_count: int
    utterance_ids: list[str]
    is_question_anchored: bool = False
    stripped: str | None = None  # "ad_read", "cold_open", "outro", or None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_timestamp(ms: int) -> str:
    """Format milliseconds into MM:SS or HH:MM:SS string."""
    seconds = int(ms / 1000)
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def get_utterance_stripped_tag(
    sid: str,
    start_ms: int,
    end_ms: int,
    text: str,
    max_episode_ms: int,
) -> str | None:
    """Determine if a raw utterance falls inside cold open, ad read, or outro."""
    # 1. Cold open check
    if sid in COLD_OPEN_SPANS:
        _c_start, c_end = COLD_OPEN_SPANS[sid]
        if start_ms < c_end:
            return "cold_open"

    # 2. Ad read check
    if sid in AD_SPANS:
        for a_start, a_end in AD_SPANS[sid]:
            if start_ms >= (a_start - 500) and end_ms <= (a_end + 500):
                return "ad_read"

    # 3. Outro check: last 80s matching outro remix patterns
    if start_ms >= (max_episode_ms - 80000) and any(p.search(text) for p in OUTRO_PATTERNS):
        return "outro"

    return None


def build_turns_from_utterances(
    utterances: Sequence[tuple[Any, ...]],
    max_gap_s: float = 2.0,
    max_words: int = 400,
    enable_speaker_break: bool = True,
    enable_stripping: bool = True,
) -> list[Turn]:
    """Group consecutive utterances into turns.

    Breaks on:
    - Speaker change (if enable_speaker_break is True)
    - Silence gap > max_gap_s (2.0s)
    - Word cap > max_words (400 words)
    - Stripped classification change (so ads/cold-opens/outros don't bleed into dialogue)
    """
    if not utterances:
        return []

    source_id = utterances[0][1]
    max_ms = max(u[5] for u in utterances)

    # Classify each utterance's stripped status
    classified: list[tuple[Any, ...]] = []
    outro_active = False
    for u in utterances:
        uid, src, subj, text, start_ms, end_ms, spk = u[:7]
        st: str | None = None
        if enable_stripping:
            st = get_utterance_stripped_tag(source_id, start_ms, end_ms, text, max_ms)
            if st == "outro":
                outro_active = True
            elif outro_active and start_ms >= (max_ms - 80000):
                st = "outro"
        classified.append((uid, src, subj, text, start_ms, end_ms, spk, st))

    turns_raw: list[dict[str, Any]] = []
    curr: dict[str, Any] | None = None

    for u in classified:
        uid, src, subj, text, start_ms, end_ms, spk, st = u
        words = text.split()
        word_count = len(words)
        spk_label = spk or SPEAKER_NAME_MAP.get(subj, subj)

        if curr is None:
            curr = {
                "source_id": src,
                "subject_id": subj,
                "speaker_label": spk_label,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "utterance_ids": [uid],
                "texts": [text],
                "word_count": word_count,
                "stripped": st,
            }
        else:
            gap_s = (start_ms - curr["end_ms"]) / 1000.0
            same_speaker = (subj == curr["subject_id"]) if enable_speaker_break else True
            same_stripped = (st == curr["stripped"]) if enable_stripping else True
            exceeds_cap = (curr["word_count"] + word_count > max_words)

            if (not same_speaker) or (gap_s > max_gap_s) or exceeds_cap or (not same_stripped):
                turns_raw.append(curr)
                curr = {
                    "source_id": src,
                    "subject_id": subj,
                    "speaker_label": spk_label,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "utterance_ids": [uid],
                    "texts": [text],
                    "word_count": word_count,
                    "stripped": st,
                }
            else:
                curr["end_ms"] = max(curr["end_ms"], end_ms)
                curr["utterance_ids"].append(uid)
                curr["texts"].append(text)
                curr["word_count"] += word_count

    if curr is not None:
        turns_raw.append(curr)

    # Convert to Turn objects
    turns: list[Turn] = []
    for idx, t in enumerate(turns_raw):
        turn_id = f"{t['source_id']}_t{idx:04d}"
        joined_text = " ".join(t["texts"]).strip()
        turns.append(
            Turn(
                turn_id=turn_id,
                source_id=t["source_id"],
                subject_id=t["subject_id"],
                speaker_label=t["speaker_label"],
                start_ms=t["start_ms"],
                end_ms=t["end_ms"],
                text=joined_text,
                word_count=t["word_count"],
                utterance_ids=t["utterance_ids"],
                is_question_anchored=False,
                stripped=t["stripped"],
            )
        )

    # Classify question anchoring
    classify_question_anchoring(turns)
    return turns


def classify_question_anchoring(turns: list[Turn]) -> None:
    """Classify each turn as question-anchored or not.

    A turn is question-anchored when the immediately preceding turn from a
    DIFFERENT speaker ends in an interrogative (? or ?' or ?").
    """
    for idx, turn in enumerate(turns):
        if idx == 0:
            turn.is_question_anchored = False
            continue

        prev_turn = turns[idx - 1]
        prev_text = prev_turn.text.rstrip()
        is_diff_speaker = prev_turn.subject_id != turn.subject_id
        ends_with_q = prev_text.endswith(("?", '?"', "?'", "?..."))

        turn.is_question_anchored = bool(is_diff_speaker and ends_with_q)


def load_utterances_for_episode(
    con: duckdb.DuckDBPyConnection, source_id: str
) -> list[tuple[Any, ...]]:
    """Load utterances for a single episode from v1/social_proof.duckdb."""
    return con.execute(
        """
        SELECT utterance_id, source_id, subject_id, text_verbatim, start_ms, end_ms, speaker_label
        FROM utterances
        WHERE source_id = ?
        ORDER BY start_ms, end_ms, utterance_id
        """,
        [source_id],
    ).fetchall()


def load_all_sources(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, int]]:
    """Load all sources (source_id, title, duration_ms) from v1/social_proof.duckdb."""
    return con.execute(
        """
        SELECT source_id, title, COALESCE(duration_ms, 0)
        FROM sources
        ORDER BY source_id
        """
    ).fetchall()


def format_transcript_markdown(title: str, source_id: str, turns: list[Turn]) -> str:
    """Format turns into a human-readable markdown transcript."""
    total_turns = len(turns)
    retained_turns = [t for t in turns if t.stripped is None]
    stripped_turns = [t for t in turns if t.stripped is not None]
    q_anchored_turns = [t for t in turns if t.is_question_anchored]

    lines: list[str] = [
        f"# {title}",
        "",
        f"- **Source ID:** `{source_id}`",
        f"- **Total Turns:** {total_turns}",
        f"- **Retained Turns:** {len(retained_turns)}",
        f"- **Stripped Turns:** {len(stripped_turns)}",
        f"- **Question-Anchored:** {len(q_anchored_turns)} ({len(q_anchored_turns)/total_turns*100:.1f}%)" if total_turns else "- **Question-Anchored:** 0",
        "",
        "---",
        "",
    ]

    for t in turns:
        ts_start = format_timestamp(t.start_ms)
        ts_end = format_timestamp(t.end_ms)
        tag_parts = []
        if t.is_question_anchored:
            tag_parts.append("Q-Anchored")
        if t.stripped:
            tag_parts.append(f"STRIPPED: {t.stripped}")

        tags = f" [{' | '.join(tag_parts)}]" if tag_parts else ""
        header = f"### [{t.turn_id}] {t.speaker_label} ({ts_start} - {ts_end}){tags}"
        lines.append(header)
        lines.append("")
        if t.stripped:
            lines.append(f"> *[{t.stripped.upper()}]* {t.text}")
        else:
            lines.append(t.text)
        lines.append("")

    return "\n".join(lines)


def export_transcripts(
    con: duckdb.DuckDBPyConnection,
    output_dir: Path,
) -> dict[str, Any]:
    """Export structured JSON and readable Markdown transcripts for all 23 episodes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = load_all_sources(con)

    summary: dict[str, Any] = {
        "total_episodes": len(sources),
        "total_utterances": 0,
        "total_turns": 0,
        "total_retained_turns": 0,
        "total_stripped_turns": 0,
        "total_question_anchored_turns": 0,
        "episodes": [],
    }

    all_utt_words = []
    all_turn_words = []
    retained_turn_words = []

    for sid, title, _ in sources:
        utts = load_utterances_for_episode(con, sid)
        for u in utts:
            all_utt_words.append(len(u[3].split()))

        turns = build_turns_from_utterances(utts)
        retained = [t for t in turns if t.stripped is None]
        stripped = [t for t in turns if t.stripped is not None]
        q_anchored = [t for t in turns if t.is_question_anchored]

        for t in turns:
            all_turn_words.append(t.word_count)
            if t.stripped is None:
                retained_turn_words.append(t.word_count)

        summary["total_utterances"] += len(utts)
        summary["total_turns"] += len(turns)
        summary["total_retained_turns"] += len(retained)
        summary["total_stripped_turns"] += len(stripped)
        summary["total_question_anchored_turns"] += len(q_anchored)

        ep_meta = {
            "source_id": sid,
            "title": title,
            "utterance_count": len(utts),
            "turn_count": len(turns),
            "retained_turn_count": len(retained),
            "stripped_turn_count": len(stripped),
            "question_anchored_count": len(q_anchored),
            "question_anchored_pct": round(len(q_anchored) / len(turns) * 100.0, 2) if turns else 0,
        }
        summary["episodes"].append(ep_meta)

        # 1. JSON export
        json_path = output_dir / f"{sid}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "source_id": sid,
                    "title": title,
                    "metrics": ep_meta,
                    "turns": [t.to_dict() for t in turns],
                },
                f,
                indent=2,
            )

        # 2. Markdown export
        md_path = output_dir / f"{sid}.md"
        md_content = format_transcript_markdown(title, sid, turns)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

    return summary
