"""Tests for DuckDB Storage layer, deterministic IDs, VSS embeddings, and Parquet artifacts (U1)."""

import uuid
from pathlib import Path

import pytest

from fixtures.fixture_loader import load_valid_fixtures
from worker.entities import (
    Claim,
    Proposition,
    Source,
    SourceSubjectRole,
    Subject,
    Utterance,
)
from worker.storage import (
    ArtifactStore,
    Storage,
    compute_assessment_id,
    compute_claim_id,
    compute_principle_id,
    compute_proposition_id,
    compute_role_id,
    compute_source_id,
    compute_tension_id,
    compute_utterance_id,
    normalize_canonical_text,
)


def test_deterministic_ids_are_reproducible_and_content_derived() -> None:
    src_id_1 = compute_source_id("https://youtube.com/watch?v=abc123")
    src_id_2 = compute_source_id("https://youtube.com/watch?v=abc123")
    assert src_id_1 == src_id_2
    assert len(src_id_1) == 16

    utt_id_1 = compute_utterance_id(src_id_1, 1000, "Hello world")
    utt_id_2 = compute_utterance_id(src_id_1, 1000, "Hello world")
    assert utt_id_1 == utt_id_2

    prop_id_1 = compute_proposition_id("Federal Licensing of Frontier Models")
    prop_id_2 = compute_proposition_id("federal licensing of frontier models")
    assert prop_id_1 == prop_id_2

    claim_id_1 = compute_claim_id(utt_id_1, prop_id_1, "support", "gemma-3-27b-it:v1:s1")
    claim_id_2 = compute_claim_id(utt_id_1, prop_id_1, "support", "gemma-3-27b-it:v1:s1")
    assert claim_id_1 == claim_id_2

    princ_id = compute_principle_id("an elected official who misleads should resign")
    assert len(princ_id) == 16

    # Tension ID is order-independent
    t_id_1 = compute_tension_id("clm_a", "clm_b", "unacknowledged_reversal")
    t_id_2 = compute_tension_id("clm_b", "clm_a", "unacknowledged_reversal")
    assert t_id_1 == t_id_2

    asm_id = compute_assessment_id("subj_1", "topic_1", "v1.2")
    assert len(asm_id) == 16


def test_entity_round_trip(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()

    subject = Subject(
        subject_id="subj_test_01",
        display_name="Test Subject",
        aliases=["Alias A"],
        handles={"x": "test_subj"},
        created_at="2024-01-01T00:00:00Z",
    )
    store.insert_subject(subject)
    fetched_subj = store.get_subject("subj_test_01")
    assert fetched_subj is not None
    assert fetched_subj.display_name == subject.display_name
    assert fetched_subj.aliases == subject.aliases
    assert fetched_subj.handles == subject.handles

    source = sources[0]
    store.insert_source(source)
    fetched_src = store.get_source(source.source_id)
    assert fetched_src is not None
    assert fetched_src.title == source.title
    assert fetched_src.canonical_url == source.canonical_url
    assert fetched_src.citation_url_template == source.citation_url_template

    # Insert subject before role for foreign key constraint
    store.insert_subject(Subject(subject_id=roles[0].subject_id, display_name="Role Subject"))
    role = roles[0]
    store.insert_source_role(role)
    fetched_role = store.get_source_role(role.source_id, role.subject_id)
    assert fetched_role is not None
    assert fetched_role.tier == role.tier
    assert fetched_role.venue_type == role.venue_type
    assert fetched_role.audience_stance == role.audience_stance
    assert fetched_role.is_adversarial == role.is_adversarial

    utt = utterances[0]
    store.insert_utterance(utt)
    fetched_utt = store.get_utterance(utt.utterance_id)
    assert fetched_utt is not None
    assert fetched_utt.text_verbatim == utt.text_verbatim
    assert fetched_utt.start_ms == utt.start_ms

    claim = claims[0]
    store.insert_claim(claim)
    fetched_claim = store.get_claim(claim.claim_id)
    assert fetched_claim is not None
    assert fetched_claim.stance == claim.stance
    assert fetched_claim.quote_span == claim.quote_span
    assert fetched_claim.extraction_version == claim.extraction_version


def test_idempotent_duplicate_writes_produce_one_row(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    sources, utterances, claims, _, _, roles = load_valid_fixtures()

    # Insert same source twice
    store.insert_source(sources[0])
    store.insert_source(sources[0])
    cnt_sources = store.con.execute("SELECT count(*) FROM sources WHERE source_id = ?", [sources[0].source_id]).fetchone()
    assert cnt_sources is not None and cnt_sources[0] == 1

    # Insert subject and insert same role twice
    store.insert_subject(Subject(subject_id=roles[0].subject_id, display_name="Role Subject"))
    store.insert_source_role(roles[0])
    store.insert_source_role(roles[0])
    cnt_role = store.con.execute("SELECT count(*) FROM source_roles WHERE role_id = ?", [roles[0].role_id]).fetchone()
    assert cnt_role is not None and cnt_role[0] == 1

    # Insert same utterance twice
    store.insert_utterance(utterances[0])
    store.insert_utterance(utterances[0])
    cnt_utt = store.con.execute("SELECT count(*) FROM utterances WHERE utterance_id = ?", [utterances[0].utterance_id]).fetchone()
    assert cnt_utt is not None and cnt_utt[0] == 1

    # Insert same claim twice
    store.insert_claim(claims[0])
    store.insert_claim(claims[0])
    cnt_claim = store.con.execute("SELECT count(*) FROM claims WHERE claim_id = ?", [claims[0].claim_id]).fetchone()
    assert cnt_claim is not None and cnt_claim[0] == 1


def test_vss_embeddings_hnsw_cosine_search(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Create 3 normalized 768-dim vectors
    # v1 is aligned with query
    v1 = [1.0] + [0.0] * 767
    # v2 is partially aligned
    v2 = [0.7071, 0.7071] + [0.0] * 766
    # v3 is orthogonal
    v3 = [0.0, 1.0] + [0.0] * 766

    prop1 = Proposition(proposition_id="prop_1", canonical_text="Topic 1")
    prop2 = Proposition(proposition_id="prop_2", canonical_text="Topic 2")
    prop3 = Proposition(proposition_id="prop_3", canonical_text="Topic 3")

    store.insert_proposition(prop1)
    store.insert_proposition(prop2)
    store.insert_proposition(prop3)

    store.insert_proposition_embedding("prop_1", v1)
    store.insert_proposition_embedding("prop_2", v2)
    store.insert_proposition_embedding("prop_3", v3)

    query_v = [1.0] + [0.0] * 767
    results = store.query_nearest_propositions(query_v, limit=3)
    assert len(results) == 3
    # Order must be prop_1 (sim ~1.0), prop_2 (sim ~0.707), prop_3 (sim ~0.0)
    assert results[0][0] == "prop_1"
    assert results[0][1] > 0.99
    assert results[1][0] == "prop_2"
    assert results[2][0] == "prop_3"


def test_vector_dimension_strict_768_enforcement(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    # 512-dim vector should fail
    with pytest.raises(ValueError, match="Vector width must be exactly 768"):
        store.insert_proposition_embedding("prop_bad", [0.1] * 512)

    # 1024-dim vector should fail
    with pytest.raises(ValueError, match="Vector width must be exactly 768"):
        store.insert_proposition_embedding("prop_bad", [0.1] * 1024)


def test_three_hour_episode_word_timestamps_parquet_in_artifact_store(tmp_path: Path) -> None:
    """Build a 3-hour episode's word timestamps (~30,000 words);

    assert the Parquet lands on disk and the utterance row holds only a hash.
    """
    artifacts = ArtifactStore(base_dir=tmp_path / "artifacts")
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Generate 30,000 words (~3 hours of audio)
    words = []
    current_ms = 0
    for i in range(30000):
        words.append({
            "word": f"word_{i}",
            "start_ms": current_ms,
            "end_ms": current_ms + 300,
            "confidence": 0.95,
        })
        current_ms += 360  # ~3 hours total = ~10,800,000 ms

    parquet_hash = artifacts.put_word_timestamps(words)
    assert len(parquet_hash) == 64
    parquet_file = tmp_path / "artifacts" / f"words_{parquet_hash}.parquet"
    assert parquet_file.exists()
    assert parquet_file.stat().st_size > 0

    # Retrieve and verify round trip
    recovered_words = artifacts.get_word_timestamps(parquet_hash)
    assert recovered_words is not None
    assert len(recovered_words) == 30000
    assert recovered_words[0]["word"] == "word_0"
    assert recovered_words[29999]["word"] == "word_29999"

    # Utterance holds ONLY the hash ref
    utt = Utterance(
        utterance_id="utt_long_01",
        source_id="src_long_01",
        subject_id="subj_01",
        text_verbatim="Summary text for long episode...",
        start_ms=0,
        end_ms=current_ms,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
        word_timestamps_ref=parquet_hash,
    )
    store.insert_utterance(utt)
    fetched_utt = store.get_utterance("utt_long_01")
    assert fetched_utt is not None
    assert fetched_utt.word_timestamps_ref == parquet_hash


def test_core_reversal_detector_self_join(tmp_path: Path) -> None:
    """Tests the exact core reversal detector query from design_data_layer.md §4."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    sources, utterances, claims, _, _, _ = load_valid_fixtures()

    for s in sources:
        store.insert_source(s)
    for u in utterances:
        store.insert_utterance(u)
    for c in claims:
        store.insert_claim(c)

    reversals = store.detect_unacknowledged_reversals("subj_valid_01")
    assert len(reversals) == 1
    c1_id, c2_id, prop_id = reversals[0]
    assert c1_id == "clm_valid_01"
    assert c2_id == "clm_valid_02"
    assert prop_id == "prop_licensing_01"


def test_multi_subject_source_different_tiers_round_trip(tmp_path: Path) -> None:
    """Persist one source with two subjects at different tiers — Tier B for one, Tier C for the other —

    and assert both round-trip intact, neither overwriting the other. (c)
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Create 2 subjects
    host = Subject(subject_id="subj_host", display_name="Host")
    guest = Subject(subject_id="subj_guest", display_name="Guest")
    store.insert_subject(host)
    store.insert_subject(guest)

    # Create 1 source (e.g. podcast episode)
    source = Source(
        source_id="src_ep_200",
        title="Episode 200 with Guest",
        publisher="The Show",
        canonical_url="https://youtube.com/watch?v=ep200",
        artifact_hash="hash_ep200",
    )
    store.insert_source(source)

    # Role 1: Host has Tier B / own_channel / friendly
    role_host = SourceSubjectRole(
        role_id=compute_role_id(source.source_id, host.subject_id),
        source_id=source.source_id,
        subject_id=host.subject_id,
        tier="B",
        venue_type="own_channel",
        audience_stance="friendly",
        is_adversarial=False,
    )

    # Role 2: Guest has Tier C / guest / neutral
    role_guest = SourceSubjectRole(
        role_id=compute_role_id(source.source_id, guest.subject_id),
        source_id=source.source_id,
        subject_id=guest.subject_id,
        tier="C",
        venue_type="guest",
        audience_stance="neutral",
        is_adversarial=False,
    )

    store.insert_source_role(role_host)
    store.insert_source_role(role_guest)

    # Assert both round-trip intact, neither overwriting the other
    fetched_host_role = store.get_source_role(source.source_id, host.subject_id)
    fetched_guest_role = store.get_source_role(source.source_id, guest.subject_id)

    assert fetched_host_role is not None
    assert fetched_guest_role is not None

    assert fetched_host_role.tier == "B"
    assert fetched_host_role.venue_type == "own_channel"
    assert fetched_host_role.audience_stance == "friendly"

    assert fetched_guest_role.tier == "C"
    assert fetched_guest_role.venue_type == "guest"
    assert fetched_guest_role.audience_stance == "neutral"

    all_roles = store.get_source_roles_for_source(source.source_id)
    assert len(all_roles) == 2
    tiers = {r.tier for r in all_roles}
    assert tiers == {"B", "C"}


def test_falsification_non_deterministic_uuid_breaks_idempotency(tmp_path: Path) -> None:
    """Falsification test: Replacing deterministic ID with random UUID breaks duplicate test."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Non-deterministic source insertion
    def insert_random_source(canonical_url: str) -> None:
        random_id = str(uuid.uuid4())[:16]
        src = Source(
            source_id=random_id,
            title="Video",
            publisher="Pub",
            canonical_url=canonical_url,
            artifact_hash="hash",
        )
        store.insert_source(src)

    # Ingesting same canonical content twice with UUID produces 2 rows
    insert_random_source("https://youtube.com/watch?v=same_url")
    insert_random_source("https://youtube.com/watch?v=same_url")
    cnt = store.con.execute("SELECT count(*) FROM sources WHERE canonical_url = 'https://youtube.com/watch?v=same_url'").fetchone()
    assert cnt is not None and cnt[0] == 2  # Falsification confirmed: duplicate rows created!


def test_normalize_canonical_text() -> None:
    """Canonical form for content-derived IDs strips terminal punctuation and whitespace only."""
    # Terminal punctuation stripped
    assert normalize_canonical_text("China is optimistic about AI.") == "china is optimistic about ai"
    assert normalize_canonical_text("China is optimistic about AI!") == "china is optimistic about ai"
    assert normalize_canonical_text("China is optimistic about AI?") == "china is optimistic about ai"
    assert normalize_canonical_text("China is optimistic about AI…") == "china is optimistic about ai"
    assert normalize_canonical_text('China is optimistic about AI"') == "china is optimistic about ai"
    assert normalize_canonical_text("China is optimistic about AI'") == "china is optimistic about ai"
    assert normalize_canonical_text("China is optimistic about AI.”") == "china is optimistic about ai"

    # Whitespace collapsed and lowercased
    assert normalize_canonical_text("  China   has   optimism.  ") == "china has optimism"

    # Idempotent
    t = "String theory remains unproved until verified empirically."
    assert normalize_canonical_text(normalize_canonical_text(t)) == normalize_canonical_text(t)

    # Identical IDs computed with or without trailing period
    id1 = compute_proposition_id("China has greater societal optimism.")
    id2 = compute_proposition_id("China has greater societal optimism")
    assert id1 == id2


def test_migration_guard_fires_when_live_claim_proposition_moves(tmp_path: Path) -> None:
    """Guard in step 2.2 (§17e): If any proposition whose new_id != proposition_id

    has >= 1 live claim, migration refuses to cascade and raises loudly.
    """
    import hashlib

    db_path = tmp_path / "guard_test.duckdb"
    store = Storage(db_path=str(db_path), artifact_dir=tmp_path / "artifacts")

    # Construct proposition whose stored_id differs from compute_proposition_id
    raw_text = "Federal licensing prevents catastrophic rogue deployments."
    # Legacy un-stripped hash
    legacy_id = hashlib.sha256(raw_text.strip().lower().encode("utf-8")).hexdigest()[:16]
    normalized_id = compute_proposition_id(raw_text)
    assert legacy_id != normalized_id

    # Insert proposition with legacy ID
    store.con.execute(
        "INSERT INTO propositions VALUES (?, ?, NULL, ?, 1, 'active', NULL)",
        [legacy_id, raw_text, ["subj_01"]],
    )

    # Insert a source, utterance, and LIVE claim pointing to this legacy ID
    source = Source(
        source_id="src_g01",
        title="Podcast",
        publisher="Host",
        artifact_hash="hash_g01",
        canonical_url="https://example.com/g01",
    )
    store.insert_source(source)
    utt = Utterance(
        utterance_id="utt_g01",
        source_id="src_g01",
        subject_id="subj_01",
        text_verbatim=raw_text,
        start_ms=0,
        end_ms=1000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="manual",
    )
    store.insert_utterance(utt)
    claim = Claim(
        claim_id="clm_g01",
        subject_id="subj_01",
        utterance_id="utt_g01",
        proposition_id=legacy_id,
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
    )
    store.insert_claim(claim)

    # Assert migration refuses to proceed and raises RuntimeError
    with pytest.raises(RuntimeError, match="Refusing to cascade migration"):
        store.migrate_propositions()


def test_migration_idempotence_and_zero_changes(tmp_path: Path) -> None:
    """Idempotence (§17e): Running migration twice reports zero changes on second run,

    and database file hash is unchanged.
    """
    import hashlib

    class MockEmbedder:
        def embed_document(self, text: str) -> list[float]:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            return [float(b) / 255.0 for b in (h * 24)[:768]]

    db_path = tmp_path / "idempotent_test.duckdb"
    store = Storage(db_path=str(db_path), artifact_dir=tmp_path / "artifacts")
    embedder = MockEmbedder()

    # Insert live proposition with 1 claim
    p_live_id = compute_proposition_id("Autonomous AI agents operate effectively")
    store.insert_proposition(
        Proposition(
            proposition_id=p_live_id,
            canonical_text="Autonomous AI agents operate effectively",
            subject_ids=["subj_01"],
            claim_count=0,  # drifted count
        )
    )
    source = Source(
        source_id="src_i01",
        title="Test",
        publisher="Test",
        artifact_hash="hash_i01",
        canonical_url="https://example.com/i01",
    )
    store.insert_source(source)
    utt = Utterance(
        utterance_id="utt_i01",
        source_id="src_i01",
        subject_id="subj_01",
        text_verbatim="Autonomous AI agents operate effectively",
        start_ms=0,
        end_ms=1000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="manual",
    )
    store.insert_utterance(utt)
    store.insert_claim(
        Claim(
            claim_id="clm_i01",
            subject_id="subj_01",
            utterance_id="utt_i01",
            proposition_id=p_live_id,
            stance="support",
            hedging_level=0.1,
            is_own_assertion=True,
        )
    )

    # Insert fabricated proposition
    store.insert_proposition(
        Proposition(
            proposition_id="db3ec63d33cf6f0a",
            canonical_text="Mandatory state and federal licensing regimes for frontier artificial intelligence models",
            claim_count=1,
            status="active",
        )
    )

    # Run migration 1
    report1 = store.migrate_propositions(embedder=embedder)
    assert report1["claim_counts_updated"] >= 1
    assert report1["embedded_count"] == 1
    assert report1["status_updated"] >= 1

    # Take hash after first run
    store.con.execute("CHECKPOINT")
    hash1 = hashlib.sha256(open(db_path, "rb").read()).hexdigest()

    # Run migration 2
    report2 = store.migrate_propositions(embedder=embedder)
    assert report2["merged_count"] == 0
    assert report2["updated_count"] == 0
    assert report2["claim_counts_updated"] == 0
    assert report2["status_updated"] == 0
    assert report2["embedded_count"] == 0

    store.con.execute("CHECKPOINT")
    hash2 = hashlib.sha256(open(db_path, "rb").read()).hexdigest()

    assert hash1 == hash2, "DB hash changed on idempotent second run!"

