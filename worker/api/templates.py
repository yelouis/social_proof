"""Server-side HTML templates for the review site.

Implements design_ui_direction.md §1–§6b:
- Courtroom-archive visual language: dark surface, monospace tags, serif quotes.
- Invariant I3: citation-first rendering with verbatim quotes and offset deep links.
- Invariant I5 / §4: Rendering null — empty axes/sections render explicitly with stated reasons.
- Extension design token reuse without forking.
"""

from __future__ import annotations

import html
from typing import Any

CSS_STYLES = """
:root {
  color-scheme: dark;
  --sp-color-background: #121316;
  --sp-color-surface: #1a1b20;
  --sp-color-surfaceHover: #22242b;
  --sp-color-card: #22242a;
  --sp-color-border: #2e313a;
  --sp-color-borderSubtle: #252730;
  --sp-color-textPrimary: #f0f1f4;
  --sp-color-textSecondary: #9ea3b0;
  --sp-color-textMuted: #686d7c;
  --sp-color-accentFinding: #e5a93c;
  --sp-color-accentCite: #5b8bf7;
  --sp-color-accentCiteHover: #7aa4fc;
  --sp-color-tagBackground: #262933;
  --sp-color-tagText: #b8bdcb;
  --sp-font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --sp-font-quote: 'Newsreader', 'Georgia', 'Times New Roman', serif;
  --sp-font-mono: ui-monospace, 'SF Mono', Menlo, Monaco, monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: var(--sp-color-background);
  color: var(--sp-color-textPrimary);
  font-family: var(--sp-font-sans);
  font-size: 13px;
  line-height: 1.45;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.sp-container {
  max-width: 1040px;
  width: 100%;
  margin: 0 auto;
  padding: 20px;
}

.sp-header {
  border-bottom: 1px solid var(--sp-color-border);
  background: var(--sp-color-surface);
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(8px);
}

.sp-header-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sp-brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
  text-decoration: none;
  color: inherit;
}

.sp-brand-title {
  font-family: var(--sp-font-mono);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--sp-color-textPrimary);
}

.sp-brand-badge {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-accentFinding);
  border: 1px solid rgba(229, 169, 60, 0.35);
  border-radius: 2px;
  padding: 1px 4px;
}

.sp-nav {
  display: flex;
  gap: 16px;
}

.sp-nav-link {
  color: var(--sp-color-textSecondary);
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
  transition: color 0.15s ease;
}

.sp-nav-link:hover, .sp-nav-link.active {
  color: var(--sp-color-textPrimary);
}

.sp-breadcrumbs {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textMuted);
  margin-bottom: 12px;
}

.sp-breadcrumbs a {
  color: var(--sp-color-textSecondary);
  text-decoration: none;
}

.sp-breadcrumbs a:hover {
  text-decoration: underline;
}

.sp-page-title-block {
  margin-bottom: 20px;
  border-bottom: 1px solid var(--sp-color-borderSubtle);
  padding-bottom: 12px;
}

.sp-page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--sp-color-textPrimary);
  letter-spacing: -0.01em;
}

.sp-page-subtitle {
  font-size: 12px;
  color: var(--sp-color-textSecondary);
  margin-top: 4px;
}

.sp-section-heading {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--sp-color-textMuted);
  text-transform: uppercase;
  margin: 24px 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-section-heading::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--sp-color-borderSubtle);
}

.sp-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sp-card {
  background: var(--sp-color-surface);
  border: 1px solid var(--sp-color-border);
  border-radius: 6px;
  padding: 16px;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.sp-card:hover {
  border-color: var(--sp-color-textMuted);
  background: var(--sp-color-surfaceHover);
}

.sp-episode-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}

.sp-episode-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sp-color-textPrimary);
  text-decoration: none;
}

.sp-episode-title:hover {
  text-decoration: underline;
}

.sp-episode-meta {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textSecondary);
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.sp-quote-verbatim {
  font-family: var(--sp-font-quote);
  font-size: 14px;
  font-style: italic;
  line-height: 1.6;
  color: var(--sp-color-textPrimary);
  padding: 12px 16px;
  background: var(--sp-color-card);
  border-left: 3px solid var(--sp-color-accentCite);
  border-radius: 4px;
  margin: 8px 0;
}

.sp-claim-meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textSecondary);
  margin-top: 8px;
}

.sp-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--sp-color-tagBackground);
  color: var(--sp-color-tagText);
}

.sp-badge-support {
  background: rgba(91, 139, 247, 0.15);
  color: #8cb4fc;
  border: 1px solid rgba(91, 139, 247, 0.3);
}

.sp-badge-oppose {
  background: rgba(229, 169, 60, 0.15);
  color: #f0c370;
  border: 1px solid rgba(229, 169, 60, 0.3);
}

.sp-cite-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--sp-color-accentCite);
  text-decoration: none;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 2px;
  border: 1px solid rgba(91, 139, 247, 0.25);
  background: rgba(91, 139, 247, 0.08);
  transition: all 0.15s ease;
}

.sp-cite-link:hover {
  background: rgba(91, 139, 247, 0.2);
  border-color: var(--sp-color-accentCite);
  color: var(--sp-color-accentCiteHover);
}

.sp-cite-disabled {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--sp-color-textMuted);
  font-family: var(--sp-font-mono);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 2px;
  border: 1px dashed var(--sp-color-borderSubtle);
  background: rgba(37, 39, 48, 0.4);
  cursor: not-allowed;
}

.sp-proposition-header {
  background: var(--sp-color-card);
  border: 1px solid var(--sp-color-border);
  border-radius: 6px;
  padding: 16px;
}

.sp-proposition-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--sp-color-textPrimary);
  margin-bottom: 4px;
}

.sp-speaker-info {
  font-size: 12px;
  color: var(--sp-color-textSecondary);
}

.sp-timeline {
  display: flex;
  flex-direction: column;
  position: relative;
  margin-left: 12px;
  border-left: 2px solid var(--sp-color-border);
  padding-left: 16px;
  gap: 16px;
}

.sp-timeline-node {
  position: relative;
}

.sp-timeline-dot {
  position: absolute;
  left: -23px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--sp-color-accentCite);
  border: 2px solid var(--sp-color-background);
}

.sp-timeline-dot.current {
  background: var(--sp-color-accentFinding);
  box-shadow: 0 0 6px rgba(229, 169, 60, 0.6);
}

.sp-timeline-content {
  background: var(--sp-color-surface);
  border: 1px solid var(--sp-color-borderSubtle);
  border-radius: 6px;
  padding: 12px;
}

.sp-timeline-content.current {
  border-color: rgba(229, 169, 60, 0.4);
  background: var(--sp-color-surfaceHover);
}

.sp-axes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.sp-axis-card {
  background: var(--sp-color-surface);
  border: 1px solid var(--sp-color-border);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.sp-axis-name {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  text-transform: uppercase;
  color: var(--sp-color-textSecondary);
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.sp-axis-scored {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.sp-axis-val {
  font-family: var(--sp-font-mono);
  font-size: 22px;
  font-weight: 700;
  color: var(--sp-color-textPrimary);
}

.sp-axis-bar {
  width: 100%;
  height: 4px;
  background: var(--sp-color-tagBackground);
  border-radius: 2px;
  margin-top: 4px;
  overflow: hidden;
}

.sp-axis-bar-fill {
  height: 100%;
  background: var(--sp-color-accentCite);
  border-radius: 2px;
}

.sp-axis-null-state {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textMuted);
  padding: 4px 0;
  text-align: center;
  border-top: 1px dashed var(--sp-color-borderSubtle);
  border-bottom: 1px dashed var(--sp-color-borderSubtle);
  margin: 4px 0;
}

.sp-tension-card {
  background: var(--sp-color-surface);
  border: 1px solid var(--sp-color-border);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
}

.sp-tension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-accentFinding);
  margin-bottom: 12px;
  border-bottom: 1px solid var(--sp-color-borderSubtle);
  padding-bottom: 4px;
}

.sp-null-banner {
  background: var(--sp-color-card);
  border: 1px dashed var(--sp-color-borderSubtle);
  border-radius: 6px;
  padding: 12px 16px;
  color: var(--sp-color-textMuted);
  font-size: 12px;
  font-style: italic;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-person-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.sp-person-card {
  background: var(--sp-color-surface);
  border: 1px solid var(--sp-color-border);
  border-radius: 6px;
  padding: 12px;
  text-decoration: none;
  color: inherit;
  transition: all 0.15s ease;
}

.sp-person-card:hover {
  background: var(--sp-color-surfaceHover);
  border-color: var(--sp-color-textMuted);
}

.sp-person-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--sp-color-textPrimary);
}

.sp-person-stats {
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textSecondary);
  margin-top: 4px;
}

.sp-footer {
  margin-top: auto;
  border-top: 1px solid var(--sp-color-borderSubtle);
  padding: 16px 0;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-color-textMuted);
  text-align: center;
}
"""


def _auth_query(token: str | None) -> str:
    return f"?token={token}" if token else ""


def render_axis(name: str, axis_data: dict[str, Any] | None) -> str:
    """Render an axis score or its explicit null reason."""
    if not axis_data or axis_data.get("score") is None:
        raw_reason = (
            axis_data.get("reason", "insufficient evidence")
            if axis_data
            else "insufficient evidence"
        )
        reason = raw_reason.replace("_", " ")
        return f"""
        <div class="sp-axis-card" data-axis="{html.escape(name)}">
          <div class="sp-axis-name">{html.escape(name)}</div>
          <div class="sp-axis-null-state">─── {html.escape(reason)} ───</div>
          <div style="font-size: 11px; color: var(--sp-color-textMuted);">Nothing to score. Not a low score — an absent one.</div>
        </div>
        """

    score_val = float(axis_data["score"])
    n_val = axis_data.get("n", 0)
    percent = max(0, min(100, int(score_val * 100)))
    return f"""
    <div class="sp-axis-card" data-axis="{html.escape(name)}">
      <div class="sp-axis-name">{html.escape(name)}</div>
      <div class="sp-axis-scored">
        <div class="sp-axis-val">{score_val:.2f}</div>
        <div style="font-size: 11px; color: var(--sp-color-textSecondary);">n={n_val}</div>
      </div>
      <div class="sp-axis-bar">
        <div class="sp-axis-bar-fill" style="width: {percent}%;"></div>
      </div>
    </div>
    """


def render_base_layout(title: str, content: str, token: str | None = None) -> str:
    """Wrap content in base courtroom-archive HTML shell."""
    t_q = _auth_query(token)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} — Social Proof</title>
  <style>{CSS_STYLES}</style>
</head>
<body>
  <header class="sp-header">
    <div class="sp-container sp-header-inner">
      <a href="/{t_q}" class="sp-brand">
        <span class="sp-brand-title">SOCIAL PROOF</span>
        <span class="sp-brand-badge">ARCHIVE</span>
      </a>
      <nav class="sp-nav">
        <a href="/{t_q}" class="sp-nav-link">Episodes</a>
        <a href="/{t_q}#persons" class="sp-nav-link">Persons</a>
      </nav>
    </div>
  </header>
  <main class="sp-container">
    {content}
  </main>
  <footer class="sp-footer">
    <div class="sp-container">
      Courtroom-record evidence archive · Live DuckDB query · Local only · No build step
    </div>
  </footer>
</body>
</html>
"""


def render_index_page(
    episodes: list[dict[str, Any]],
    subjects: list[dict[str, Any]],
    token: str | None = None,
) -> str:
    """Render GET / route (Episodes and Persons)."""
    t_q = _auth_query(token)
    episodes_html: list[str] = []
    for ep in episodes:
        sid = ep["source_id"]
        episodes_html.append(
            f"""
            <div class="sp-card">
              <div class="sp-episode-header">
                <a href="/episode/{sid}{t_q}" class="sp-episode-title">{html.escape(ep['title'])}</a>
                <span class="sp-badge">{ep['claim_count']} claims</span>
              </div>
              <div class="sp-episode-meta">
                <span>{ep['date_formatted']}</span>
                <span>·</span>
                <span>Duration: {ep['duration_formatted']}</span>
                <span>·</span>
                <a href="/episode/{sid}{t_q}" style="color: var(--sp-color-accentCite); text-decoration: none;">Examine claims →</a>
              </div>
            </div>
            """
        )

    persons_html: list[str] = []
    for subj in subjects:
        sub_id = subj["subject_id"]
        persons_html.append(
            f"""
            <a href="/person/{sub_id}{t_q}" class="sp-person-card">
              <div class="sp-person-name">{html.escape(subj['display_name'])}</div>
              <div class="sp-person-stats">{subj['claim_count']} claims across {subj['episode_count']} episode(s)</div>
            </a>
            """
        )

    content = f"""
    <div class="sp-page-title-block">
      <h1 class="sp-page-title">Corpus Evidence Record</h1>
      <p class="sp-page-subtitle">Verbatim claims, chronological timelines, and rubric vectors across {len(episodes)} recorded episodes.</p>
    </div>

    <div class="sp-section-heading">Episodes (Newest First)</div>
    <div class="sp-card-list">
      {''.join(episodes_html)}
    </div>

    <div class="sp-section-heading" id="persons">Persons in Corpus</div>
    <div class="sp-person-grid">
      {''.join(persons_html)}
    </div>
    """
    return render_base_layout("Corpus Evidence Record", content, token)


def render_episode_page(episode: dict[str, Any], token: str | None = None) -> str:
    """Render GET /episode/{source_id} route."""
    t_q = _auth_query(token)
    persons_sections: list[str] = []

    for s_name, p_claims in episode["claims_by_person"].items():
        sub_id = p_claims[0]["subject_id"]
        p_claim_cards: list[str] = []
        for c in p_claims:
            cid = c["claim_id"]
            stance_badge_cls = (
                "sp-badge-support" if c["stance"] == "support" else "sp-badge-oppose"
            )
            cite_html = (
                f'<a href="{c["cite_url"]}" target="_blank" rel="noreferrer" class="sp-cite-link">▸ cite {c["timestamp_formatted"]}</a>'
                if c["cite_url"]
                else f'<span class="sp-cite-disabled" title="{html.escape(c["cite_disabled_reason"] or "")}">▸ cite unavailable ({html.escape(c["cite_disabled_reason"] or "")})</span>'
            )
            p_claim_cards.append(
                f"""
                <div class="sp-card" style="margin-bottom: 8px;">
                  <blockquote class="sp-quote-verbatim">"{html.escape(c['quote_text'])}"</blockquote>
                  <div class="sp-claim-meta-bar">
                    <span class="sp-badge {stance_badge_cls}">{c['stance']}</span>
                    <span>offset {c['timestamp_formatted']}</span>
                    <span>·</span>
                    <span>hedging {c['hedging_level']:.2f}</span>
                    <span>·</span>
                    {cite_html}
                    <span style="margin-left: auto;">
                      <a href="/claim/{cid}{t_q}" style="color: var(--sp-color-accentCite); text-decoration: none;">View Social Proof Panel →</a>
                    </span>
                  </div>
                </div>
                """
            )

        persons_sections.append(
            f"""
            <div style="margin-top: 20px;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                <h2 style="font-size: 14px; font-weight: 600;">{html.escape(s_name)}</h2>
                <a href="/person/{sub_id}{t_q}" style="font-size: 11px; color: var(--sp-color-textSecondary); text-decoration: none;">All claims by {html.escape(s_name)} →</a>
              </div>
              <div class="sp-card-list">
                {''.join(p_claim_cards)}
              </div>
            </div>
            """
        )

    content = f"""
    <div class="sp-breadcrumbs">
      <a href="/{t_q}">Archive</a> &gt; <span>{html.escape(episode['title'])}</span>
    </div>
    <div class="sp-page-title-block">
      <h1 class="sp-page-title">{html.escape(episode['title'])}</h1>
      <div class="sp-episode-meta">
        <span>Recorded: {episode['date_formatted']}</span>
        <span>·</span>
        <span>Duration: {episode['duration_formatted']}</span>
        <span>·</span>
        <span>{episode['total_claims']} verbatim claims recorded</span>
      </div>
    </div>

    <div class="sp-section-heading">Claims Grouped by Speaker (Timestamp Order)</div>
    {''.join(persons_sections) if persons_sections else '<div class="sp-null-banner">No claims recorded for this episode.</div>'}
    """
    return render_base_layout(episode["title"], content, token)


def render_claim_panel_page(panel: dict[str, Any], token: str | None = None) -> str:
    """Render GET /claim/{claim_id} route (Social Proof Panel Depth 2)."""
    t_q = _auth_query(token)
    c = panel["claim"]
    cid = c["claim_id"]
    subj_id = c["subject_id"]
    source_id = c["source_id"]

    stance_badge_cls = (
        "sp-badge-support" if c["stance"] == "support" else "sp-badge-oppose"
    )
    cite_html = (
        f'<a href="{c["cite_url"]}" target="_blank" rel="noreferrer" class="sp-cite-link">▸ cite {c["timestamp_formatted"]}</a>'
        if c["cite_url"]
        else f'<span class="sp-cite-disabled" title="{html.escape(c["cite_disabled_reason"] or "")}">▸ cite unavailable ({html.escape(c["cite_disabled_reason"] or "")})</span>'
    )

    # Timeline nodes
    timeline_nodes: list[str] = []
    for t_claim in panel["timeline"]:
        is_current = t_claim["is_current"]
        t_stance_cls = (
            "sp-badge-support" if t_claim["stance"] == "support" else "sp-badge-oppose"
        )
        t_cite = (
            f'<a href="{t_claim["cite_url"]}" target="_blank" rel="noreferrer" class="sp-cite-link">▸ cite {t_claim["timestamp_formatted"]}</a>'
            if t_claim["cite_url"]
            else f'<span class="sp-cite-disabled" title="{html.escape(t_claim["cite_disabled_reason"] or "")}">▸ cite unavailable</span>'
        )
        t_link = (
            '<span style="color: var(--sp-color-accentFinding); font-weight: bold;">[Viewing This Claim]</span>'
            if is_current
            else f'<a href="/claim/{t_claim["claim_id"]}{t_q}" style="color: var(--sp-color-accentCite); text-decoration: none;">View Claim Record →</a>'
        )
        timeline_nodes.append(
            f"""
            <div class="sp-timeline-node">
              <div class="sp-timeline-dot {'current' if is_current else ''}"></div>
              <div class="sp-timeline-content {'current' if is_current else ''}">
                <div style="display: flex; justify-content: space-between; font-family: var(--sp-font-mono); font-size: 11px; color: var(--sp-color-textSecondary); margin-bottom: 4px;">
                  <span>{t_claim['date_formatted']} · {html.escape(t_claim['source_title'])}</span>
                  <span class="sp-badge {t_stance_cls}">{t_claim['stance']}</span>
                </div>
                <blockquote class="sp-quote-verbatim" style="margin: 4px 0;">"{html.escape(t_claim['quote_text'])}"</blockquote>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                  {t_cite}
                  {t_link}
                </div>
              </div>
            </div>
            """
        )

    timeline_count = len(panel["timeline"])
    timeline_footer = (
        f'<div style="font-size: 11px; color: var(--sp-color-textMuted); margin-top: 8px;">{timeline_count} claim(s) recorded in corpus on this proposition by this speaker.</div>'
        if timeline_count > 1
        else '<div style="font-size: 11px; color: var(--sp-color-textMuted); margin-top: 8px;">1 claim recorded in corpus on this proposition; no prior or subsequent positions by this speaker.</div>'
    )

    # Rubric Axes
    axes_data = panel["axes"]
    evidence_count = sum(
        len(v) for v in panel.get("axis_evidence", {}).values() if isinstance(v, list)
    )
    axes_html = f"""
    <div class="sp-axes-grid">
      {render_axis('Consistency', axes_data.get('consistency'))}
      {render_axis('Specificity', axes_data.get('specificity'))}
      {render_axis('Update Integrity', axes_data.get('update_integrity'))}
      {render_axis('Even-handedness', axes_data.get('even_handedness'))}
    </div>
    <div style="font-family: var(--sp-font-mono); font-size: 11px; color: var(--sp-color-textMuted); margin-top: 8px;">
      rubric {panel.get('rubric_version', 'v1.0')} · {evidence_count} evidence references tracked in assessment
    </div>
    """

    # Published Tensions
    tensions = panel.get("tensions", [])
    if tensions:
        t_cards: list[str] = []
        for t in tensions:
            t_cards.append(
                f"""
                <div class="sp-tension-card">
                  <div class="sp-tension-header">
                    <span>┌─ {html.escape(t['type'].replace('_', ' ').upper())}</span>
                    <span>severity {t['severity']:.2f} ─┐</span>
                  </div>
                  <div class="sp-null-banner">Claim conflict detected across recorded timeline.</div>
                </div>
                """
            )
        tensions_html = "".join(t_cards)
    else:
        tensions_html = """
        <div class="sp-null-banner">
          <span>no unacknowledged reversals or published tensions detected for this proposition</span>
        </div>
        """

    # Principles
    principles_html = """
    <div class="sp-null-banner">
      <span>no principle conflicts detected on this topic</span>
    </div>
    """

    content = f"""
    <div class="sp-breadcrumbs">
      <a href="/{t_q}">Archive</a> &gt;
      <a href="/episode/{source_id}{t_q}">{html.escape(c['source_title'])}</a> &gt;
      <span>Claim {cid}</span>
    </div>

    <div class="sp-proposition-header">
      <div style="font-family: var(--sp-font-mono); font-size: 11px; letter-spacing: 0.08em; color: var(--sp-color-accentCite); text-transform: uppercase; margin-bottom: 4px;">Proposition</div>
      <div class="sp-proposition-text">{html.escape(c['proposition_text'])}</div>
      <div class="sp-speaker-info">Asserted by <a href="/person/{subj_id}{t_q}" style="color: var(--sp-color-textPrimary); font-weight: 600; text-decoration: underline;">{html.escape(c['subject_name'])}</a> in <em>{html.escape(c['source_title'])}</em></div>
    </div>

    <div class="sp-section-heading">Verbatim Record &amp; Citation</div>
    <div class="sp-card">
      <blockquote class="sp-quote-verbatim">"{html.escape(c['quote_text'])}"</blockquote>
      <div class="sp-claim-meta-bar">
        <span class="sp-badge {stance_badge_cls}">{c['stance']}</span>
        <span>recorded {c['date_formatted']}</span>
        <span>·</span>
        <span>offset {c['timestamp_formatted']}</span>
        <span>·</span>
        <span>hedging {c['hedging_level']:.2f}</span>
        <span>·</span>
        {cite_html}
      </div>
    </div>

    <div class="sp-section-heading">Timeline of Verbatim Claims (Primary Artifact)</div>
    <div class="sp-timeline">
      {''.join(timeline_nodes)}
    </div>
    {timeline_footer}

    <div class="sp-section-heading">Four Trust Vectors (Rubric Engine)</div>
    {axes_html}

    <div class="sp-section-heading">Published Tensions</div>
    {tensions_html}

    <div class="sp-section-heading">Principles &amp; Consistency Standards</div>
    {principles_html}
    """
    return render_base_layout(f"Claim {cid}", content, token)


def render_person_page(person: dict[str, Any], token: str | None = None) -> str:
    """Render GET /person/{subject_id} route."""
    t_q = _auth_query(token)
    ep_sections: list[str] = []

    for ep in person["episodes"]:
        c_cards: list[str] = []
        for sc in ep["claims"]:
            cid = sc["claim_id"]
            s_cls = (
                "sp-badge-support" if sc["stance"] == "support" else "sp-badge-oppose"
            )
            c_cards.append(
                f"""
                <div class="sp-card" style="margin-bottom: 6px;">
                  <blockquote class="sp-quote-verbatim">"{html.escape(sc['quote_text'])}"</blockquote>
                  <div class="sp-claim-meta-bar">
                    <span class="sp-badge {s_cls}">{sc['stance']}</span>
                    <span>offset {sc['timestamp_formatted']}</span>
                    <span>·</span>
                    <a href="/claim/{cid}{t_q}" style="color: var(--sp-color-accentCite); text-decoration: none;">Social Proof Panel →</a>
                  </div>
                </div>
                """
            )

        ep_sections.append(
            f"""
            <div style="margin-top: 16px;">
              <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <a href="/episode/{ep['source_id']}{t_q}" style="font-weight: 600; font-size: 14px; color: var(--sp-color-textPrimary); text-decoration: underline;">{html.escape(ep['title'])}</a>
                <span style="font-size: 11px; color: var(--sp-color-textSecondary);">{ep['date_formatted']} · {len(ep['claims'])} claims</span>
              </div>
              <div class="sp-card-list">
                {''.join(c_cards)}
              </div>
            </div>
            """
        )

    content = f"""
    <div class="sp-breadcrumbs">
      <a href="/{t_q}">Archive</a> &gt; <span>{html.escape(person['display_name'])}</span>
    </div>

    <div class="sp-page-title-block">
      <h1 class="sp-page-title">{html.escape(person['display_name'])}</h1>
      <p class="sp-page-subtitle">{person['total_claims']} verbatim claims recorded across {person['total_episodes']} episode(s).</p>
    </div>

    <div class="sp-section-heading">All Claims by Episode</div>
    {''.join(ep_sections)}
    """
    return render_base_layout(person["display_name"], content, token)
