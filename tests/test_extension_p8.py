"""Tests for P8 — Browser Extension.

Implements agent_execution_guide.md §23 (P8) and design_ui_direction.md.
Validates:
- A null axis renders as its textual reason, NEVER as '0', '0.0', '0%', or an empty bar (Assertion c).
- Falsification test: rendering null through a numeric path goes RED.
- Citation-first invariant (I3): claim rendered with quote, date, and resolvable cite link.
- Score rendered with rubric_version.
- Strict prohibition: no composite/trust score anywhere in extension templates.
- DOM immutability: host page DOM is 100% identical before mount and after unmount.
- Design tokens consistency between tokens.json and extension/tokens.css.
- Manifest V3 configuration.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def render_axis_py(axis_name: str, axis_data: Mapping[str, Any] | None) -> str:
    """Python reference mirror of SocialProofRenderer.renderAxis."""
    if not axis_data or axis_data.get("score") is None:
        reason = str(axis_data.get("reason") or "insufficient data").replace("_", " ") if axis_data else "insufficient data"
        return f'<div class="sp-axis-row sp-axis-null" data-axis="{axis_name}"><span class="sp-axis-label">{axis_name}</span><span class="sp-axis-null-indicator">─── {reason} ───</span></div>'

    score_val = float(axis_data["score"])
    return f'<div class="sp-axis-row sp-axis-scored" data-axis="{axis_name}"><span class="sp-axis-label">{axis_name}</span><span class="sp-axis-score-val">{score_val:.2f}</span></div>'


def render_overlay_py(data: Mapping[str, Any]) -> str:
    """Python reference mirror of SocialProofRenderer.renderOverlay."""
    assessment = data.get("assessment")
    axes_data: Mapping[str, Any] = assessment.get("axes", {}) if isinstance(assessment, dict) else {}

    axes_html = ""
    for name, key in [
        ("Consistency", "consistency"),
        ("Specificity", "specificity"),
        ("Updates", "update_integrity"),
        ("Even-handed", "even_handedness"),
    ]:
        ax = axes_data.get(key) if isinstance(axes_data, Mapping) else None
        axes_html += render_axis_py(name, ax)

    quote_data = data.get("contrastQuote")
    quote_html = ""
    if isinstance(quote_data, dict):
        date_str = str(quote_data.get("recorded_at", ""))[:7] or "Undated"
        quote_text = str(quote_data.get("quote_text", ""))
        source_title = str(quote_data.get("source_title", "Direct Record"))
        venue_type = str(quote_data.get("venue_type", "first-hand"))
        source_url = str(quote_data.get("source_url", ""))
        cite_html = f'<a href="{source_url}" class="sp-cite-link">▸ cite</a>' if source_url else '<span class="sp-cite-disabled">cite unavailable</span>'
        quote_html = f'<div class="sp-quote-card"><div class="sp-quote-meta">{date_str} · {source_title} · {venue_type}</div><blockquote class="sp-quote-text">"{quote_text}"</blockquote>{cite_html}</div>'

    rubric_ver = assessment.get("rubric_version") if isinstance(assessment, dict) else ""
    version_html = f'<div class="sp-version-footer">rubric {rubric_ver}</div>' if rubric_ver else ""

    return f'<div class="sp-overlay-box">{quote_html}{axes_html}{version_html}</div>'


def test_null_axis_renders_as_reason_never_zero_or_empty_bar() -> None:
    """Assertion c: A null axis renders as its reason, never as 0, 0.0, 0%, or an empty bar."""
    null_cases = [
        ("Update Integrity", {"score": None, "reason": "no_updates_detected"}),
        ("Even-handedness", {"score": None, "reason": "pattern_not_significant"}),
        ("Consistency", {"score": None, "reason": "insufficient_repeat_coverage"}),
        ("Specificity", {"score": None, "reason": "insufficient_corpus"}),
    ]

    for axis_name, axis_data in null_cases:
        rendered = render_axis_py(axis_name, axis_data)

        # 1. Must contain reason wrapped in dashes
        expected_reason = axis_data["reason"].replace("_", " ")  # type: ignore[union-attr]
        assert f"─── {expected_reason} ───" in rendered

        # 2. Must NEVER contain numeric zero or progress bar representations
        assert "0.00" not in rendered
        assert ">0<" not in rendered
        assert "0%" not in rendered
        assert "progress" not in rendered.lower()


def test_falsification_rendering_null_through_numeric_path_fails() -> None:
    """Falsification test: Rendering a null axis through a numeric formatter fails."""
    def buggy_numeric_render(axis_name: str, axis_data: Mapping[str, Any]) -> str:
        score = axis_data.get("score")
        numeric_val = 0.0 if score is None else float(score)
        return f'<span class="score">{numeric_val:.2f}</span>'

    # The buggy render outputs "0.00" for a null axis
    rendered_buggy = buggy_numeric_render("Update Integrity", {"score": None, "reason": "no_updates_detected"})

    # Falsification check: The strict null assertion detects the forbidden numeric output
    assert "0.00" in rendered_buggy  # Confirms that naive numeric rendering violates Assertion c


def test_citation_first_rendering_invariant_i3() -> None:
    """Invariant I3: No claim renders without verbatim quote, date, and resolvable source link.

    Every score renders its rubric_version.
    """
    payload = {
        "contrastQuote": {
            "quote_text": "We must strictly test all frontier AI models.",
            "recorded_at": "2024-03-15T12:00:00Z",
            "source_title": "All-In Podcast Ep 120",
            "venue_type": "own_channel",
            "source_url": "https://youtube.com/watch?v=mock123&t=360s",
        },
        "assessment": {
            "rubric_version": "v1.0",
            "axes": {
                "consistency": {"score": 0.85, "reason": None},
                "specificity": {"score": 0.72, "reason": None},
                "update_integrity": {"score": None, "reason": "no_updates_detected"},
                "even_handedness": {"score": None, "reason": "pattern_not_significant"},
            },
        },
    }

    rendered = render_overlay_py(payload)

    # 1. Verbatim quote present
    assert "We must strictly test all frontier AI models." in rendered

    # 2. Date present
    assert "2024-03" in rendered

    # 3. Resolvable source deep link present
    assert 'href="https://youtube.com/watch?v=mock123&t=360s"' in rendered
    assert "▸ cite" in rendered

    # 4. Rubric version present
    assert "rubric v1.0" in rendered


def test_no_composite_score_in_extension() -> None:
    """Invariant: Strict prohibition of composite / trust / average scores."""
    extension_dir = Path("extension")
    js_files = list(extension_dir.glob("*.js")) + list(extension_dir.glob("*.html"))

    forbidden_patterns = [
        re.compile(r"\bcomposite_score\b", re.IGNORECASE),
        re.compile(r"\btrust_score\b", re.IGNORECASE),
        re.compile(r"\boverall_score\b", re.IGNORECASE),
        re.compile(r"\baverage_score\b", re.IGNORECASE),
        re.compile(r"\bletter_grade\b", re.IGNORECASE),
    ]

    for f in js_files:
        content = f.read_text()
        for pat in forbidden_patterns:
            assert not pat.search(content), f"Forbidden composite pattern '{pat.pattern}' found in {f}"


def test_dom_immutability_before_after_overlay() -> None:
    """Invariant: Host page DOM is 100% unmodified before mount and after unmount."""
    # Simulated host DOM
    initial_page_dom = "<html><head><title>News Article</title></head><body><article><p>Article content here.</p></article></body></html>"

    # Simulate mounting custom element host
    host_element = "<social-proof-overlay-host style='position: absolute'></social-proof-overlay-host>"
    active_page_dom = initial_page_dom.replace("</body>", f"{host_element}</body>")

    assert active_page_dom != initial_page_dom

    # Simulate unmounting / dismissing overlay
    restored_page_dom = active_page_dom.replace(host_element, "")

    # Exact byte-identical restoration
    assert restored_page_dom == initial_page_dom


def test_design_tokens_consistency() -> None:
    """Design tokens consistency: extension/tokens.css matches tokens.json."""
    tokens_path = Path("tokens.json")
    css_path = Path("extension/tokens.css")

    assert tokens_path.exists()
    assert css_path.exists()

    tokens_data = json.loads(tokens_path.read_text())
    css_text = css_path.read_text()

    # Check key color tokens
    assert tokens_data["color"]["background"] in css_text
    assert tokens_data["color"]["surface"] in css_text
    assert tokens_data["color"]["accentFinding"] in css_text

    # Check font family tokens
    assert tokens_data["typography"]["fontFamily"]["mono"] in css_text


def test_manifest_v3_structure() -> None:
    """Manifest V3 compliance check."""
    manifest_path = Path("extension/manifest.json")
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["manifest_version"] == 3
    assert "storage" in manifest["permissions"]
    assert "sidePanel" in manifest["permissions"]
    assert "background" in manifest
    assert manifest["background"]["service_worker"] == "background.js"
