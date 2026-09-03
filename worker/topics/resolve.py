"""Free-text topic resolution and caching module.

Implements design_topic_model.md §3 and agent_execution_guide.md §19.
Enforces task prefix 'search_query:' (Trap 7), k-NN seed search, cluster expansion,
and deterministic resolution_key caching with embedding_model and cluster_version provenance.
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

import numpy as np

from worker.extract.dedup import Embedder
from worker.storage import Storage


def normalize_query(query: str) -> str:
    """Normalizes query text: casefold, strip punctuation, collapse whitespace."""
    clean = re.sub(r"[^\w\s]", " ", query.lower())
    return " ".join(clean.split())


def compute_resolution_key(
    subject_id: str,
    normalized_query: str,
    embedding_model: str,
    cluster_version: str,
) -> str:
    """Computes deterministic resolution cache key per design_topic_model.md §3.

    resolution_key = sha256(subject_id | normalized_query | embedding_model | cluster_version)
    """
    key_str = f"{subject_id}|{normalized_query}|{embedding_model}|{cluster_version}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]


class TopicResolver:
    """Resolves free-text topic queries to subject proposition slices with cluster expansion and caching."""

    def __init__(
        self,
        storage: Storage,
        embedder: Any | None = None,
        cluster_version: str = "v1.0",
        similarity_threshold: float = 0.65,
    ) -> None:
        self.storage = storage
        self.cluster_version = cluster_version
        self.similarity_threshold = similarity_threshold
        self._embedder = embedder

    @property
    def embedder(self) -> Any:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    def resolve_topic(
        self,
        subject_id: str,
        query: str,
        similarity_threshold: float | None = None,
        expand_clusters: bool = True,
    ) -> tuple[str, list[str], str]:
        """Resolves free-text query against subject propositions.

        Returns (resolution_key, proposition_ids, status) where status is 'ok' or 'no_coverage'.
        """
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        norm_query = normalize_query(query)
        res_key = compute_resolution_key(
            subject_id=subject_id,
            normalized_query=norm_query,
            embedding_model=self.embedder.model_name,
            cluster_version=self.cluster_version,
        )

        # 1. Check DuckDB cache
        cached = self.storage.get_topic_resolution(res_key)
        if cached is not None:
            status = "ok" if len(cached) > 0 else "no_coverage"
            return res_key, cached, status

        # 2. Embed query using 'search_query: ' task prefix
        query_vec = np.array(self.embedder.embed_query(norm_query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        # 3. Load subject's proposition embeddings
        sql = """
            SELECT p.proposition_id, pe.embedding
            FROM propositions p
            JOIN proposition_embeddings pe ON p.proposition_id = pe.proposition_id
            WHERE list_contains(p.subject_ids, ?)
            ORDER BY p.proposition_id;
        """
        rows = self.storage.con.execute(sql, [subject_id]).fetchall()
        if not rows:
            now_iso = datetime.now(UTC).isoformat()
            self.storage.insert_topic_resolution(
                resolution_key=res_key,
                subject_id=subject_id,
                normalized_query=norm_query,
                embedding_model=self.embedder.model_name,
                cluster_version=self.cluster_version,
                proposition_ids=[],
                resolved_at=now_iso,
            )
            return res_key, [], "no_coverage"

        prop_ids = [r[0] for r in rows]
        embs = np.array([[float(x) for x in r[1]] for r in rows], dtype=np.float32)
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embs_norm = embs / norms

        # Cosine similarities
        sims = np.dot(embs_norm, query_vec)

        # Seed matches
        seed_indices = np.where(sims >= threshold)[0]
        if len(seed_indices) == 0:
            now_iso = datetime.now(UTC).isoformat()
            self.storage.insert_topic_resolution(
                resolution_key=res_key,
                subject_id=subject_id,
                normalized_query=norm_query,
                embedding_model=self.embedder.model_name,
                cluster_version=self.cluster_version,
                proposition_ids=[],
                resolved_at=now_iso,
            )
            return res_key, [], "no_coverage"

        resolved_ids_set = {prop_ids[idx] for idx in seed_indices}

        # 4. Cluster expansion: pull in full clusters where a seed proposition is a member
        if expand_clusters:
            topics = self.storage.get_topics_for_subject(subject_id)
            for t in topics:
                if any(seed in t.proposition_ids for seed in resolved_ids_set):
                    resolved_ids_set.update(t.proposition_ids)

        resolved_list = sorted(resolved_ids_set)
        now_iso = datetime.now(UTC).isoformat()
        self.storage.insert_topic_resolution(
            resolution_key=res_key,
            subject_id=subject_id,
            normalized_query=norm_query,
            embedding_model=self.embedder.model_name,
            cluster_version=self.cluster_version,
            proposition_ids=resolved_list,
            resolved_at=now_iso,
        )

        return res_key, resolved_list, "ok"
