"""Tests for B5: Local review page showing what was extracted, and what was not.

Validates:
- Assertion (c): Every turn in the most recent episode appears on the page, count matching B1's,
  each carrying either its claims or its exclusion gate; and the four gate percentages shown match
  B3's reported figures.
- Progressive rendering: Renders correctly with B1 alone, with B1+B2, and with all three (B1+B2+B3).
- Model provenance: Model ID, quantisation, runtime, prompt version, and rubric commit hash.
- Zero external network requests: Assert no external script, css, font, or image URLs.
- Falsification: Removing turns triggers count discrepancy error naming the missing count.
- Loopback serving & read-only guarantee: Binds to 127.0.0.1, handles GET, rejects writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from v2.src.review import (
    TurnCountMismatchError,
    load_episode_data,
    render_review_html,
    validate_episode_turns,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"

REFERENCE_EPISODE = "00251a80c868f535"  # All-In E287


def test_assertion_c_every_turn_appears_and_gate_percentages_match_b3():
    """Assertion (c) verbatim:

    'every turn in the most recent episode appears on the page, count matching B1's, each carrying
    either its claims or its exclusion gate; and the four gate percentages shown match B3's reported figures.'
    """
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    # 1. Turn count matching B1's exactly (405 turns)
    b1_turn_count = data["metrics"]["turn_count"]
    assert b1_turn_count == 405
    assert len(data["turns"]) == 405

    html = render_review_html(data)

    # 2. Every turn in the episode appears on the page
    for turn in data["turns"]:
        turn_id = turn["turn_id"]
        assert f'id="{turn_id}"' in html or f"id='{turn_id}'" in html, f"Turn {turn_id} missing from rendered page"

    # Count rendered turn elements in HTML
    turn_article_matches = re.findall(r'class="[^"]*\bturn-card\b[^"]*"', html)
    assert len(turn_article_matches) == 405, f"Expected 405 rendered turn cards, found {len(turn_article_matches)}"

    # 3. Each turn carrying either its claims or its exclusion gate
    for turn in data["turns"]:
        turn_id = turn["turn_id"]
        # Model verdict must be present
        model_verdict = turn.get("model_verdict")
        assert model_verdict is not None, f"Turn {turn_id} has no model verdict"
        assert model_verdict in ("claim", "exclusion"), f"Turn {turn_id} invalid verdict: {model_verdict}"
        if model_verdict == "claim":
            assert turn.get("model_claims") or turn.get("model_claim"), f"Turn {turn_id} claim verdict with no claim payload"
        else:
            assert turn.get("model_gate") in ("gate_1", "gate_2", "gate_3", "gate_4"), f"Turn {turn_id} exclusion without valid gate"

    # 4. The four gate percentages shown match B3's reported figures
    # B3 reported: Gate 1: 405 (100.00%), Gate 2: 0 (0.00%), Gate 3: 0 (0.00%), Gate 4: 0 (0.00%)
    gate_counts = data["gate_distributions"]["model"]["counts"]
    gate_pcts = data["gate_distributions"]["model"]["percentages"]

    assert gate_counts["gate_1"] == 405
    assert gate_counts["gate_2"] == 0
    assert gate_counts["gate_3"] == 0
    assert gate_counts["gate_4"] == 0

    assert gate_pcts["gate_1"] == 100.0
    assert gate_pcts["gate_2"] == 0.0
    assert gate_pcts["gate_3"] == 0.0
    assert gate_pcts["gate_4"] == 0.0

    # Ensure these percentages appear in the rendered HTML
    assert "100.0%" in html or "100%" in html
    assert "Gate 1" in html
    assert "Gate 2" in html
    assert "Gate 3" in html
    assert "Gate 4" in html


def test_progressive_rendering_b1_alone():
    """The page renders correctly with B1's output alone — turns, speakers, timestamps,

    ad-stripped spans marked — and says plainly that no claims have been extracted yet.
    """
    # Pick an episode with B1 transcripts only (e.g. 5d5cfe08c004e87c)
    other_ep = "5d5cfe08c004e87c"
    data = load_episode_data(
        source_id=other_ep,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    assert data["has_gold"] is False
    assert data["has_extraction"] is False
    assert len(data["turns"]) == data["metrics"]["turn_count"]

    html = render_review_html(data)

    # Must state plainly that no claims have been extracted yet
    assert "no claims have been extracted yet" in html.lower()

    # Must display turns, speakers, timestamps
    first_turn = data["turns"][0]
    assert first_turn["turn_id"] in html
    assert first_turn["speaker_label"] in html

    # Ad-stripped spans marked if any exist
    stripped_turns = [t for t in data["turns"] if t.get("stripped")]
    if stripped_turns:
        assert "stripped" in html.lower()


def test_progressive_rendering_b1_and_b2_gold_only(tmp_path):
    """The page renders correctly with B1 + B2 (gold dataset present, model extraction absent)."""
    # Create an isolated scenario with B1 transcript + B2 gold, but no extraction artifact
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=tmp_path,  # empty extraction dir
    )

    assert data["has_gold"] is True
    assert data["has_extraction"] is False

    html = render_review_html(data)

    # Shows gold distribution (Gate 1: 302, Gate 2: 8, Gate 3: 6, Gate 4: 56)
    assert "302" in html
    assert "56" in html
    assert "no model claims extracted yet" in html.lower() or "no claims have been extracted yet" in html.lower()


def test_side_by_side_disagreements_match_b4():
    """Step 4: On B2's labelled episode, show model and human side by side.

    Three states per turn: both agree claim, both agree not, they disagree. Disagreement count must match B4's (33
    disagreements).
    """
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    assert data["has_gold"] is True
    assert data["has_extraction"] is True

    # Count disagreement states
    disagreements = [t for t in data["turns"] if t["agreement_state"] in ("disagreement_fn", "disagreement_fp")]
    assert len(disagreements) == 33, f"Expected 33 disagreements matching B4, found {len(disagreements)}"

    agreed_exclusions = [t for t in data["turns"] if t["agreement_state"] == "agreed_exclusion"]
    assert len(agreed_exclusions) == 372

    agreed_claims = [t for t in data["turns"] if t["agreement_state"] == "agreed_claim"]
    assert len(agreed_claims) == 0

    html = render_review_html(data)
    assert "disagreement" in html.lower()
    assert "33" in html


def test_model_identity_displayed():
    """Step 5: Show the model identity on every page.

    Model id, quantisation, runtime, prompt version, and the rubric commit hash.
    """
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    html = render_review_html(data)

    # Model metadata fields must be present
    assert "mlx-community/gemma-2-2b-it-4bit" in html
    assert "4-bit" in html
    assert "mlx" in html.lower()
    assert "23da31c" in html  # Rubric commit


def test_zero_network_requests():
    """Validation: No network requests from the served page.

    Assert it; a local tool that phones out is not a local tool.
    """
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    html = render_review_html(data)

    # Check for external resource links in href, src, or CSS @import
    # Allowed: local fragment links (#turn-..., etc.) or relative links (?episode=...)
    external_links = re.findall(r'(?:src|href|url)\s*=\s*["\'](https?://[^"\']+)["\']', html)
    assert len(external_links) == 0, f"Found external resource requests: {external_links}"

    # Also ensure no @import url(...) to external domain
    css_external_imports = re.findall(r'@import\s+url\(["\']?(https?://[^"\')]+)["\']?\)', html)
    assert len(css_external_imports) == 0, f"Found external CSS @import: {css_external_imports}"


def test_falsification_turn_count_discrepancy():
    """Falsify: Point it at a turn file with three turns removed; the count check

    must fail and name the discrepancy. Restore; record both.
    """
    with open(TRANSCRIPT_DIR / f"{REFERENCE_EPISODE}.json", "r", encoding="utf-8") as f:
        full_data = json.load(f)

    # Mutate: remove 3 turns from turns list, keeping metrics.turn_count at 405
    corrupted_data = dict(full_data)
    corrupted_data["turns"] = full_data["turns"][:-3]
    assert len(corrupted_data["turns"]) == 402
    assert corrupted_data["metrics"]["turn_count"] == 405

    with pytest.raises(TurnCountMismatchError) as exc_info:
        validate_episode_turns(corrupted_data)

    # Must name the discrepancy
    error_msg = str(exc_info.value)
    assert "402" in error_msg
    assert "405" in error_msg
    assert "discrepancy" in error_msg.lower() or "mismatch" in error_msg.lower()


def test_server_loopback_and_read_only():
    """Validates that create_server binds strictly to 127.0.0.1, handles GET /health

    and GET /?episode=..., and rejects POST/PUT/DELETE with 405 Method Not Allowed.
    """
    import threading
    import urllib.error
    import urllib.request

    from v2.scripts.serve_review import create_server

    # Invalid host binding must be rejected
    with pytest.raises(ValueError):
        create_server(host="0.0.0.0", port=8999)

    server = create_server(host="127.0.0.1", port=8998)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # GET /health
        req = urllib.request.Request("http://127.0.0.1:8998/health")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            health_json = json.loads(resp.read().decode("utf-8"))
            assert health_json["status"] == "ok"
            assert health_json["read_only"] is True
            assert health_json["host"] == "127.0.0.1"

        # GET /
        req = urllib.request.Request(f"http://127.0.0.1:8998/?episode={REFERENCE_EPISODE}")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Social Proof V2 Review" in html
            assert "All-In E287" in html
            assert "Gate 1" in html

        # POST / should raise HTTP 405 Method Not Allowed
        post_req = urllib.request.Request(
            "http://127.0.0.1:8998/",
            data=b'{"bad": "write"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(post_req)
        assert err.value.code == 405

    finally:
        server.shutdown()
        server.server_close()

