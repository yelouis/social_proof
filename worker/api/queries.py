"""Shared read-only query layer for the review site.

Implements Issue 033 and agent_execution_guide.md §17q.
Guarantees:
- Structural exclusions: tensions.status = 'published', propositions.status = 'active'.
- Assertion (c): No quarantined tension or proposition can be returned.
- Quote verbatim integrity: every claim's quote_text is verified in utterance text_verbatim.
- Zero links to offset 00:00: deep links require offset > 0 and a template, otherwise disabled with reason.
- Evaluates DuckDB live on demand without generated static files.
"""

from __future__ import annotations

import json
from typing import Any

import duckdb


def format_ms_to_timestamp(ms: int | None) -> str:
    """Format milliseconds into HH:MM:SS or MM:SS."""
    if ms is None or ms < 0:
        return "00:00"
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_duration(ms: int | None) -> str:
    """Format duration in milliseconds to human-readable string (e.g. 1h 36m 41s)."""
    if ms is None or ms <= 0:
        return "0m"
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def format_date(iso_str: str | None) -> str:
    """Format an ISO date string to YYYY-MM-DD."""
    if not iso_str:
        return "Undated"
    return iso_str[:10]


def get_quarantined_ids(con: duckdb.DuckDBPyConnection) -> tuple[set[str], set[str]]:
    """Get the set of quarantined tension and proposition IDs for integrity guards."""
    q_tensions = set(
        r[0]
        for r in con.execute(
            "SELECT tension_id FROM tensions WHERE status = 'quarantined'"
        ).fetchall()
    )
    q_props = set(
        r[0]
        for r in con.execute(
            "SELECT proposition_id FROM propositions WHERE status = 'quarantined'"
        ).fetchall()
    )
    return q_tensions, q_props


def get_episodes_list(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Return all episodes ordered newest first, with active claim counts."""
    # Count claims per source only on active propositions
    counts_rows = con.execute(
        """
        SELECT u.source_id, count(c.claim_id)
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE p.status = 'active'
        GROUP BY u.source_id
        """
    ).fetchall()
    claim_counts = {r[0]: r[1] for r in counts_rows}

    sources_rows = con.execute(
        """
        SELECT source_id, title, canonical_url, recorded_at, published_at, duration_ms
        FROM sources
        ORDER BY recorded_at DESC, published_at DESC
        """
    ).fetchall()

    episodes: list[dict[str, Any]] = []
    for sid, title, can_url, rec_at, pub_at, dur_ms in sources_rows:
        episodes.append(
            {
                "source_id": sid,
                "title": title,
                "canonical_url": can_url,
                "recorded_at": rec_at,
                "published_at": pub_at,
                "date_formatted": format_date(rec_at or pub_at),
                "duration_ms": dur_ms,
                "duration_formatted": format_duration(dur_ms),
                "claim_count": claim_counts.get(sid, 0),
            }
        )
    return episodes


def get_all_subjects(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Return all subjects with claim and episode counts."""
    subj_rows = con.execute(
        """
        SELECT s.subject_id, s.display_name,
               count(DISTINCT c.claim_id) as claim_count,
               count(DISTINCT u.source_id) as episode_count
        FROM subjects s
        LEFT JOIN claims c ON s.subject_id = c.subject_id
        LEFT JOIN utterances u ON c.utterance_id = u.utterance_id
        LEFT JOIN propositions p ON c.proposition_id = p.proposition_id AND p.status = 'active'
        GROUP BY s.subject_id, s.display_name
        ORDER BY s.display_name ASC
        """
    ).fetchall()

    return [
        {
            "subject_id": sid,
            "display_name": name,
            "claim_count": cnt,
            "episode_count": ep_cnt,
        }
        for sid, name, cnt, ep_cnt in subj_rows
    ]


def get_episode_detail(
    con: duckdb.DuckDBPyConnection, source_id: str
) -> dict[str, Any] | None:
    """Return episode metadata and claims grouped by speaker in timestamp order."""
    src_row = con.execute(
        """
        SELECT source_id, title, canonical_url, recorded_at, published_at, duration_ms
        FROM sources
        WHERE source_id = ?
        """,
        [source_id],
    ).fetchone()

    if not src_row:
        return None

    sid, title, can_url, rec_at, pub_at, dur_ms = src_row
    q_tensions, q_props = get_quarantined_ids(con)

    # Query claims on active propositions only
    claims_rows = con.execute(
        """
        SELECT c.claim_id, c.subject_id, sub.display_name, c.utterance_id, c.proposition_id,
               c.stance, c.hedging_level, c.quote_text, u.text_verbatim, u.start_ms, u.end_ms,
               s.citation_url_template
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN sources s ON u.source_id = s.source_id
        JOIN subjects sub ON c.subject_id = sub.subject_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE u.source_id = ? AND p.status = 'active'
        ORDER BY u.start_ms ASC
        """,
        [source_id],
    ).fetchall()

    claims_by_person: dict[str, list[dict[str, Any]]] = {}
    total_claims = 0

    for row in claims_rows:
        (
            cid,
            subj_id,
            subj_name,
            utt_id,
            prop_id,
            stance,
            hedging,
            quote_text,
            text_verbatim,
            start_ms,
            end_ms,
            cite_tmpl,
        ) = row

        # Structural quarantine guard
        if prop_id in q_props:
            raise RuntimeError(f"Quarantined proposition {prop_id} in active query!")

        # Verbatim quote verification
        if quote_text not in text_verbatim:
            raise RuntimeError(
                f"Claim {cid} quote_text is not a verbatim substring of utterance {utt_id}!"
            )

        # Citation link rules (Zero links to offset 00:00)
        cite_url: str | None = None
        cite_disabled_reason: str | None = None
        if not cite_tmpl:
            cite_disabled_reason = "No citation URL template available for this source"
        elif start_ms is None or start_ms <= 0:
            cite_disabled_reason = (
                "Citation link disabled: offset is 00:00 (recording start)"
            )
        else:
            cite_url = cite_tmpl.format(seconds=int(start_ms / 1000))

        claim_data = {
            "claim_id": cid,
            "subject_id": subj_id,
            "subject_name": subj_name,
            "stance": stance,
            "hedging_level": float(hedging) if hedging is not None else 0.0,
            "quote_text": quote_text,
            "start_ms": start_ms,
            "timestamp_formatted": format_ms_to_timestamp(start_ms),
            "cite_url": cite_url,
            "cite_disabled_reason": cite_disabled_reason,
        }

        if subj_name not in claims_by_person:
            claims_by_person[subj_name] = []
        claims_by_person[subj_name].append(claim_data)
        total_claims += 1

    return {
        "source_id": sid,
        "title": title,
        "canonical_url": can_url,
        "date_formatted": format_date(rec_at or pub_at),
        "duration_formatted": format_duration(dur_ms),
        "total_claims": total_claims,
        "claims_by_person": claims_by_person,
    }


def get_claim_panel(
    con: duckdb.DuckDBPyConnection, claim_id: str
) -> dict[str, Any] | None:
    """Return the complete Social Proof panel payload for Depth 2 view."""
    q_tensions, q_props = get_quarantined_ids(con)

    claim_row = con.execute(
        """
        SELECT c.claim_id, c.subject_id, sub.display_name, c.utterance_id, c.proposition_id,
               p.canonical_text, c.stance, c.hedging_level, c.recorded_at, c.quote_text,
               u.text_verbatim, u.source_id, s.title, u.start_ms, u.end_ms,
               s.citation_url_template
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN sources s ON u.source_id = s.source_id
        JOIN subjects sub ON c.subject_id = sub.subject_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE c.claim_id = ? AND p.status = 'active'
        """,
        [claim_id],
    ).fetchone()

    if not claim_row:
        return None

    (
        cid,
        subj_id,
        subj_name,
        utt_id,
        prop_id,
        prop_text,
        stance,
        hedging,
        rec_at,
        quote_text,
        text_verbatim,
        src_id,
        src_title,
        start_ms,
        end_ms,
        cite_tmpl,
    ) = claim_row

    if prop_id in q_props:
        raise RuntimeError(f"Quarantined proposition {prop_id} in active query!")

    if quote_text not in text_verbatim:
        raise RuntimeError(
            f"Claim {cid} quote_text is not a verbatim substring of utterance {utt_id}!"
        )

    # Citation link rules
    cite_url: str | None = None
    cite_disabled_reason: str | None = None
    if not cite_tmpl:
        cite_disabled_reason = "No citation URL template available for this source"
    elif start_ms is None or start_ms <= 0:
        cite_disabled_reason = (
            "Citation link disabled: offset is 00:00 (recording start)"
        )
    else:
        cite_url = cite_tmpl.format(seconds=int(start_ms / 1000))

    target_claim = {
        "claim_id": cid,
        "subject_id": subj_id,
        "subject_name": subj_name,
        "source_id": src_id,
        "source_title": src_title,
        "proposition_id": prop_id,
        "proposition_text": prop_text,
        "stance": stance,
        "hedging_level": float(hedging) if hedging is not None else 0.0,
        "recorded_at": rec_at,
        "date_formatted": format_date(rec_at),
        "timestamp_formatted": format_ms_to_timestamp(start_ms),
        "quote_text": quote_text,
        "cite_url": cite_url,
        "cite_disabled_reason": cite_disabled_reason,
    }

    # Timeline: all claims by that speaker on the same proposition
    timeline_rows = con.execute(
        """
        SELECT c.claim_id, c.stance, c.quote_text, c.recorded_at, u.start_ms,
               s.title, s.citation_url_template, u.text_verbatim
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN sources s ON u.source_id = s.source_id
        WHERE c.proposition_id = ? AND c.subject_id = ?
        ORDER BY c.recorded_at ASC, u.start_ms ASC
        """,
        [prop_id, subj_id],
    ).fetchall()

    timeline: list[dict[str, Any]] = []
    for t_row in timeline_rows:
        t_cid, t_stance, t_quote, t_rec_at, t_start_ms, t_src_title, t_cite_tmpl, t_verbatim = (
            t_row
        )
        if t_quote not in t_verbatim:
            raise RuntimeError(f"Timeline claim {t_cid} quote is not in verbatim text!")

        t_url: str | None = None
        t_reason: str | None = None
        if not t_cite_tmpl:
            t_reason = "No citation URL template available for this source"
        elif t_start_ms is None or t_start_ms <= 0:
            t_reason = "Citation link disabled: offset is 00:00 (recording start)"
        else:
            t_url = t_cite_tmpl.format(seconds=int(t_start_ms / 1000))

        timeline.append(
            {
                "claim_id": t_cid,
                "stance": t_stance,
                "quote_text": t_quote,
                "date_formatted": format_date(t_rec_at),
                "timestamp_formatted": format_ms_to_timestamp(t_start_ms),
                "source_title": t_src_title,
                "cite_url": t_url,
                "cite_disabled_reason": t_reason,
                "is_current": (t_cid == cid),
            }
        )

    # Rubric assessment
    ass_row = con.execute(
        """
        SELECT rubric_version, sufficiency, axes, axis_evidence
        FROM assessments
        WHERE subject_id = ? AND topic_id = 'global'
        """,
        [subj_id],
    ).fetchone()

    axes_data: dict[str, Any] = {}
    axis_evidence: dict[str, Any] = {}
    rubric_version = "v1.0"
    if ass_row:
        rubric_version = ass_row[0]
        axes_data = (
            json.loads(ass_row[2])
            if isinstance(ass_row[2], str)
            else (ass_row[2] or {})
        )
        axis_evidence = (
            json.loads(ass_row[3])
            if isinstance(ass_row[3], str)
            else (ass_row[3] or {})
        )

    # Published tensions involving this claim
    tension_rows = con.execute(
        """
        SELECT tension_id, type, claim_a_id, claim_b_id, severity, status
        FROM tensions
        WHERE status = 'published' AND (claim_a_id = ? OR claim_b_id = ?)
        """,
        [cid, cid],
    ).fetchall()

    tensions: list[dict[str, Any]] = []
    for t_row in tension_rows:
        tid, ttype, c_a, c_b, sev, st = t_row
        if tid in q_tensions:
            raise RuntimeError(f"Quarantined tension {tid} in published query!")
        tensions.append(
            {
                "tension_id": tid,
                "type": ttype,
                "claim_a_id": c_a,
                "claim_b_id": c_b,
                "severity": float(sev) if sev is not None else 0.5,
                "status": st,
            }
        )

    # Principles (active only)
    principles_rows = con.execute(
        """
        SELECT principle_id, canonical_text
        FROM principles
        """
    ).fetchall()
    principles = [{"principle_id": r[0], "canonical_text": r[1]} for r in principles_rows]

    return {
        "claim": target_claim,
        "timeline": timeline,
        "axes": axes_data,
        "axis_evidence": axis_evidence,
        "rubric_version": rubric_version,
        "tensions": tensions,
        "principles": principles,
    }


def get_person_detail(
    con: duckdb.DuckDBPyConnection, subject_id: str
) -> dict[str, Any] | None:
    """Return person metadata and claims across all episodes."""
    subj_row = con.execute(
        "SELECT subject_id, display_name FROM subjects WHERE subject_id = ?",
        [subject_id],
    ).fetchone()
    if not subj_row:
        return None

    sid, name = subj_row
    q_tensions, q_props = get_quarantined_ids(con)

    claims_rows = con.execute(
        """
        SELECT c.claim_id, c.stance, c.quote_text, c.recorded_at, u.start_ms,
               s.source_id, s.title, u.text_verbatim, p.proposition_id
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN sources s ON u.source_id = s.source_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE c.subject_id = ? AND p.status = 'active'
        ORDER BY s.recorded_at DESC, u.start_ms ASC
        """,
        [subject_id],
    ).fetchall()

    claims_by_episode: dict[str, dict[str, Any]] = {}
    for c_row in claims_rows:
        cid, stance, quote, rec_at, start_ms, ep_id, ep_title, verbatim, prop_id = c_row
        if prop_id in q_props:
            raise RuntimeError(f"Quarantined proposition {prop_id} in active query!")
        if quote not in verbatim:
            raise RuntimeError(f"Claim {cid} quote is not in utterance verbatim!")

        if ep_id not in claims_by_episode:
            claims_by_episode[ep_id] = {
                "source_id": ep_id,
                "title": ep_title,
                "date_formatted": format_date(rec_at),
                "claims": [],
            }
        claims_by_episode[ep_id]["claims"].append(
            {
                "claim_id": cid,
                "stance": stance,
                "quote_text": quote,
                "timestamp_formatted": format_ms_to_timestamp(start_ms),
            }
        )

    return {
        "subject_id": sid,
        "display_name": name,
        "total_claims": len(claims_rows),
        "total_episodes": len(claims_by_episode),
        "episodes": list(claims_by_episode.values()),
    }
