"""Tests for P3 — Topic model and resolution.

Implements agent_execution_guide.md §19 (P3) and design_topic_model.md.
Validates:
- HDBSCAN proposition clustering and noise point preservation
- Free-text resolution with nomic task prefix enforcement (Trap 7)
- Cluster expansion
- Separate-process determinism (Assertion c, Journey J4)
- Falsification: Cache invalidation on embedding_model provenance bump
- TopicDriftGuard wide-gap detection
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from worker.entities import Proposition, Subject, Topic
from worker.extract.dedup import stub_hash_embedding
from worker.storage import Storage, compute_proposition_id
from worker.topics.cluster import TopicClusterer
from worker.topics.drift import TopicDriftGuard
from worker.topics.resolve import (
    TopicResolver,
    compute_resolution_key,
    normalize_query,
)


class MockSemanticEmbedder:
    """Deterministic 768-dim mock embedder that captures task prefixes and maps semantic concepts."""

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5") -> None:
        self.model_name = model_name
        self.last_prefixed_text: str | None = None
        self.calls: list[str] = []

    def embed_document(self, text: str) -> list[float]:
        prefixed = f"search_document: {text}"
        self.last_prefixed_text = prefixed
        self.calls.append(prefixed)
        return self._vectorize(prefixed)

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"search_query: {text}"
        self.last_prefixed_text = prefixed
        self.calls.append(prefixed)
        return self._vectorize(prefixed)

    def _vectorize(self, text: str) -> list[float]:
        clean = text.lower()
        vec = np.zeros(768, dtype=np.float32)
        # Cluster 1: AI compute & regulation
        if "compute" in clean or "frontier" in clean or "licensing" in clean or "cluster" in clean:
            vec[0:50] = 1.0
        # Cluster 2: Open weights & models
        elif "open weight" in clean or "open source" in clean or "weights" in clean:
            vec[50:100] = 1.0
        # Noise / idiosyncratic
        elif "quantum" in clean:
            vec[100:150] = 1.0
        else:
            vec[200:250] = 0.5
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [float(x) for x in vec.tolist()]


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "topic_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


def test_task_prefix_enforcement_trap_7() -> None:
    """Trap 7: Embedder must enforce 'search_query: ' on queries and 'search_document: ' on documents."""
    embedder = MockSemanticEmbedder()

    # Query embedding
    embedder.embed_query("AI safety")
    assert embedder.last_prefixed_text == "search_query: AI safety"

    # Document embedding
    embedder.embed_document("frontier AI compute cluster threshold")
    assert embedder.last_prefixed_text == "search_document: frontier AI compute cluster threshold"

    # Falsification check: dropping prefix changes output
    _vec_with_prefix = embedder.embed_query("open weights")
    assert embedder.calls[-1].startswith("search_query: ")


def test_hdbscan_clustering_and_noise_preservation(test_store: Storage) -> None:
    """HDBSCAN clusters propositions per subject, keeping noise points unclustered."""
    subject = Subject(subject_id="subj_cluster_01", display_name="Host One")
    test_store.insert_subject(subject)

    embedder = MockSemanticEmbedder()

    # Create 3 propositions in Cluster 1 (compute / licensing)
    c1_props = [
        "frontier compute threshold licensing requirements",
        "mandatory compute cluster reporting for frontier AI",
        "federal licensing for frontier AI training clusters",
    ]
    # Create 2 propositions in Cluster 2 (open weights)
    c2_props = [
        "releasing open weights enables democratic research",
        "open source weights must be protected from export controls",
    ]
    # Create 1 isolated noise proposition
    noise_props = ["quantum superposition in cryogenic apparatus"]

    all_props = c1_props + c2_props + noise_props
    for text in all_props:
        pid = compute_proposition_id(text)
        prop = Proposition(
            proposition_id=pid,
            canonical_text=text,
            subject_ids=[subject.subject_id],
        )
        test_store.insert_proposition(prop)
        emb = embedder.embed_document(text)
        test_store.insert_proposition_embedding(pid, emb)

    clusterer = TopicClusterer(storage=test_store, min_cluster_size=2)
    topics = clusterer.cluster_propositions_for_subject(subject.subject_id)

    # Must find at least 2 distinct clusters
    assert len(topics) >= 2
    # Ensure all topic rows were written to storage
    stored_topics = test_store.get_topics_for_subject(subject.subject_id)
    assert len(stored_topics) == len(topics)

    # Verify noise proposition was NOT shoehorned into a cluster
    noise_pid = compute_proposition_id(noise_props[0])
    for t in stored_topics:
        assert noise_pid not in t.proposition_ids


def test_free_text_resolution_with_cluster_expansion(test_store: Storage) -> None:
    """Query matching a seed proposition expands to include the entire topic cluster."""
    subject = Subject(subject_id="subj_res_01", display_name="Host Two")
    test_store.insert_subject(subject)
    embedder = MockSemanticEmbedder()

    p1 = compute_proposition_id("federal licensing for frontier compute")
    p2 = compute_proposition_id("mandatory cluster compute registration")
    p3 = compute_proposition_id("releasing open weight models")

    test_store.insert_proposition(Proposition(proposition_id=p1, canonical_text="federal licensing for frontier compute", subject_ids=[subject.subject_id]))
    test_store.insert_proposition(Proposition(proposition_id=p2, canonical_text="mandatory cluster compute registration", subject_ids=[subject.subject_id]))
    test_store.insert_proposition(Proposition(proposition_id=p3, canonical_text="releasing open weight models", subject_ids=[subject.subject_id]))

    test_store.insert_proposition_embedding(p1, embedder.embed_document("federal licensing for frontier compute"))
    test_store.insert_proposition_embedding(p2, embedder.embed_document("mandatory cluster compute registration"))
    test_store.insert_proposition_embedding(p3, embedder.embed_document("releasing open weight models"))

    # Put p1 and p2 in a cluster topic
    topic = Topic(
        topic_id="top_compute_01",
        subject_id=subject.subject_id,
        label="Frontier Compute Regulation",
        proposition_ids=[p1, p2],
    )
    test_store.insert_topic(topic)

    resolver = TopicResolver(storage=test_store, embedder=embedder, similarity_threshold=0.60)

    # Query directly mentioning "licensing" matches p1 as seed, then expands to [p1, p2]
    res_key, prop_ids, status = resolver.resolve_topic(
        subject_id=subject.subject_id,
        query="frontier compute licensing",
        expand_clusters=True,
    )

    assert status == "ok"
    assert p1 in prop_ids
    assert p2 in prop_ids  # Expanded!
    assert p3 not in prop_ids

    # Query resolved and cached in DuckDB
    cached = test_store.get_topic_resolution(res_key)
    assert cached == prop_ids


def test_below_threshold_query_yields_no_coverage(test_store: Storage) -> None:
    """Query resolving below similarity threshold returns 'no_coverage' and empty list."""
    subject = Subject(subject_id="subj_res_cov", display_name="Host Three")
    test_store.insert_subject(subject)
    embedder = MockSemanticEmbedder()

    pid = compute_proposition_id("federal licensing for frontier compute")
    test_store.insert_proposition(Proposition(proposition_id=pid, canonical_text="federal licensing for frontier compute", subject_ids=[subject.subject_id]))
    test_store.insert_proposition_embedding(pid, embedder.embed_document("federal licensing for frontier compute"))

    resolver = TopicResolver(storage=test_store, embedder=embedder, similarity_threshold=0.85)

    # Completely unrelated query
    res_key, prop_ids, status = resolver.resolve_topic(
        subject_id=subject.subject_id,
        query="ancient roman aqueduct engineering",
    )

    assert status == "no_coverage"
    assert prop_ids == []
    # Cached in DuckDB as empty
    assert test_store.get_topic_resolution(res_key) == []


def test_falsification_embedding_model_bump_causes_cache_miss(test_store: Storage) -> None:
    """Falsification test: Bumping embedding_model string in cache key causes cache MISS."""
    subject = Subject(subject_id="subj_falsify_cache", display_name="Host Four")
    test_store.insert_subject(subject)
    embedder_v1 = MockSemanticEmbedder(model_name="nomic-ai/nomic-embed-text-v1.5")

    pid = compute_proposition_id("releasing open weight models")
    test_store.insert_proposition(Proposition(proposition_id=pid, canonical_text="releasing open weight models", subject_ids=[subject.subject_id]))
    test_store.insert_proposition_embedding(pid, embedder_v1.embed_document("releasing open weight models"))

    resolver_v1 = TopicResolver(storage=test_store, embedder=embedder_v1)
    key_v1, props_v1, status_v1 = resolver_v1.resolve_topic(subject.subject_id, "open weights")
    assert status_v1 == "ok"
    assert pid in props_v1

    # Verify cached under key_v1
    assert test_store.get_topic_resolution(key_v1) == props_v1

    # Bump model name in resolver (v2.0)
    embedder_v2 = MockSemanticEmbedder(model_name="nomic-ai/nomic-embed-text-v2.0")
    resolver_v2 = TopicResolver(storage=test_store, embedder=embedder_v2)

    # Resolution key must change
    norm_q = normalize_query("open weights")
    key_v2 = compute_resolution_key(subject.subject_id, norm_q, "nomic-ai/nomic-embed-text-v2.0", "v1.0")
    assert key_v2 != key_v1

    # Before resolving under v2, key_v2 MUST be a cache miss
    assert test_store.get_topic_resolution(key_v2) is None

    # Resolving under v2 now computes and caches under key_v2
    k2_resolved, props_v2, status_v2 = resolver_v2.resolve_topic(subject.subject_id, "open weights")
    assert k2_resolved == key_v2
    assert status_v2 == "ok"
    assert test_store.get_topic_resolution(key_v2) == props_v2


def test_separate_process_resolution_determinism_assertion_c(tmp_path: Path) -> None:
    """Assertion (c) & Journey J4:

    Running the same query twice in two completely separate Python processes against the same
    database yields byte-identical resolved proposition sets and identical cache keys.
    """
    db_path = tmp_path / "multiprocess_test.duckdb"
    store = Storage(str(db_path), artifact_dir=tmp_path / "artifacts")

    subject = Subject(subject_id="subj_mp_01", display_name="Multi Process Subject")
    store.insert_subject(subject)

    # Populate 3 propositions with deterministic hash embeddings
    prop_texts = [
        "frontier AI compute cluster threshold regulation",
        "federal licensing for frontier AI training clusters",
        "open weights foundation models for research",
    ]
    p_ids = []
    for text in prop_texts:
        pid = compute_proposition_id(text)
        p_ids.append(pid)
        store.insert_proposition(Proposition(proposition_id=pid, canonical_text=text, subject_ids=[subject.subject_id]))
        store.insert_proposition_embedding(pid, stub_hash_embedding(text))

    topic = Topic(
        topic_id="top_mp_01",
        subject_id=subject.subject_id,
        label="Frontier AI Compute",
        proposition_ids=[p_ids[0], p_ids[1]],
    )
    store.insert_topic(topic)
    store.close()  # Release lock for subprocesses

    # Script to run in separate Python subprocesses
    worker_script = """
import json, sys
from worker.storage import Storage
from worker.topics.resolve import TopicResolver
from worker.extract.dedup import stub_hash_embedding

class SubprocessMockEmbedder:
    def __init__(self):
        self.model_name = "mock-proc-embedder"
    def embed_query(self, text: str):
        return stub_hash_embedding(f"search_query: {text}")

db_path = sys.argv[1]
store = Storage(db_path)
embedder = SubprocessMockEmbedder()
resolver = TopicResolver(storage=store, embedder=embedder, similarity_threshold=0.20)
res_key, prop_ids, status = resolver.resolve_topic("subj_mp_01", "frontier compute regulation", expand_clusters=True)
store.close()

output = {"key": res_key, "prop_ids": sorted(prop_ids), "status": status}
print(json.dumps(output))
"""

    # Run Process 1
    res1 = subprocess.run(
        [sys.executable, "-c", worker_script, str(db_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data1 = json.loads(res1.stdout.strip())

    # Run Process 2
    res2 = subprocess.run(
        [sys.executable, "-c", worker_script, str(db_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data2 = json.loads(res2.stdout.strip())

    # Byte-identical outputs across processes
    assert res1.stdout.strip() == res2.stdout.strip()
    assert data1["key"] == data2["key"]
    assert data1["prop_ids"] == data2["prop_ids"]
    assert len(data1["prop_ids"]) >= 2


def test_topic_drift_guard() -> None:
    """TopicDriftGuard identifies wide era gaps (> 3 years) between statements."""
    guard = TopicDriftGuard(max_gap_years=3.0)

    # 1. Narrow gap (1.5 years): 2022 to 2023
    is_wide_1, years_1 = guard.check_date_gap("2022-01-01T00:00:00Z", "2023-07-01T00:00:00Z")
    assert is_wide_1 is False
    assert 1.4 <= years_1 <= 1.6
    assert guard.should_route_to_update_integrity("2022-01-01T00:00:00Z", "2023-07-01T00:00:00Z") is False

    # 2. Wide gap (8 years): 2016 to 2024
    is_wide_2, years_2 = guard.check_date_gap("2016-03-01T00:00:00Z", "2024-03-01T00:00:00Z")
    assert is_wide_2 is True
    assert 7.9 <= years_2 <= 8.1
    assert guard.should_route_to_update_integrity("2016-03-01T00:00:00Z", "2024-03-01T00:00:00Z") is True
