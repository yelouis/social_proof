"""Social Proof V2 — Review Page Generator and Data Loader.

Implements B5 from v2/docs/agent_execution_guide.md §9.
Renders every turn in document order with its claims or its exclusion gate.
Pure local, zero-database, read-only artefact reader.
"""

from __future__ import annotations

import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
DEFAULT_GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
DEFAULT_EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"

REFERENCE_EPISODE = "00251a80c868f535"


def get_git_head_short(repo_root: Path = ROOT_DIR.parent) -> str:
    """Returns the short git HEAD commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


SERVER_START_HEAD = get_git_head_short()


class TurnCountMismatchError(ValueError):
    """Raised when turn count on disk does not match B1's turn count metrics."""


def format_ms(ms: int) -> str:
    """Formats milliseconds into MM:SS or HH:MM:SS."""
    seconds = ms // 1000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def validate_episode_turns(transcript_data: dict[str, Any]) -> None:
    """Validates that turns in transcript_data match metrics.turn_count."""
    metrics = transcript_data.get("metrics", {})
    expected_count = metrics.get("turn_count")
    if expected_count is None:
        return
    actual_count = len(transcript_data.get("turns", []))
    if actual_count != expected_count:
        raise TurnCountMismatchError(
            f"Turn count mismatch: transcript data contains {actual_count} turns, "
            f"but metrics specifies {expected_count} turns. Discrepancy of {abs(actual_count - expected_count)} turns."
        )


def list_available_episodes(transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR) -> list[dict[str, Any]]:
    """Lists all available episodes from the transcript directory."""
    episodes: list[dict[str, Any]] = []
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
        except (json.JSONDecodeError, OSError, KeyError):
            continue
    return episodes


def load_episode_data(
    source_id: str,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    extraction_dir: Path = DEFAULT_EXTRACTION_DIR,
    extraction_file: Path | str | None = None,
) -> dict[str, Any]:
    """Loads B1 transcript, B2 gold, and B3 extraction artefacts from disk."""
    transcript_file = transcript_dir / f"{source_id}.json"
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

    artifacts_read: list[dict[str, str]] = []
    t_mtime = datetime.fromtimestamp(transcript_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    artifacts_read.append({"name": transcript_file.name, "path": str(transcript_file), "mtime": t_mtime})

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
        g_mtime = datetime.fromtimestamp(gold_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        artifacts_read.append({"name": gold_file.name, "path": str(gold_file), "mtime": g_mtime})
        with open(gold_file, "r", encoding="utf-8") as f:
            gold_data = json.load(f)
        for v in gold_data.get("verdicts", []):
            gold_verdicts[v["turn_id"]] = v

    # Load B3 Extraction set if present
    if extraction_file is not None:
        target_extraction_file = Path(extraction_file)
    else:
        target_extraction_file = extraction_dir / f"rubric_extraction_{source_id}.json"
        if not target_extraction_file.exists():
            fallback_file = extraction_dir / f"extraction_{source_id}.json"
            if fallback_file.exists():
                target_extraction_file = fallback_file

    has_extraction = target_extraction_file.exists()
    extraction_data: dict[str, Any] | None = None
    model_verdicts: dict[str, dict[str, Any]] = {}
    if has_extraction:
        e_mtime = datetime.fromtimestamp(target_extraction_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        artifacts_read.append({"name": target_extraction_file.name, "path": str(target_extraction_file), "mtime": e_mtime})
        with open(target_extraction_file, "r", encoding="utf-8") as f:
            extraction_data = json.load(f)
        for v in extraction_data.get("verdicts", []):
            model_verdicts[v["turn_id"]] = v

    # Load C4 Scored Axes if present (final artifact or live checkpoint)
    scored_axes_file = extraction_dir / f"c4_scored_axes_{source_id}.json"
    ckpt_axes_file = extraction_dir / f"c4_scored_axes_{source_id}_ckpt.json"
    target_axes_file: Path | None = None
    if scored_axes_file.exists():
        target_axes_file = scored_axes_file
    elif ckpt_axes_file.exists():
        target_axes_file = ckpt_axes_file

    has_scored_axes = target_axes_file is not None
    scored_axes_data: dict[str, Any] | None = None
    turn_axes_map: dict[str, dict[str, Any]] = {}
    if target_axes_file is not None:
        a_mtime = datetime.fromtimestamp(target_axes_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        artifacts_read.append({"name": target_axes_file.name, "path": str(target_axes_file), "mtime": a_mtime})
        with open(target_axes_file, "r", encoding="utf-8") as f:
            scored_axes_data = json.load(f)
        for sc in scored_axes_data.get("scored_claims", []):
            turn_axes_map[sc["turn_id"]] = sc

    # Model provenance metadata (Step 5 & B7 Gap 1: driven strictly by artifact, zero defaults)
    model_provenance = {
        "model_id": extraction_data.get("model_id") if extraction_data else None,
        "scoring_model_id": scored_axes_data.get("scoring_model_id") if scored_axes_data else None,
        "quantisation": extraction_data.get("quantisation") if extraction_data else None,
        "runtime": extraction_data.get("runtime") if extraction_data else None,
        "prompt_version": extraction_data.get("prompt_version") if extraction_data else None,
        "rubric_commit": extraction_data.get("rubric_commit") if extraction_data else None,
        "axes_commit": scored_axes_data.get("report", {}).get("provenance", {}).get("axes_commit") if scored_axes_data else None,
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

        ax_item = turn_axes_map.get(turn_id)
        axes_scores = ax_item.get("scores") if ax_item else None
        axes_reasons = ax_item.get("reasons") if ax_item else None

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
            "axes_scores": axes_scores,
            "axes_reasons": axes_reasons,
        })

    # Gate distribution calculations (share-of-all-turns convention across both model and gold)
    total_turns = len(merged_turns)

    model_gate_pcts = {
        g: round((c / total_turns) * 100.0, 2) if total_turns > 0 else 0.0
        for g, c in model_gate_counts.items()
    }
    gold_gate_pcts = {
        g: round((c / total_turns) * 100.0, 2) if total_turns > 0 else 0.0
        for g, c in gold_gate_counts.items()
    }

    return {
        "source_id": source_id,
        "title": transcript_data.get("title", source_id),
        "metrics": metrics,
        "turns": merged_turns,
        "has_gold": has_gold,
        "has_extraction": has_extraction,
        "has_scored_axes": has_scored_axes,
        "axes_report": scored_axes_data.get("report") if scored_axes_data else None,
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
        "artifacts_read": artifacts_read,
    }


def render_quality_profile_html(axes_report: dict[str, Any] | None) -> str:
    """Renders the Episode Claim Quality Profile report (§4) above the turn list."""
    if not axes_report:
        return ""

    claims_found = axes_report.get("claims_found", axes_report.get("episode", {}).get("claims_found", 0))
    total_turns = axes_report.get("total_turns", axes_report.get("episode", {}).get("total_turns", 405))
    density_pct = axes_report.get("claim_density_pct", axes_report.get("density_pct", axes_report.get("episode", {}).get("density_pct", 0.0)))
    prov = axes_report.get("provenance", {})
    scoring_model = html.escape(str(prov.get("scoring_model_id", "GLM-4-32B")))
    extractor_model = html.escape(str(prov.get("model_id", "Gemma-4-31B")))

    sp_panel = axes_report.get("speaker_panel", {})
    ex_panel = axes_report.get("extraction_panel", {})
    cross_checks = axes_report.get("proxy_cross_checks") or axes_report.get("cross_checks", {})

    def render_axis_row(axis_data: dict[str, Any], is_extraction: bool = False) -> str:
        name = axis_data.get("axis", "").capitalize()
        mean_val = axis_data.get("mean", 0.0)
        counts = axis_data.get("counts", {})
        pcts = axis_data.get("percentages", {})
        zeros = axis_data.get("zero_scores_turn_ids", [])
        if zeros:
            links = [f'<a class="zero-turn-link" href="#{tid}">{tid[-5:]}</a>' for tid in zeros]
            zeros_str = f'<div class="zero-turns-list"><span class="zero-tag">0s ({len(zeros)}):</span> {" ".join(links)}</div>'
        else:
            zeros_str = '<div class="zero-turns-list"><span class="zero-none">0s: none</span></div>'

        return f"""
        <div class="axis-row">
            <div class="axis-name-col">
                <span class="axis-title">{name}</span>
                <span class="axis-mean font-mono">mean {mean_val:.2f}</span>
            </div>
            <div class="axis-dist-col">
                <div class="dist-bar-track">
                    <div class="dist-seg seg-2" style="width: {pcts.get('2', 0.0)}%" title="Score 2: {counts.get('2', 0)} ({pcts.get('2', 0.0):.1f}%)"></div>
                    <div class="dist-seg seg-1" style="width: {pcts.get('1', 0.0)}%" title="Score 1: {counts.get('1', 0)} ({pcts.get('1', 0.0):.1f}%)"></div>
                    <div class="dist-seg seg-0" style="width: {pcts.get('0', 0.0)}%" title="Score 0: {counts.get('0', 0)} ({pcts.get('0', 0.0):.1f}%)"></div>
                </div>
                <div class="dist-numbers">
                    <span class="d-val d-2">2: {pcts.get('2', 0.0):.1f}% ({counts.get('2', 0)})</span>
                    <span class="d-val d-1">1: {pcts.get('1', 0.0):.1f}% ({counts.get('1', 0)})</span>
                    <span class="d-val d-0">0: {pcts.get('0', 0.0):.1f}% ({counts.get('0', 0)})</span>
                </div>
            </div>
            <div class="axis-zeros-col">
                {zeros_str}
            </div>
        </div>
        """

    sp_order = ["voice", "target", "propositionality", "contestability", "typing"]
    ex_order = ["decontextualisation", "fidelity", "granularity"]

    sp_rows = "\n".join(render_axis_row(sp_panel[ax]) for ax in sp_order if ax in sp_panel)
    ex_rows = "\n".join(render_axis_row(ex_panel[ax], is_extraction=True) for ax in ex_order if ax in ex_panel)

    ref_cc = cross_checks.get("decontextualisation", {})
    comp_cc = cross_checks.get("granularity", {})
    fid_cc = cross_checks.get("fidelity", {})

    return f"""
    <section class="quality-profile-section" id="claim-quality-profile">
        <header class="qp-header">
            <div class="qp-title-block">
                <span class="qp-pill">C4 Episode Quality Profile</span>
                <h2 class="qp-title">Claim Quality Across Eight Axes</h2>
                <div class="qp-meta">
                    Two-Pass Architecture &bull; Extractor: <span class="font-mono">{extractor_model}</span> &bull; Scorer: <span class="font-mono">{scoring_model}</span> (Independent Scorer)
                </div>
            </div>
            <div class="qp-stats-box">
                <div class="qp-stat">
                    <span class="qp-stat-num">{claims_found}</span>
                    <span class="qp-stat-lbl">Claims Found</span>
                </div>
                <div class="qp-stat">
                    <span class="qp-stat-num">{density_pct:.1f}%</span>
                    <span class="qp-stat-lbl">Density ({claims_found}/{total_turns} turns)</span>
                </div>
            </div>
        </header>

        <div class="qp-panels-grid">
            <div class="qp-panel-card speaker-card">
                <div class="panel-card-header">
                    <div class="panel-heading">Speaker Panel</div>
                    <div class="panel-sub">How good were the claims made &bull; Epistemic commitment of the speaker</div>
                </div>
                <div class="axis-rows-container">
                    {sp_rows}
                </div>
            </div>

            <div class="qp-panel-card extraction-card">
                <div class="panel-card-header">
                    <div class="panel-heading">Extraction Panel</div>
                    <div class="panel-sub">How well we captured them &bull; Quality gate on extraction pipeline (scored by {scoring_model})</div>
                </div>
                <div class="axis-rows-container">
                    {ex_rows}
                </div>

                <div class="mechanical-proxies-block">
                    <div class="proxies-title">Mechanical Proxy Cross-Checks (§4 &amp; §18)</div>
                    <div class="proxy-stat-row">
                        <span class="proxy-name">Unresolved referents:</span>
                        <span class="proxy-num">{ref_cc.get('proxy_unresolved_referents_count', 0)} of {claims_found}</span>
                        <span class="proxy-overlap">&bull; Decontextualisation 0s overlap: {ref_cc.get('overlap_count', 0)}/{ref_cc.get('proxy_unresolved_referents_count', 0)} ({ref_cc.get('overlap_rate_pct', 0.0):.1f}%)</span>
                    </div>
                    <div class="proxy-stat-row">
                        <span class="proxy-name">Compound claims &gt; 35w:</span>
                        <span class="proxy-num">{comp_cc.get('proxy_compound_claims_count', 0)} of {claims_found}</span>
                        <span class="proxy-overlap">&bull; Granularity 0s overlap: {comp_cc.get('overlap_count', 0)}/{comp_cc.get('proxy_compound_claims_count', 0)} ({comp_cc.get('overlap_rate_pct', 0.0):.1f}%)</span>
                    </div>
                    <div class="proxy-stat-row">
                        <span class="proxy-name">Near-verbatim quotes:</span>
                        <span class="proxy-num">{fid_cc.get('near_verbatim_quotes_count', 0)} of {claims_found}</span>
                        <span class="proxy-overlap">&bull; Token overlap &ge; 83%</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="qp-caveat-footer">
            <span class="caveat-label">Validation Note:</span> Speaker panel and Extraction panel are reported strictly separately and never blended into a composite score. Scored by independent model (<span class="font-mono">{scoring_model}</span>).
        </div>
    </section>
    """


def render_review_html(
    data: dict[str, Any],
    all_episodes: list[dict[str, Any]] | None = None,
    server_head: str | None = None,
) -> str:
    """Renders the standalone review page HTML for an episode."""
    if server_head is None:
        server_head = SERVER_START_HEAD

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
        if has_extraction and has_gold:
            m_cnt = m_gates.get(g_key, 0)
            m_pct = m_pcts.get(g_key, 0.0)
            g_cnt = g_gates.get(g_key, 0)
            g_pct = g_pcts.get(g_key, 0.0)
            display_stat = f"{m_cnt} <span class='pct'>({m_pct:.1f}%)</span> <div class='stat-sub gold-substat'>Gold: {g_cnt} ({g_pct:.2f}%)</div>"
        elif has_extraction:
            cnt = m_gates.get(g_key, 0)
            pct = m_pcts.get(g_key, 0.0)
            display_stat = f"{cnt} <span class='pct'>({pct:.1f}%)</span>"
        elif has_gold:
            cnt = g_gates.get(g_key, 0)
            pct = g_pcts.get(g_key, 0.0)
            display_stat = f"{cnt} <span class='pct'>({pct:.2f}%)</span>"
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

                axes_badges_html = ""
                if t.get("axes_scores"):
                    sc = t["axes_scores"]
                    rs = t.get("axes_reasons") or {}
                    pills = []
                    for ax in ["voice", "target", "propositionality", "contestability", "typing"]:
                        v = sc.get(ax)
                        if v is not None:
                            r = html.escape(str(rs.get(f"{ax}_reason", "")))
                            pills.append(f'<span class="axis-pill score-{v}" title="{ax.capitalize()} ({v}): {r}"><span class="ax-name">{ax[:4].upper()}</span> <span class="ax-val">{v}</span></span>')
                    for ax in ["decontextualisation", "fidelity", "granularity"]:
                        v = sc.get(ax)
                        if v is not None:
                            r = html.escape(str(rs.get(f"{ax}_reason", "")))
                            pills.append(f'<span class="axis-pill score-{v} extraction-pill" title="{ax.capitalize()} ({v}): {r}"><span class="ax-name">{ax[:5].upper()}</span> <span class="ax-val">{v}</span></span>')
                    if pills:
                        axes_badges_html = f'<div class="card-axes-row"><span class="axes-label">Quality:</span> <div class="axes-pills">{" ".join(pills)}</div></div>'

                model_col_html = f"""
                <div class="verdict-col model-col has-claim">
                    <div class="col-header"><span class="verdict-tag tag-claim">CLAIM</span> <span class="claim-type">{tp}</span></div>
                    <div class="field-label">Claim:</div>
                    <div class="claim-text">{c}</div>
                    <div class="field-label">Quote:</div>
                    <blockquote class="verbatim-quote">&ldquo;{q}&rdquo;</blockquote>
                    {axes_badges_html}
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
    quality_profile_html = render_quality_profile_html(data.get("axes_report"))

    # Model provenance banner (Step 5 & B7 Gap 1: driven strictly by artifact, zero defaults)
    if has_extraction:
        scoring_item = ""
        if prov.get("scoring_model_id"):
            scoring_item = f'<div class="prov-item"><span class="prov-k">Scoring Model:</span> <span class="prov-v">{html.escape(str(prov.get("scoring_model_id")))}</span></div>'
        axes_commit_item = ""
        if prov.get("axes_commit"):
            axes_commit_item = f'<div class="prov-item"><span class="prov-k">Axes Commit:</span> <span class="prov-v font-mono">{html.escape(str(prov.get("axes_commit")))}</span></div>'

        prov_html = f"""
        <div class="provenance-banner">
            <div class="prov-item"><span class="prov-k">Model:</span> <span class="prov-v">{html.escape(str(prov.get('model_id') or 'unknown'))}</span></div>
            {scoring_item}
            <div class="prov-item"><span class="prov-k">Quant:</span> <span class="prov-v">{html.escape(str(prov.get('quantisation') or 'unknown'))}</span></div>
            <div class="prov-item"><span class="prov-k">Runtime:</span> <span class="prov-v">{html.escape(str(prov.get('runtime') or 'unknown'))}</span></div>
            <div class="prov-item"><span class="prov-k">Prompt:</span> <span class="prov-v">{html.escape(str(prov.get('prompt_version') or 'unknown'))}</span></div>
            <div class="prov-item"><span class="prov-k">Rubric Commit:</span> <span class="prov-v font-mono">{html.escape(str(prov.get('rubric_commit') or 'unknown'))}</span></div>
            {axes_commit_item}
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

    # Format artifact provenance and mtimes for footer
    artifacts_read = data.get("artifacts_read", [])
    if artifacts_read:
        artifacts_meta_items = [
            f"{html.escape(a['name'])} ({html.escape(a['mtime'])})"
            for a in artifacts_read
        ]
        artifacts_meta_str = " &bull; ".join(artifacts_meta_items)
    else:
        artifacts_meta_str = "None"

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

        .footer-primary {{
            margin-bottom: 0.35rem;
        }}

        .footer-meta {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .gold-substat {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        /* Quality Profile Section */
        .quality-profile-section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .qp-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .qp-pill {{
            font-size: 0.75rem;
            background: var(--accent);
            color: white;
            padding: 0.15rem 0.6rem;
            border-radius: 9999px;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 0.4rem;
        }}

        .qp-title {{
            font-size: 1.35rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--text-main);
            margin-bottom: 0.25rem;
        }}

        .qp-meta {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        .qp-stats-box {{
            display: flex;
            gap: 1.5rem;
            background: var(--surface-elevated);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 0.6rem 1.2rem;
        }}

        .qp-stat {{
            display: flex;
            flex-direction: column;
        }}

        .qp-stat-num {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-main);
        }}

        .qp-stat-lbl {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .qp-panels-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 1.5rem;
            margin-bottom: 1.25rem;
        }}

        .qp-panel-card {{
            background: var(--surface-elevated);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
        }}

        .panel-card-header {{
            margin-bottom: 1rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .panel-heading {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-main);
        }}

        .panel-sub {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .axis-rows-container {{
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
        }}

        .axis-row {{
            display: grid;
            grid-template-columns: 140px 1fr 140px;
            align-items: center;
            gap: 1rem;
            padding: 0.4rem 0;
            border-bottom: 1px dashed rgba(55, 65, 81, 0.4);
        }}

        .axis-row:last-child {{
            border-bottom: none;
        }}

        .axis-name-tag {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-main);
        }}

        .axis-def {{
            font-size: 0.7rem;
            color: var(--text-subtle);
        }}

        .zero-flag-msg {{
            display: block;
            color: var(--red);
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .axis-dist-col {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}

        .dist-bar-track {{
            height: 10px;
            background: rgba(31, 41, 55, 0.8);
            border-radius: 9999px;
            overflow: hidden;
            display: flex;
        }}

        .dist-seg {{
            height: 100%;
            transition: width 0.3s ease;
        }}

        .seg-2 {{
            background: var(--green);
        }}

        .seg-1 {{
            background: var(--amber);
        }}

        .seg-0 {{
            background: var(--red);
        }}

        .dist-legend {{
            display: flex;
            gap: 0.75rem;
            font-size: 0.7rem;
            color: var(--text-muted);
        }}

        .d-val {{
            font-family: ui-monospace, monospace;
        }}

        .d-2 {{
            color: var(--green);
        }}

        .d-1 {{
            color: var(--amber);
        }}

        .d-0 {{
            color: var(--red);
        }}

        .axis-zeros-col {{
            font-size: 0.75rem;
            text-align: right;
        }}

        .zeros-header {{
            color: var(--text-subtle);
            font-size: 0.7rem;
            margin-bottom: 0.15rem;
        }}

        .zeros-none {{
            color: var(--green);
            font-size: 0.75rem;
        }}

        .zero-turn-link {{
            color: var(--red);
            text-decoration: none;
            font-family: ui-monospace, monospace;
            font-weight: 600;
            margin-left: 0.25rem;
        }}

        .zero-turn-link:hover {{
            text-decoration: underline;
        }}

        .mechanical-proxies-block {{
            margin-top: 1.25rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-subtle);
            background: rgba(17, 24, 39, 0.5);
            border-radius: 6px;
            padding: 0.85rem;
        }}

        .proxies-title {{
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }}

        .proxy-stat-row {{
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.35rem;
            flex-wrap: wrap;
        }}

        .proxy-name {{
            color: var(--text-subtle);
        }}

        .proxy-num {{
            font-weight: 600;
            color: var(--text-main);
            font-family: ui-monospace, monospace;
        }}

        .proxy-overlap {{
            color: var(--amber);
            font-size: 0.75rem;
        }}

        .qp-caveat-footer {{
            font-size: 0.75rem;
            color: var(--text-subtle);
            border-top: 1px solid var(--border-subtle);
            padding-top: 0.75rem;
        }}

        .caveat-label {{
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        /* Turn Card Axes Row & Badges */
        .card-axes-row {{
            margin-top: 0.75rem;
            padding-top: 0.6rem;
            border-top: 1px dashed var(--border-subtle);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .axes-label {{
            font-size: 0.7rem;
            color: var(--text-subtle);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }}

        .axes-pills {{
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
        }}

        .axis-pill {{
            font-size: 0.7rem;
            font-family: ui-monospace, monospace;
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
            font-weight: 600;
            cursor: help;
            display: inline-flex;
            gap: 0.2rem;
            border: 1px solid transparent;
        }}

        .axis-pill.score-2 {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border-color: rgba(16, 185, 129, 0.3);
        }}

        .axis-pill.score-1 {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border-color: rgba(245, 158, 11, 0.3);
        }}

        .axis-pill.score-0 {{
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border-color: rgba(239, 68, 68, 0.4);
            font-weight: 700;
        }}

        .axis-pill.extraction-pill {{
            border-style: dashed;
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

        {quality_profile_html}

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
        <div class="footer-primary">Social Proof V2 Reviewer &bull; Read-only loopback server (127.0.0.1) &bull; Zero network egress</div>
        <div class="footer-meta">
            Server HEAD: <span class="font-mono">{html.escape(server_head)}</span> &bull; 
            Artifacts read: {artifacts_meta_str}
        </div>
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
