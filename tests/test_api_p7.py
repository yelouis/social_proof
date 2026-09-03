"""Tests for P7 — Local API.

Implements agent_execution_guide.md §22 (P7) and design_local_api_and_clients.md.
Validates:
- Loopback binding enforcement (raises ValueError on 0.0.0.0 or external host).
- Bearer token authentication & uniform 404 response on bad tokens.
- Strict CORS rejecting wildcard * unconditionally.
- Selection-triggered /resolve (Assertion c, Journey J8): asserts zero rows with
  origin = 'page_context' and no claims or propositions created from page context.
- Falsification test: deliberately persisting page context fails verify_no_page_context.
- Compare endpoint returns HTTP 409 Conflict on rubric_version mismatch.
- Invariant I8: No client write endpoints directly modifying the claim store.
- Assessment response includes complete version provenance.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from worker.api.security import CORSPolicy, validate_host
from worker.api.server import create_app
from worker.entities import Proposition, Subject
from worker.extract.dedup import stub_hash_embedding
from worker.integrity import verify_no_page_context
from worker.storage import Storage, compute_proposition_id


class MockApiEmbedder:
    """Deterministic mock embedder for API testing."""

    def __init__(self) -> None:
        self.model_name = "mock-api-embedder"

    def embed_document(self, text: str) -> list[float]:
        return stub_hash_embedding(f"search_document: {text}")

    def embed_query(self, text: str) -> list[float]:
        return stub_hash_embedding(f"search_query: {text}")


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "api_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


@pytest.fixture
def test_client(test_store: Storage) -> tuple[TestClient, str]:
    token = "test_secret_bearer_token_12345"
    embedder = MockApiEmbedder()
    app = create_app(storage=test_store, token=token, embedder=embedder, host="127.0.0.1")
    client = TestClient(app)
    return client, token


def test_loopback_binding_enforcement(test_store: Storage) -> None:
    """Security control 1: Local API binds loopback only; raises on 0.0.0.0 or external IPs."""
    # 1. Non-loopback host raises ValueError
    with pytest.raises(ValueError, match="127.0.0.1 loopback only"):
        validate_host("0.0.0.0")

    with pytest.raises(ValueError, match="127.0.0.1 loopback only"):
        validate_host("192.168.1.10")

    # 2. Loopback passes
    validate_host("127.0.0.1")
    validate_host("localhost")

    # 3. Application factory raises on 0.0.0.0
    with pytest.raises(ValueError, match="127.0.0.1 loopback only"):
        create_app(storage=test_store, host="0.0.0.0")


def test_bearer_token_authentication(test_client: tuple[TestClient, str]) -> None:
    """Security control 2 & 4: Bearer token auth; bad token emits uniform 404."""
    client, token = test_client

    # 1. Missing token -> 404 (uniform response matching unknown route)
    res_no_token = client.get("/health")
    assert res_no_token.status_code == 404
    assert res_no_token.json() == {"detail": "Not Found"}

    # 2. Bad token -> 404
    res_bad_token = client.get("/health", headers={"Authorization": "Bearer bad_token"})
    assert res_bad_token.status_code == 404
    assert res_bad_token.json() == {"detail": "Not Found"}

    # 3. Valid token -> 200
    res_valid = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "ok"


def test_strict_cors_rejects_wildcard() -> None:
    """Security control 3: Wildcard * is rejected unconditionally; extension origins allowed."""
    # 1. Wildcard is rejected
    assert CORSPolicy.is_allowed_origin("*") is False
    assert CORSPolicy.is_allowed_origin(None) is False
    assert CORSPolicy.is_allowed_origin("") is False

    # 2. Hostile web page origin rejected
    assert CORSPolicy.is_allowed_origin("https://evil-site.com") is False
    assert CORSPolicy.is_allowed_origin("http://attacker.local:8080") is False

    # 3. Chrome and Mozilla extension origins permitted
    assert CORSPolicy.is_allowed_origin("chrome-extension://abcdefghijklmnopqrstuvwxyz123456") is True
    assert CORSPolicy.is_allowed_origin("moz-extension://a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True

    # 4. Local loopback permitted
    assert CORSPolicy.is_allowed_origin("http://127.0.0.1:8787") is True
    assert CORSPolicy.is_allowed_origin("http://localhost:3000") is True


def test_post_resolve_selection_triggered_journey_j8_assertion_c(
    test_client: tuple[TestClient, str],
    test_store: Storage,
) -> None:
    """Assertion c & Journey J8: POST /resolve processes selection in memory only;

    asserts zero rows anywhere with origin = 'page_context' and no created entities.
    """
    client, token = test_client

    # Populate subject and proposition in DuckDB
    subject = Subject(subject_id="subj_test_01", display_name="Dr. Jane Scientist")
    test_store.insert_subject(subject)

    prop_text = "mandatory AI compute threshold auditing prevents rogue training runs"
    prop_id = compute_proposition_id(prop_text)
    prop = Proposition(proposition_id=prop_id, canonical_text=prop_text, subject_ids=[subject.subject_id])
    test_store.insert_proposition(prop)
    test_store.insert_proposition_embedding(prop_id, stub_hash_embedding(f"search_document: {prop_text}"))

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "selected_text": "mandatory AI compute threshold auditing prevents rogue training runs",
        "context_before": "According to Dr. Jane Scientist in a recent interview,",
        "context_after": "which has sparked widespread debate across the sector.",
        "page_url": "https://news.hostile-example.com/articles/ai-audit-controversy",
        "page_title": "Hostile External News Report",
    }

    r_c0 = test_store.con.execute("SELECT count(*) FROM claims").fetchone()
    initial_claims_count = int(r_c0[0]) if r_c0 else 0
    r_p0 = test_store.con.execute("SELECT count(*) FROM propositions").fetchone()
    initial_props_count = int(r_p0[0]) if r_p0 else 0
    r_s0 = test_store.con.execute("SELECT count(*) FROM sources").fetchone()
    initial_sources_count = int(r_s0[0]) if r_s0 else 0

    # Call /resolve
    res = client.post("/resolve", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    # Verify resolved subjects and proposition
    assert len(data["subjects"]) >= 1
    assert data["subjects"][0]["subject_id"] == subject.subject_id
    assert data["proposition"] is not None
    assert data["proposition"]["id"] == prop_id

    # CRITICAL ASSERTION C & JOURNEY J8: Zero rows created in database
    r_c1 = test_store.con.execute("SELECT count(*) FROM claims").fetchone()
    final_claims_count = int(r_c1[0]) if r_c1 else 0
    r_p1 = test_store.con.execute("SELECT count(*) FROM propositions").fetchone()
    final_props_count = int(r_p1[0]) if r_p1 else 0
    r_s1 = test_store.con.execute("SELECT count(*) FROM sources").fetchone()
    final_sources_count = int(r_s1[0]) if r_s1 else 0

    assert final_claims_count == initial_claims_count
    assert final_props_count == initial_props_count
    assert final_sources_count == initial_sources_count

    # Verify integrity guard: zero rows with origin = 'page_context'
    claim_rows = test_store.con.execute("SELECT * FROM claims").fetchall()
    records = [{"origin": "page_context"} for r in claim_rows if "page_context" in str(r)]
    integrity_res = verify_no_page_context(records)
    assert integrity_res.passed is True


def test_falsification_deliberate_persistence_fails_page_context_check(test_store: Storage) -> None:
    """Falsification test for Journey J8: Persisting page context causes verify_no_page_context to go RED."""
    # Deliberately construct records containing a row originating from page_context
    contaminated_records = [
        {"claim_id": "legit_claim_1", "origin": "podcast_rss"},
        {"claim_id": "bad_page_context_claim", "origin": "page_context"},
    ]

    integrity_res = verify_no_page_context(contaminated_records)
    # The check must catch the contaminated row and FAIL (RED)
    assert integrity_res.passed is False
    assert "page_context" in integrity_res.message


def test_compare_returns_409_on_version_mismatch(
    test_client: tuple[TestClient, str],
    test_store: Storage,
) -> None:
    """Head-to-head comparison: returns HTTP 409 Conflict if rubric versions differ."""
    client, token = test_client

    subj_a = Subject(subject_id="subj_cmp_a", display_name="Subject A")
    subj_b = Subject(subject_id="subj_cmp_b", display_name="Subject B")
    test_store.insert_subject(subj_a)
    test_store.insert_subject(subj_b)

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Matching versions -> 200 OK
    res_ok = client.get("/compare?a=subj_cmp_a&b=subj_cmp_b&topic=global", headers=headers)
    assert res_ok.status_code == 200
    assert res_ok.json()["rubric_version"] == "v1.0"

    # 2. If app rubric engine is updated to version v2.0 for subject B, comparison must 409
    from worker.rubric.engine import RubricEngine
    client.app.state.rubric_engine = RubricEngine(storage=test_store, rubric_version="v2.0")  # type: ignore[attr-defined]

    # Pre-calculate assessment for subj_a with v1.0, while engine is now v2.0
    from worker.entities import Assessment
    test_store.insert_assessment(
        Assessment(
            assessment_id="subj_cmp_a|global|v1.0",
            subject_id="subj_cmp_a",
            topic_id="global",
            rubric_version="v1.0",
        )
    )

    # Calling compare where A is v1.0 and B is v2.0 -> returns 409
    # Monkey-patch assess_subject_topic to return different versions
    def mock_assess(subject_id: str, topic_id: str = "global") -> Assessment:
        ver = "v1.0" if subject_id == "subj_cmp_a" else "v2.0"
        return Assessment(
            assessment_id=f"{subject_id}|{topic_id}|{ver}",
            subject_id=subject_id,
            topic_id=topic_id,
            rubric_version=ver,
        )

    client.app.state.rubric_engine.assess_subject_topic = mock_assess  # type: ignore[attr-defined]

    res_conflict = client.get("/compare?a=subj_cmp_a&b=subj_cmp_b&topic=global", headers=headers)
    assert res_conflict.status_code == 409
    assert "Conflict" in res_conflict.json()["detail"]


def test_client_write_endpoints_prohibited_invariant_i8(test_client: tuple[TestClient, str]) -> None:
    """Invariant I8: Verify no write endpoints for clients exist, except POST /resolve and POST /ingest."""
    client, _ = test_client
    app = client.app

    # Enumerate all registered routes and methods
    write_routes: list[tuple[str, str]] = []
    for route in app.routes:  # type: ignore[attr-defined]
        methods: set[str] = set(getattr(route, "methods", set()))
        path = getattr(route, "path", "")
        for m in methods:
            if m in ("POST", "PUT", "PATCH", "DELETE"):
                write_routes.append((m, path))

    # Permitted write routes: only /resolve (in-memory) and /ingest (job enqueue)
    allowed_write_paths = {"/resolve", "/ingest"}
    for method, path in write_routes:
        assert path in allowed_write_paths, f"Forbidden write route found: {method} {path}"


def test_assessment_returns_version_provenance(
    test_client: tuple[TestClient, str],
    test_store: Storage,
) -> None:
    """GET /subjects/{id}/assessment returns complete version provenance."""
    client, token = test_client

    subj = Subject(subject_id="subj_prov_api", display_name="Provenance Subject")
    test_store.insert_subject(subj)

    headers = {"Authorization": f"Bearer {token}"}
    res = client.get(f"/subjects/{subj.subject_id}/assessment", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["rubric_version"] == "v1.0"
    assert data["detector_version"] == "v1.0"
    assert data["embedding_model"] == "nomic-embed-text-v1.5"
    assert data["nlp_version"] == "v1.0-regex-ner"
    assert "axes" in data
    assert "sufficiency" in data
