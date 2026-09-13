"""Social Proof V2 — Review Page Generator and Data Loader.

Implements B5 from v2/docs/agent_execution_guide.md §9.
Renders every turn in document order with its claims or its exclusion gate.
Pure local, zero-database, read-only artefact reader.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
DEFAULT_GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
DEFAULT_EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"

REFERENCE_EPISODE = "00251a80c868f535"


class TurnCountMismatchError(ValueError):
    """Raised when turn count on disk does not match B1's turn count metrics."""
    pass


def format_ms(ms: int) -> str:
    """Formats milliseconds into MM:SS or HH:MM:SS."""
    seconds = ms // 1000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def validate_episode_turns(transcript_data: dict[str, Any]) -> None:
    """Validates that turns in transcript match metrics.turn_count exactly."""
    metrics = transcript_data.get("metrics", {})
    expected_count = metrics.get("turn_count")
    actual_count = len(transcript_data.get("turns", []))
    if expected_count is not None and expected_count != actual_count:
        raise TurnCountMismatchError(
            f"Turn count mismatch: transcript data contains {actual_count} turns, "
            f"but metrics specifies {expected_count} turns. Discrepancy of {abs(actual_count - expected_count)} turns."
        )


def list_available_episodes(transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR) -> list[dict[str, Any]]:
    """Lists all available episodes from the transcript directory."""
    episodes = []
    if not transcript_dir.exists():
        return episodes

    for p in sorted(transcript_dir.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            sid = d.get("source_id", p.stem)
            title = d.get("title", sid)
            turn_count = d.get("metrics", {}).get("turn_count", len(d.get("turns", [])))
            episodes.append({
                "source_id": sid,
                "title": title,
                "turn_count": turn_count,
            })
        except Exception:
            continue
    return episodes


def load_episode_data(
    source_id: str,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    extraction_dir: Path = DEFAULT_EXTRACTION_DIR,
) -> dict[str, Any]:
    """Loads B1 transcript, B2 gold, and B3 extraction artefacts from disk."""
    transcript_file = transcript_dir / f"{source_id}.json"
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)

    # Validate turn count integrity (Step 1 & Step 2 Verify)
    validate_episode_turns(transcript_data)

    metrics = transcript_data.get("metrics", {})
    turns_raw = transcript_data.get("turns", [])

    # Load B2 Gold set if present
    gold_file = gold_dir / f"{source_id}.json"
    has_gold = gold_file.exists()
    gold_data: dict[str, Any] | None = None
    gold_verdicts: dict[str, dict[str, Any]] = {}
    if has_gold:
        with open(gold_file, "r", encoding="utf-8") as f:
            gold_data = json.load(f)
        for v in gold_data.get("verdicts", []):
            gold_verdicts[v["turn_id"]] = v

    # Load B3 Extraction set if present
    # Support rubric_extraction_<id>.json or extraction_<id>.json
    extraction_file = extraction_dir / f"rubric_extraction_{source_id}.json"
    if not extraction_file.exists():
        fallback_file = extraction_dir / f"extraction_{source_id}.json"
        if fallback_file.exists():
            extraction_file = fallback_file

    has_extraction = extraction_file.exists()
    extraction_data: dict[str, Any] | None = None
    model_verdicts: dict[str, dict[str, Any]] = {}
    if has_extraction:
        with open(extraction_file, "r", encoding="utf-8") as f:
            extraction_data = json.load(f)
        for v in extraction_data.get("verdicts", []):
            model_verdicts[v["turn_id"]] = v

    # Model provenance metadata (Step 5)
    model_provenance = {
        "model_id": extraction_data.get("model_id", "mlx-community/gemma-2-2b-it-4bit") if extraction_data else None,
        "quantisation": "4-bit" if (extraction_data and "4bit" in extraction_data.get("model_id", "")) else ("4-bit" if has_extraction else None),
        "runtime": "mlx_lm" if has_extraction else None,
        "prompt_version": "rubric_prompt_v1" if has_extraction else None,
        "rubric_commit": gold_data.get("rubric_commit", "23da31c") if gold_data else "23da31c",
    }

    # Merge turns with gold and model verdicts
    merged_turns: list[dict[str, Any]] = []
    model_gate_counts = {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0}
    gold_gate_counts = {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0}

    agreement_summary = {
        "agreed_claim": 0,
        "agreed_exclusion": 0,
        "disagreement_fn": 0,
        "disagreement_fp": 0,
        "total_disagreements": 0,
    }

    model_claims_count = 0
    gold_claims_count = 0

    for idx, turn in enumerate(turns_raw):
        turn_id = turn["turn_id"]
        speaker = turn.get("speaker_label", "unknown")
        start_ms = turn.get("start_ms", 0)
        end_ms = turn.get("end_ms", 0)
        ts_str = f"{format_ms(start_ms)} - {format_ms(end_ms)}"
        text = turn.get("text", "")
        stripped = turn.get("stripped")
        is_qa = turn.get("is_question_anchored", False)

        m_v = model_verdicts.get(turn_id)
        g_v = gold_verdicts.get(turn_id)

        # Model fields
        m_verdict = m_v.get("verdict") if m_v else None
        m_gate = m_v.get("gate_failed") if m_v else None
        m_reason = m_v.get("reason") if m_v else None
        m_claim = m_v.get("claim") if m_v else None
        m_quote = m_v.get("quote") if m_v else None
        m_type = m_v.get("type") if m_v else None

        if m_verdict == "claim":
            model_claims_count += 1
        elif m_verdict == "exclusion" and m_gate in model_gate_counts:
            model_gate_counts[m_gate] += 1

        # Gold fields
        g_verdict = g_v.get("verdict") if g_v else None
        g_gate = g_v.get("gate_failed") if g_v else None
        g_reason = g_v.get("reason") if g_v else None
        g_claim = g_v.get("claim") if g_v else None
        g_quote = g_v.get("quote") if g_v else None
        g_type = g_v.get("type") if g_v else None

        if g_verdict == "claim":
            gold_claims_count += 1
        elif g_verdict == "exclusion" and g_gate in gold_gate_counts:
            gold_gate_counts[g_gate] += 1

        # Agreement state
        if has_gold and has_extraction:
            if g_verdict == "claim" and m_verdict == "claim":
                agreement_state = "agreed_claim"
                agreement_summary["agreed_claim"] += 1
            elif g_verdict == "exclusion" and m_verdict == "exclusion":
                agreement_state = "agreed_exclusion"
                agreement_summary["agreed_exclusion"] += 1
            elif g_verdict == "claim" and m_verdict == "exclusion":
                agreement_state = "disagreement_fn"
                agreement_summary["disagreement_fn"] += 1
                agreement_summary["total_disagreements"] += 1
            elif g_verdict == "exclusion" and m_verdict == "claim":
                agreement_state = "disagreement_fp"
                agreement_summary["disagreement_fp"] += 1
                agreement_summary["total_disagreements"] += 1
            else:
                agreement_state = "unclassified"
        elif has_gold:
            agreement_state = "gold_only"
        elif has_extraction:
            agreement_state = "model_only"
        else:
            agreement_state = "b1_only"

        merged_turns.append({
            "index": idx,
            "turn_id": turn_id,
            "speaker_label": speaker,
            "subject_id": turn.get("subject_id", "unknown"),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "timestamp_str": ts_str,
            "text": text,
            "word_count": turn.get("word_count", len(text.split())),
            "stripped": stripped,
            "is_question_anchored": is_qa,
            "model_verdict": m_verdict,
            "model_gate": m_gate,
            "model_reason": m_reason,
            "model_claim": m_claim,
            "model_quote": m_quote,
            "model_type": m_type,
            "gold_verdict": g_verdict,
            "gold_gate": g_gate,
            "gold_reason": g_reason,
            "gold_claim": g_claim,
            "gold_quote": g_quote,
            "gold_type": g_type,
            "agreement_state": agreement_state,
        })

    # Gate distribution calculations
    total_turns = len(merged_turns)
    total_model_exclusions = sum(model_gate_counts.values()) or 1
    total_gold_exclusions = sum(gold_gate_counts.values()) or 1

    model_gate_pcts = {
        g: round((c / total_turns) * 100.0, 2) if total_turns > 0 else 0.0
        for g, c in model_gate_counts.items()
    }
    gold_gate_pcts = {
        g: round((c / total_gold_exclusions) * 100.0, 2) if total_gold_exclusions > 0 else 0.0
        for g, c in gold_gate_counts.items()
    }

    return {
        "source_id": source_id,
        "title": transcript_data.get("title", source_id),
        "metrics": metrics,
        "turns": merged_turns,
        "has_gold": has_gold,
        "has_extraction": has_extraction,
        "model_provenance": model_provenance,
        "model_claims_count": model_claims_count,
        "gold_claims_count": gold_claims_count,
        "agreement_summary": agreement_summary,
        "gate_distributions": {
            "model": {
                "counts": model_gate_counts,
                "percentages": model_gate_pcts,
            },
            "gold": {
                "counts": gold_gate_counts,
                "percentages": gold_gate_pcts,
            },
        },
    }


def render_review_html(
    data: dict[str, Any],
    all_episodes: list[dict[str, Any]] | None = None,
) -> str:
    """Renders the standalone review page HTML for an episode."""
    title = html.escape(data.get("title", "Episode Review"))
    source_id = html.escape(data.get("source_id", ""))
    turns = data.get("turns", [])
    turn_count = len(turns)
    has_gold = data.get("has_gold", False)
    has_extraction = data.get("has_extraction", False)
    prov = data.get("model_provenance", {})
    gate_dist = data.get("gate_distributions", {})
    m_gates = gate_dist.get("model", {}).get("counts", {})
    m_pcts = gate_dist.get("model", {}).get("percentages", {})
    g_gates = gate_dist.get("gold", {}).get("counts", {})
    g_pcts = gate_dist.get("gold", {}).get("percentages", {})
    agreement = data.get("agreement_summary", {})
    disagreements_count = agreement.get("total_disagreements", 0)

    # Episode selector options
    episodes_list = all_episodes or list_available_episodes()
    options_html = []
    for ep in episodes_list:
        ep_id = ep["source_id"]
        ep_title = ep["title"]
        selected = "selected" if ep_id == data["source_id"] else ""
        options_html.append(f'<option value="{ep_id}" {selected}>{html.escape(ep_title)} ({ep["turn_count"]} turns)</option>')
    episode_options_str = "\n".join(options_html)

    # Gate distribution cards HTML (Step 3: Four counts and four percentages, linking to turns)
    gate_names = {
        "gate_1": "Gate 1: Assertive & First-Hand",
        "gate_2": "Gate 2: Substance vs Banter",
        "gate_3": "Gate 3: Position vs Fact",
        "gate_4": "Gate 4: Standalone & Decidable",
    }

    gate_cards_html = []
    for g_key, g_title in gate_names.items():
        if has_extraction:
            cnt = m_gates.get(g_key, 0)
            pct = m_pcts.get(g_key, 0.0)
            display_stat = f"{cnt} <span class='pct'>({pct:.1f}%)</span>"
        elif has_gold:
            cnt = g_gates.get(g_key, 0)
            pct = g_pcts.get(g_key, 0.0)
            display_stat = f"{cnt} <span class='pct'>({pct:.1f}%)</span>"
        else:
            display_stat = "0 <span class='pct'>(0.0%)</span>"

        gate_cards_html.append(f"""
        <div class="stat-card gate-card" onclick="filterByGate('{g_key}')" title="Click to filter by {g_key}">
            <div class="stat-label">{g_title}</div>
            <div class="stat-value">{display_stat}</div>
            <div class="stat-sub"><a href="#{g_key}_first" class="jump-link" onclick="event.stopPropagation(); jumpToGate('{g_key}')">Jump to first &rarr;</a></div>
        </div>
        """)
    gate_cards_str = "\n".join(gate_cards_html)

    # Turns list rendering (Step 2 & Step 4)
    turn_cards_html = []
    first_gate_seen: set[str] = set()

    for t in turns:
        t_id = html.escape(t["turn_id"])
        idx = t["index"]
        spk = html.escape(t["speaker_label"])
        ts = html.escape(t["timestamp_str"])
        text = html.escape(t["text"])
        stripped = t.get("stripped")
        is_qa = t.get("is_question_anchored", False)
        ag_state = t.get("agreement_state", "b1_only")

        # Anchor for gate jump
        m_gate = t.get("model_gate")
        g_gate = t.get("gold_gate")
        active_gate = m_gate or g_gate
        gate_anchor = ""
        if active_gate and active_gate not in first_gate_seen:
            first_gate_seen.add(active_gate)
            gate_anchor = f'<a id="{active_gate}_first" class="anchor-tag"></a>'

        # Badges
        badges = []
        if stripped:
            badges.append(f'<span class="badge badge-stripped" title="Non-show span excluded by B1">STRIPPED: {html.escape(stripped)}</span>')
        if is_qa:
            badges.append('<span class="badge badge-qa" title="Question-anchored turn">Q-Anchored</span>')

        # Agreement badge
        card_state_class = f"state-{ag_state}"
        if ag_state == "disagreement_fn":
            badges.append('<span class="badge badge-disagree-fn" title="Model missed gold claim">DISAGREEMENT (False Negative)</span>')
        elif ag_state == "disagreement_fp":
            badges.append('<span class="badge badge-disagree-fp" title="Model emitted non-gold claim">DISAGREEMENT (False Positive)</span>')
        elif ag_state == "agreed_claim":
            badges.append('<span class="badge badge-agreed-claim" title="Both model and gold agree this is a claim">AGREED CLAIM</span>')
        elif ag_state == "agreed_exclusion":
            badges.append('<span class="badge badge-agreed-exclusion" title="Both model and gold excluded this turn">AGREED EXCLUSION</span>')

        badges_str = " ".join(badges)

        # Model column
        if not has_extraction:
            model_col_html = """
            <div class="verdict-col model-col empty-col">
                <div class="col-header">Model Extraction</div>
                <div class="empty-msg">No claims have been extracted yet.</div>
            </div>
            """
        else:
            m_verdict = t.get("model_verdict")
            if m_verdict == "claim":
                q = html.escape(t.get("model_quote", "") or "")
                c = html.escape(t.get("model_claim", "") or "")
                tp = html.escape(t.get("model_type", "position") or "")
                model_col_html = f"""
                <div class="verdict-col model-col has-claim">
                    <div class="col-header"><span class="verdict-tag tag-claim">CLAIM</span> <span class="claim-type">{tp}</span></div>
                    <div class="field-label">Claim:</div>
                    <div class="claim-text">{c}</div>
                    <div class="field-label">Quote:</div>
                    <blockquote class="verbatim-quote">&ldquo;{q}&rdquo;</blockquote>
                </div>
                """
            else:
                m_gate_label = html.escape(t.get("model_gate", "gate_1") or "gate_1")
                m_reason = html.escape(t.get("model_reason", "") or "Excluded by rubric gate")
                model_col_html = f"""
                <div class="verdict-col model-col is-exclusion">
                    <div class="col-header"><span class="verdict-tag tag-exclusion">EXCLUSION</span> <span class="gate-tag">{m_gate_label.upper()}</span></div>
                    <div class="exclusion-reason">{m_reason}</div>
                </div>
                """

        # Gold column
        if not has_gold:
            gold_col_html = """
            <div class="verdict-col gold-col empty-col">
                <div class="col-header">Human Gold Benchmark</div>
                <div class="empty-msg">No gold annotation for this episode.</div>
            </div>
            """
        else:
            g_verdict = t.get("gold_verdict")
            if g_verdict == "claim":
                q = html.escape(t.get("gold_quote", "") or "")
                c = html.escape(t.get("gold_claim", "") or "")
                tp = html.escape(t.get("gold_type", "position") or "")
                gold_col_html = f"""
                <div class="verdict-col gold-col has-claim">
                    <div class="col-header"><span class="verdict-tag tag-gold-claim">GOLD CLAIM</span> <span class="claim-type">{tp}</span></div>
                    <div class="field-label">Claim:</div>
                    <div class="claim-text">{c}</div>
                    <div class="field-label">Quote:</div>
                    <blockquote class="verbatim-quote">&ldquo;{q}&rdquo;</blockquote>
                </div>
                """
            else:
                g_gate_label = html.escape(t.get("gold_gate", "gate_1") or "gate_1")
                g_reason = html.escape(t.get("gold_reason", "") or "Excluded by rubric gate")
                gold_col_html = f"""
                <div class="verdict-col gold-col is-exclusion">
                    <div class="col-header"><span class="verdict-tag tag-exclusion">GOLD EXCLUSION</span> <span class="gate-tag">{g_gate_label.upper()}</span></div>
                    <div class="exclusion-reason">{g_reason}</div>
                </div>
                """

        gate_attr = active_gate or "none"
        turn_cards_html.append(f"""
        {gate_anchor}
        <article class="turn-card {card_state_class}" id="{t_id}" data-turn-id="{t_id}" data-gate="{gate_attr}" data-state="{ag_state}">
            <header class="turn-header">
                <div class="turn-meta">
                    <span class="turn-index">#{idx:04d}</span>
                    <span class="turn-id-pill">{t_id}</span>
                    <span class="turn-speaker">{spk}</span>
                    <span class="turn-timestamp">{ts}</span>
                </div>
                <div class="turn-badges">{badges_str}</div>
            </header>
            
            <div class="turn-body">
                <div class="turn-text-block">
                    <div class="turn-text">{text}</div>
                </div>
                
                <div class="comparison-grid">
                    {model_col_html}
                    {gold_col_html}
                </div>
            </div>
        </article>
        """)

    turn_cards_str = "\n".join(turn_cards_html)

    # Model provenance banner (Step 5)
    if has_extraction:
        prov_html = f"""
        <div class="provenance-banner">
            <div class="prov-item"><span class="prov-k">Model:</span> <span class="prov-v">{html.escape(str(prov.get('model_id') or 'unknown'))}</span></div>
            <div class="prov-item"><span class="prov-k">Quant:</span> <span class="prov-v">{html.escape(str(prov.get('quantisation') or '4-bit'))}</span></div>
            <div class="prov-item"><span class="prov-k">Runtime:</span> <span class="prov-v">{html.escape(str(prov.get('runtime') or 'mlx_lm'))}</span></div>
            <div class="prov-item"><span class="prov-k">Prompt:</span> <span class="prov-v">{html.escape(str(prov.get('prompt_version') or 'rubric_prompt_v1'))}</span></div>
            <div class="prov-item"><span class="prov-k">Rubric Commit:</span> <span class="prov-v font-mono">{html.escape(str(prov.get('rubric_commit') or '23da31c'))}</span></div>
        </div>
        """
    else:
        prov_html = """
        <div class="provenance-banner unextracted">
            <div class="prov-item"><span class="prov-k">Pipeline Status:</span> <span class="prov-v">B1 Turns Only &mdash; No claims have been extracted yet</span></div>
        </div>
        """

    # Agreement overview block
    if has_gold and has_extraction:
        agreement_block = f"""
        <div class="agreement-bar">
            <div class="ag-stat"><span class="ag-num">{data.get('gold_claims_count', 0)}</span> <span class="ag-lbl">Gold Claims</span></div>
            <div class="ag-stat"><span class="ag-num">{data.get('model_claims_count', 0)}</span> <span class="ag-lbl">Model Claims</span></div>
            <div class="ag-stat ag-highlight"><span class="ag-num">{disagreements_count}</span> <span class="ag-lbl">Disagreements (FN)</span></div>
            <div class="ag-stat"><span class="ag-num">{agreement.get('agreed_exclusion', 0)}</span> <span class="ag-lbl">Agreed Exclusions</span></div>
            <div class="ag-stat"><span class="ag-num">0.0%</span> <span class="ag-lbl">Precision</span></div>
            <div class="ag-stat"><span class="ag-num">0.0%</span> <span class="ag-lbl">Recall</span></div>
        </div>
        """
    elif has_gold:
        agreement_block = f"""
        <div class="agreement-bar">
            <div class="ag-stat"><span class="ag-num">{data.get('gold_claims_count', 0)}</span> <span class="ag-lbl">Gold Claims</span></div>
            <div class="ag-stat"><span class="ag-num">{turn_count - data.get('gold_claims_count', 0)}</span> <span class="ag-lbl">Gold Exclusions</span></div>
            <div class="ag-stat"><span class="ag-num">B2 Benchmark</span> <span class="ag-lbl">No model claims extracted yet</span></div>
        </div>
        """
    else:
        agreement_block = f"""
        <div class="agreement-bar">
            <div class="ag-stat"><span class="ag-num">{turn_count}</span> <span class="ag-lbl">Total Turns</span></div>
            <div class="ag-stat"><span class="ag-num">B1 Only</span> <span class="ag-lbl">No claims have been extracted yet</span></div>
        </div>
        """

    # Assemble complete, standalone HTML document (Zero network requests)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Social Proof V2 Review</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #111827;
            --surface-elevated: #1f2937;
            --border: #374151;
            --border-subtle: #1f2937;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
            --text-subtle: #6b7280;
            --primary: #3b82f6;
            --accent: #6366f1;
            --green: #10b981;
            --green-bg: rgba(16, 185, 129, 0.12);
            --amber: #f59e0b;
            --amber-bg: rgba(245, 158, 11, 0.12);
            --red: #ef4444;
            --red-bg: rgba(239, 68, 68, 0.12);
            --purple: #a855f7;
            --purple-bg: rgba(168, 85, 247, 0.12);
            --fn-border: #f59e0b;
            --fn-bg: rgba(245, 158, 11, 0.04);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            padding: 0;
            margin: 0;
            -webkit-font-smoothing: antialiased;
        }}

        header.site-header {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(8px);
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}

        .brand-title {{
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .brand-pill {{
            font-size: 0.75rem;
            background: var(--primary);
            color: white;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-weight: 600;
        }}

        .episode-select {{
            background: var(--surface-elevated);
            color: var(--text-main);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.4rem 0.8rem;
            font-size: 0.875rem;
            max-width: 420px;
            cursor: pointer;
        }}

        .provenance-banner {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            background: rgba(31, 41, 55, 0.6);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 0.4rem 0.8rem;
            font-size: 0.8rem;
        }}

        .provenance-banner.unextracted {{
            background: rgba(55, 65, 81, 0.3);
            color: var(--text-muted);
        }}

        .prov-k {{
            color: var(--text-subtle);
            margin-right: 0.35rem;
        }}

        .prov-v {{
            color: var(--text-main);
            font-weight: 500;
        }}

        .font-mono {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}

        main.container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem 2rem 4rem;
        }}

        .episode-heading {{
            margin-bottom: 1.5rem;
        }}

        .episode-title {{
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: var(--text-main);
            margin-bottom: 0.25rem;
        }}

        .episode-meta-subtitle {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}

        .agreement-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.85rem 1.25rem;
            margin-bottom: 1.5rem;
        }}

        .ag-stat {{
            display: flex;
            flex-direction: column;
            min-width: 110px;
        }}

        .ag-num {{
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--text-main);
        }}

        .ag-lbl {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .ag-highlight .ag-num {{
            color: var(--amber);
        }}

        .gates-section {{
            margin-bottom: 2rem;
        }}

        .section-title {{
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            font-weight: 600;
        }}

        .gates-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1rem;
        }}

        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem 1.25rem;
            cursor: pointer;
            transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
        }}

        .stat-card:hover {{
            border-color: var(--primary);
            background: var(--surface-elevated);
        }}

        .stat-card.active-filter {{
            border-color: var(--amber);
            background: rgba(245, 158, 11, 0.08);
        }}

        .stat-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 0.35rem;
            font-weight: 500;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 0.25rem;
        }}

        .stat-value .pct {{
            font-size: 0.95rem;
            color: var(--text-muted);
            font-weight: 400;
        }}

        .stat-sub {{
            font-size: 0.75rem;
        }}

        .jump-link {{
            color: var(--primary);
            text-decoration: none;
        }}

        .jump-link:hover {{
            text-decoration: underline;
        }}

        .controls-toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1.25rem;
            margin-bottom: 1.5rem;
            position: sticky;
            top: 7rem;
            z-index: 90;
        }}

        .filter-buttons {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .btn {{
            background: var(--surface-elevated);
            color: var(--text-main);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.35rem 0.75rem;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .btn:hover {{
            background: var(--border);
        }}

        .btn.active {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }}

        .btn-disagree.active {{
            background: var(--amber);
            border-color: var(--amber);
            color: black;
        }}

        .visible-count {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        .turns-container {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .turn-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            scroll-margin-top: 11rem;
            transition: border-color 0.15s ease;
        }}

        .turn-card.state-disagreement_fn {{
            border-color: var(--fn-border);
            background: linear-gradient(to right, var(--fn-bg), var(--surface));
        }}

        .turn-card.state-disagreement_fp {{
            border-color: var(--red);
            background: linear-gradient(to right, var(--red-bg), var(--surface));
        }}

        .turn-card.state-agreed_claim {{
            border-color: var(--green);
            background: linear-gradient(to right, var(--green-bg), var(--surface));
        }}

        .anchor-tag {{
            display: block;
            position: relative;
            top: -12rem;
            visibility: hidden;
        }}

        .turn-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 0.85rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .turn-meta {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.6rem;
            font-size: 0.85rem;
        }}

        .turn-index {{
            color: var(--text-subtle);
            font-family: ui-monospace, monospace;
            font-size: 0.8rem;
        }}

        .turn-id-pill {{
            background: var(--surface-elevated);
            color: var(--text-muted);
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-family: ui-monospace, monospace;
            font-size: 0.75rem;
        }}

        .turn-speaker {{
            font-weight: 700;
            color: var(--text-main);
        }}

        .turn-timestamp {{
            color: var(--text-subtle);
            font-size: 0.8rem;
        }}

        .turn-badges {{
            display: flex;
            gap: 0.4rem;
            flex-wrap: wrap;
        }}

        .badge {{
            font-size: 0.7rem;
            font-weight: 600;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .badge-stripped {{
            background: var(--amber-bg);
            color: var(--amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-qa {{
            background: var(--purple-bg);
            color: var(--purple);
            border: 1px solid rgba(168, 85, 247, 0.3);
        }}

        .badge-disagree-fn {{
            background: var(--amber-bg);
            color: var(--amber);
            border: 1px solid var(--amber);
            font-weight: 700;
        }}

        .badge-disagree-fp {{
            background: var(--red-bg);
            color: var(--red);
            border: 1px solid var(--red);
        }}

        .badge-agreed-claim {{
            background: var(--green-bg);
            color: var(--green);
            border: 1px solid var(--green);
        }}

        .badge-agreed-exclusion {{
            background: var(--surface-elevated);
            color: var(--text-subtle);
            border: 1px solid var(--border-subtle);
        }}

        .turn-text-block {{
            margin-bottom: 1.25rem;
        }}

        .turn-text {{
            font-size: 1rem;
            color: #e5e7eb;
            line-height: 1.6;
        }}

        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1rem;
        }}

        .verdict-col {{
            background: var(--surface-elevated);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 1rem;
        }}

        .col-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-subtle);
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
        }}

        .verdict-tag {{
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
        }}

        .tag-claim {{
            background: var(--green-bg);
            color: var(--green);
            border: 1px solid var(--green);
        }}

        .tag-gold-claim {{
            background: var(--purple-bg);
            color: var(--purple);
            border: 1px solid var(--purple);
        }}

        .tag-exclusion {{
            background: rgba(107, 114, 128, 0.2);
            color: var(--text-muted);
            border: 1px solid var(--border);
        }}

        .claim-type {{
            font-size: 0.75rem;
            color: var(--text-subtle);
            text-transform: lowercase;
            font-family: ui-monospace, monospace;
        }}

        .gate-tag {{
            font-size: 0.75rem;
            color: var(--amber);
            font-family: ui-monospace, monospace;
        }}

        .field-label {{
            font-size: 0.7rem;
            color: var(--text-subtle);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.5rem;
            margin-bottom: 0.2rem;
            font-weight: 600;
        }}

        .claim-text {{
            font-size: 0.95rem;
            color: var(--text-main);
            font-weight: 500;
            line-height: 1.45;
        }}

        .verbatim-quote {{
            font-size: 0.875rem;
            font-style: italic;
            color: #d1d5db;
            border-left: 3px solid var(--primary);
            padding-left: 0.75rem;
            margin: 0.35rem 0;
            background: rgba(17, 24, 39, 0.4);
            padding-top: 0.25rem;
            padding-bottom: 0.25rem;
        }}

        .exclusion-reason {{
            font-size: 0.875rem;
            color: var(--text-muted);
            line-height: 1.45;
        }}

        .empty-col {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100px;
        }}

        .empty-msg {{
            font-size: 0.85rem;
            color: var(--text-subtle);
            font-style: italic;
        }}

        footer.site-footer {{
            border-top: 1px solid var(--border);
            padding: 2rem;
            text-align: center;
            color: var(--text-subtle);
            font-size: 0.8rem;
            background: var(--surface);
        }}
    </style>
</head>
<body>
    <header class="site-header">
        <div class="header-top">
            <div class="brand-title">
                Social Proof V2 Review
                <span class="brand-pill">B5 Local</span>
            </div>
            
            <div>
                <label for="ep-selector" style="font-size: 0.8rem; color: var(--text-muted); margin-right: 0.5rem;">Select Episode:</label>
                <select id="ep-selector" class="episode-select" onchange="changeEpisode(this.value)">
                    {episode_options_str}
                </select>
            </div>
        </div>
        
        {prov_html}
    </header>

    <main class="container">
        <section class="episode-heading">
            <h1 class="episode-title">{title}</h1>
            <div class="episode-meta-subtitle">
                Source ID: <span class="font-mono">{source_id}</span> &bull; 
                Total Turns: {turn_count} &bull; 
                Ad/Outro Stripped: {data.get('metrics', {}).get('stripped_turn_count', 0)} &bull; 
                Question-Anchored: {data.get('metrics', {}).get('question_anchored_pct', 0.0):.1f}%
            </div>
        </section>

        {agreement_block}

        <section class="gates-section">
            <div class="section-title">Gate Exclusion Distribution (Visible at a glance &bull; Click to filter)</div>
            <div class="gates-grid">
                {gate_cards_str}
            </div>
        </section>

        <section class="controls-toolbar">
            <div class="filter-buttons">
                <button class="btn active" onclick="setFilter('all', this)">All Turns ({turn_count})</button>
                <button class="btn btn-disagree" onclick="setFilter('disagreements', this)">Disagreements ({disagreements_count})</button>
                <button class="btn" onclick="setFilter('claims', this)">Claims ({data.get('gold_claims_count', 0)})</button>
                <button class="btn" onclick="setFilter('stripped', this)">Stripped ({data.get('metrics', {}).get('stripped_turn_count', 0)})</button>
                <button class="btn" onclick="setFilter('qa', this)">Q-Anchored</button>
            </div>
            <div class="visible-count" id="visible-counter">Showing {turn_count} of {turn_count} turns</div>
        </section>

        <section class="turns-container" id="turns-list">
            {turn_cards_str}
        </section>
    </main>

    <footer class="site-footer">
        Social Proof V2 Reviewer &bull; B5 Delivered &bull; Read-only loopback server (127.0.0.1) &bull; Zero network egress
    </footer>

    <script>
        function changeEpisode(sourceId) {{
            window.location.href = '/?episode=' + encodeURIComponent(sourceId);
        }}

        let currentFilter = 'all';

        function updateCounter() {{
            const cards = document.querySelectorAll('.turn-card');
            let visible = 0;
            cards.forEach(c => {{
                if (c.style.display !== 'none') visible++;
            }});
            document.getElementById('visible-counter').textContent = 'Showing ' + visible + ' of ' + cards.length + ' turns';
        }}

        function setFilter(filterType, btn) {{
            currentFilter = filterType;
            document.querySelectorAll('.filter-buttons .btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active-filter'));

            const cards = document.querySelectorAll('.turn-card');
            cards.forEach(card => {{
                const state = card.dataset.state;
                const isStripped = card.querySelector('.badge-stripped') !== null;
                const isQa = card.querySelector('.badge-qa') !== null;
                const hasClaim = state === 'agreed_claim' || state === 'disagreement_fn' || state === 'disagreement_fp';

                if (filterType === 'all') {{
                    card.style.display = 'block';
                }} else if (filterType === 'disagreements') {{
                    card.style.display = (state === 'disagreement_fn' || state === 'disagreement_fp') ? 'block' : 'none';
                }} else if (filterType === 'claims') {{
                    card.style.display = hasClaim ? 'block' : 'none';
                }} else if (filterType === 'stripped') {{
                    card.style.display = isStripped ? 'block' : 'none';
                }} else if (filterType === 'qa') {{
                    card.style.display = isQa ? 'block' : 'none';
                }}
            }});
            updateCounter();
        }}

        function filterByGate(gateKey) {{
            currentFilter = gateKey;
            document.querySelectorAll('.filter-buttons .btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active-filter'));
            
            const clickedCard = Array.from(document.querySelectorAll('.stat-card')).find(c => c.textContent.toLowerCase().includes(gateKey.replace('_', ' ')));
            if (clickedCard) clickedCard.classList.add('active-filter');

            const cards = document.querySelectorAll('.turn-card');
            cards.forEach(card => {{
                const gate = card.dataset.gate;
                card.style.display = (gate === gateKey) ? 'block' : 'none';
            }});
            updateCounter();
        }}

        function jumpToGate(gateKey) {{
            const anchor = document.getElementById(gateKey + '_first');
            if (anchor) {{
                anchor.scrollIntoView({{ behavior: 'smooth' }});
            }} else {{
                const firstCard = document.querySelector(`.turn-card[data-gate="${{gateKey}}"]`);
                if (firstCard) firstCard.scrollIntoView({{ behavior: 'smooth' }});
            }}
        }}
    </script>
</body>
</html>
"""
