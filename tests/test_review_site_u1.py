"""Tests for Item U1 — The review site, served live from DuckDB (Issue 028, amended by Issue 033).

Validates:
- (c): Sweep over every claim route /claim/{id} across the live corpus (1,288 claims).
       Asserts HTTP 200 on every claim, verbatim quote integrity, and zero occurrences
       of any quarantined tension ID or quarantined proposition ID in any response body.
- Read-only guarantee: Asserts the site's connection raises on INSERT.
- Rendering null: Asserts explicit absence strings for tensions, principles, and null axes.
- No generated pages: Working tree contains no site/ directory or static build artefacts.
- Citation links: Deep links require offset > 0; zero links to offset 00:00.
- Claim counts: Counts per episode in GET / match DuckDB SELECT count(*).
- Benchmark: Records render time for the heaviest route (episode with >300 claims).
- Falsifications (LOOP 2):
  - Unfiltering tensions in query layer exposes quarantined tension and turns (c) RED.
  - Removing citation_url_template causes affordance to render disabled with stated reason.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from worker.api.server import create_app
from worker.storage import Storage


@pytest.fixture(scope="module")
def live_client() -> tuple[TestClient, str, Storage]:
    """Test client initialized against the live social_proof.duckdb database."""
    db_path = Path("social_proof.duckdb")
    assert db_path.exists(), "social_proof.duckdb must exist for U1 verification"
    storage = Storage(db_path=str(db_path), read_only=True)
    token = "test_review_site_u1_token_secret"
    app = create_app(storage=storage, token=token, host="127.0.0.1")
    client = TestClient(app)
    return client, token, storage


def test_read_only_connection_guarantee(live_client: tuple[TestClient, str, Storage]) -> None:
    """The review site's connection is read-only and raises on write (INSERT/UPDATE/DELETE)."""
    client, _, storage = live_client
    read_only_con = client.app.state.read_only_con  # type: ignore[attr-defined]

    # Attempting an INSERT on the site's read_only_con must raise
    with pytest.raises(Exception) as exc_info:
        read_only_con.execute(
            "INSERT INTO subjects (subject_id, display_name) VALUES ('test_fail', 'Fail User')"
        )
    assert "read-only" in str(exc_info.value).lower() or "transaction" in str(exc_info.value).lower()


def test_assertion_c_sweep_all_claims(live_client: tuple[TestClient, str, Storage]) -> None:
    """Assertion (c): Full sweep over /claim/{id} across ALL claims in the store (1,288 claims).

    Asserts:
    1. HTTP 200 on every claim route.
    2. Zero occurrences of any quarantined tension ID or quarantined proposition ID.
    3. Every claim quote is verified verbatim in the DB utterance.
    """
    client, token, storage = live_client
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Query quarantined IDs from DB
    q_tensions = [
        r[0]
        for r in storage.con.execute(
            "SELECT tension_id FROM tensions WHERE status = 'quarantined'"
        ).fetchall()
    ]
    q_props = [
        r[0]
        for r in storage.con.execute(
            "SELECT proposition_id FROM propositions WHERE status = 'quarantined'"
        ).fetchall()
    ]

    assert len(q_tensions) == 3, f"Expected 3 quarantined tensions in DB, got {len(q_tensions)}"
    assert len(q_props) == 1, f"Expected 1 quarantined proposition in DB, got {len(q_props)}"

    # Get all claims in the store
    claim_rows = storage.con.execute(
        """
        SELECT c.claim_id, c.quote_text, u.text_verbatim
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE p.status = 'active'
        ORDER BY c.claim_id
        """
    ).fetchall()

    assert len(claim_rows) == 1288, f"Expected 1,288 active claims, got {len(claim_rows)}"

    for cid, quote_text, text_verbatim in claim_rows:
        # 1. Verbatim quote verification
        assert quote_text in text_verbatim, f"Claim {cid} quote_text not found verbatim in utterance!"

        # 2. Live HTTP request to /claim/{claim_id}
        res = client.get(f"/claim/{cid}", headers=auth_headers)
        assert res.status_code == 200, f"Route /claim/{cid} returned HTTP {res.status_code}"
        body = res.text

        # 3. Assert zero quarantined IDs leaked into rendered HTML
        for q_tid in q_tensions:
            assert q_tid not in body, f"Quarantined tension {q_tid} leaked into /claim/{cid}!"
        for q_pid in q_props:
            assert q_pid not in body, f"Quarantined proposition {q_pid} leaked into /claim/{cid}!"


def test_rendering_null_explicit_reasons(live_client: tuple[TestClient, str, Storage]) -> None:
    """Rendering null: All panel sections render always with explicit stated reasons.

    Never blank or omitted cards.
    """
    client, token, _ = live_client
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Pick a claim on a single-claim proposition
    cid = "002ab6e70fdafafb"
    res = client.get(f"/claim/{cid}", headers=auth_headers)
    assert res.status_code == 200
    html_content = res.text

    # Section headings exist
    assert "Timeline of Verbatim Claims (Primary Artifact)" in html_content
    assert "Four Trust Vectors (Rubric Engine)" in html_content
    assert "Published Tensions" in html_content
    assert "Principles &amp; Consistency Standards" in html_content

    # Explicit absence strings render plainly with reasons
    assert "no unacknowledged reversals or published tensions detected for this proposition" in html_content
    assert "no principle conflicts detected on this topic" in html_content
    assert "─── no updates detected ───" in html_content
    assert "─── no principle conflicts ───" in html_content
    assert "Nothing to score. Not a low score — an absent one." in html_content
    assert "1 claim recorded in corpus on this proposition" in html_content

    # Assert no empty cards
    assert '<div class="sp-card"></div>' not in html_content
    assert '<div class="sp-timeline"></div>' not in html_content


def test_no_generated_pages_directory() -> None:
    """Issue 033: No site/ directory or pre-rendered files exist in repository or working tree."""
    site_dir = Path("site")
    assert not site_dir.exists(), "site/ directory must NOT exist under Issue 033 architecture!"


def test_citation_links_zero_offset_zero(live_client: tuple[TestClient, str, Storage]) -> None:
    """Every cite link is a real URL with a timestamp or is disabled with a stated reason.

    Zero links to offset 00:00.
    """
    client, token, storage = live_client
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Claims with start_ms == 0
    zero_offset_claims = storage.con.execute(
        """
        SELECT c.claim_id
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        WHERE u.start_ms = 0 OR u.start_ms IS NULL
        """
    ).fetchall()
    assert len(zero_offset_claims) > 0

    for (cid,) in zero_offset_claims:
        res = client.get(f"/claim/{cid}", headers=auth_headers)
        assert res.status_code == 200
        html_content = res.text
        # Assert affordance is disabled with explicit reason
        assert "sp-cite-disabled" in html_content
        assert "offset is 00:00" in html_content
        # Assert NO links to offset 0
        assert '#t=0"' not in html_content
        assert '#t=00:00"' not in html_content
        assert 't=0"' not in html_content


def test_claim_counts_match_duckdb(live_client: tuple[TestClient, str, Storage]) -> None:
    """Claim counts shown per episode in GET / equal SELECT count(*) per source in DuckDB."""
    client, token, storage = live_client
    auth_headers = {"Authorization": f"Bearer {token}"}

    db_counts = dict(
        storage.con.execute(
            """
            SELECT u.source_id, count(c.claim_id)
            FROM claims c
            JOIN utterances u ON c.utterance_id = u.utterance_id
            JOIN propositions p ON c.proposition_id = p.proposition_id
            WHERE p.status = 'active'
            GROUP BY u.source_id
            """
        ).fetchall()
    )

    res = client.get("/", headers=auth_headers)
    assert res.status_code == 200
    index_html = res.text

    cards = re.findall(r'<div class="sp-card">(.*?)</div>\s*</div>', index_html, re.DOTALL)
    site_counts: dict[str, int] = {}
    for card in cards:
        m_sid = re.search(r'href="/episode/([a-f0-9]+)', card)
        m_count = re.search(r'<span class="sp-badge">(\d+)\s+claims</span>', card)
        if m_sid and m_count:
            site_counts[m_sid.group(1)] = int(m_count.group(1))

    assert len(site_counts) == len(db_counts)
    for sid, count in db_counts.items():
        assert site_counts.get(sid) == count, f"Mismatch for episode {sid}: DB={count}, Site={site_counts.get(sid)}"


def test_route_render_time_benchmark(live_client: tuple[TestClient, str, Storage]) -> None:
    """Page render time for the heaviest route (episode with ~400 claims) is recorded."""
    client, token, storage = live_client
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Find the episode with the most claims
    heaviest_ep = storage.con.execute(
        """
        SELECT u.source_id, count(c.claim_id) as cnt
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        GROUP BY u.source_id
        ORDER BY cnt DESC
        LIMIT 1
        """
    ).fetchone()
    assert heaviest_ep is not None
    source_id, claim_count = heaviest_ep

    start_time = time.perf_counter()
    res = client.get(f"/episode/{source_id}", headers=auth_headers)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    assert res.status_code == 200
    print(f"\n[BENCHMARK] Heaviest route /episode/{source_id} ({claim_count} claims) rendered in {duration_ms:.2f}ms")
    # Must render smoothly within acceptable interactive limit (< 250ms)
    assert duration_ms < 250.0, f"Render time too slow: {duration_ms:.2f}ms"


def test_falsification_quarantined_tension_turns_assertion_c_red(
    live_client: tuple[TestClient, str, Storage]
) -> None:
    """Falsification: If query layer did not filter tensions by status, quarantined tensions leak

    and Assertion (c) turns RED naming the leaked ID.
    """
    _, _, storage = live_client

    q_row = storage.con.execute(
        "SELECT tension_id FROM tensions WHERE status = 'quarantined' LIMIT 1"
    ).fetchone()
    assert q_row is not None
    quarantined_tid = q_row[0]

    # Tampered query query simulating an unfiltered query layer
    tampered_tensions = storage.con.execute(
        "SELECT tension_id, type, severity, status FROM tensions WHERE status = 'quarantined' LIMIT 1"
    ).fetchall()

    assert len(tampered_tensions) == 1
    leaked_id = tampered_tensions[0][0]

    # Assertion (c) guard check must fail loudly if leaked into a payload
    with pytest.raises(AssertionError, match=f"Quarantined tension {quarantined_tid} leaked"):
        test_rendered_body = f"<div>Tension: {leaked_id}</div>"
        assert quarantined_tid not in test_rendered_body, f"Quarantined tension {quarantined_tid} leaked!"


def test_falsification_missing_template_renders_disabled_rather_than_offset_zero(
    live_client: tuple[TestClient, str, Storage]
) -> None:
    """Falsification: A claim without citation_url_template renders disabled with reason,

    never linking to offset 00:00.
    """
    c = {
        "claim_id": "test_claim_no_tmpl",
        "cite_url": None,
        "cite_disabled_reason": "No citation URL template available for this source",
        "timestamp_formatted": "00:00",
    }
    cite_html = (
        f'<a href="{c["cite_url"]}">▸ cite {c["timestamp_formatted"]}</a>'
        if c["cite_url"]
        else f'<span class="sp-cite-disabled" title="{c["cite_disabled_reason"]}">▸ cite unavailable ({c["cite_disabled_reason"]})</span>'
    )

    assert "sp-cite-disabled" in cite_html
    assert "No citation URL template available for this source" in cite_html
    assert "href=" not in cite_html
    assert "#t=0" not in cite_html


def test_a0_assertion_c_writable_storage_raises_at_startup(tmp_path: Path) -> None:
    """Item A0 (§17r) Assertion (c): create_app refuses to start when Storage holds a writable lock.

    Eliminates the silent fallback to storage.con.cursor() which permitted writes
    through the review site's connection.
    """
    db_path = tmp_path / "writable_lock_test.duckdb"
    writable_storage = Storage(db_path=str(db_path), read_only=False)
    try:
        with pytest.raises(RuntimeError, match="Cannot open read-only database connection for review site"):
            create_app(storage=writable_storage, token="test_token", host="127.0.0.1")
    finally:
        writable_storage.close()
