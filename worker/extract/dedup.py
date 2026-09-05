"""Proposition canonicalisation, embedding generation, and semantic deduplication.

Implements Parameter 008 (T_dedup) and design_claim_extraction.md §1 & §4.

WARNING / STUB NOTICE:
`stub_hash_embedding` is a bag-of-words hash vectoriser stub for 768-dim embeddings.
It has NO semantic capability: 'licensing' and 'permitting' hash to unrelated slots and
score ~0 similarity. Dedup merges only near-identical strings until real semantic model
(nomic-embed-text-v1.5) lands in V2. T_dedup = 0.86 is empirical Parameter 008.
"""

import hashlib
from typing import Any, NamedTuple

import numpy as np
from sentence_transformers import SentenceTransformer

from worker.entities import Proposition
from worker.storage import Storage, compute_proposition_id, normalize_canonical_text


class DedupDecision(NamedTuple):
    proposition_id: str
    is_new: bool
    similarity: float
    canonical_text: str


class Embedder:
    """Production embedding model wrapper for nomic-embed-text-v1.5.

    Implements task prefix enforcement (Trap 7) and strict 768-dim output.
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        expected_dim: int = 768,
        model_instance: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.expected_dim = expected_dim
        if model_instance is not None:
            self.model = model_instance
        else:
            self.model = SentenceTransformer(model_name, trust_remote_code=True)

        dim_func = getattr(self.model, "get_embedding_dimension", None) or getattr(
            self.model, "get_sentence_embedding_dimension", None
        )
        actual_dim = dim_func() if dim_func else 768
        if actual_dim != expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}"
            )

    def embed_document(self, text: str) -> list[float]:
        """Embeds document/proposition with 'search_document: ' prefix."""
        return self._embed(f"search_document: {text}")

    def embed_query(self, text: str) -> list[float]:
        """Embeds search query with 'search_query: ' prefix."""
        return self._embed(f"search_query: {text}")

    def similarity(self, doc_text_a: str, doc_text_b: str) -> float:
        """Computes document-to-document similarity using search_document: prefix on both sides (Trap 7)."""
        vec_a = self.embed_document(doc_text_a)
        vec_b = self.embed_document(doc_text_b)
        return cosine_similarity(vec_a, vec_b)

    def _embed(self, prefixed_text: str) -> list[float]:
        vec = self.model.encode(prefixed_text, normalize_embeddings=True)
        return [float(x) for x in vec.tolist()]


NomicEmbedder = Embedder

_DEFAULT_EMBEDDER: Embedder | None = None


def get_embedder() -> Embedder:
    """Returns a module-level cached Embedder instance to avoid redundant model loads."""
    global _DEFAULT_EMBEDDER
    if _DEFAULT_EMBEDDER is None:
        _DEFAULT_EMBEDDER = Embedder()
    return _DEFAULT_EMBEDDER


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Computes cosine similarity between two vector representations."""
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def stub_hash_embedding(text: str, dim: int = 768) -> list[float]:
    """Generates a reproducible 768-dim hash vector for testing/offline mock embedding matching.

    WARNING: Has NO semantic capability. Do not use as a real embedding model.
    """
    words = text.lower().split()
    vec = np.zeros(dim, dtype=np.float32)

    for i, w in enumerate(words):
        h = int(hashlib.sha256(w.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        weight = 1.0 / (1.0 + 0.1 * i)
        vec[idx] += sign * weight

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec[0] = 1.0

    return [float(x) for x in vec.tolist()]


class PropositionCanonicalizer:
    """Canonicalises proposition text and deduplicates semantically against the DuckDB store.

    Parameter 008: T_dedup (default 0.86).
    """

    def __init__(
        self,
        storage: Storage,
        embedder: Embedder | None = None,
        t_dedup: float = 0.86,
    ) -> None:
        self.storage = storage
        self.embedder = embedder
        self.t_dedup = t_dedup

    def canonicalise_and_dedup(
        self,
        raw_proposition_text: str,
        subject_id: str,
        embedding: list[float] | None = None,
    ) -> DedupDecision:
        """Finds closest existing proposition by cosine similarity.

        If similarity >= t_dedup: merges into existing proposition.
        Otherwise: creates a new proposition.
        """
        canonical_text = normalize_canonical_text(raw_proposition_text)
        if embedding is not None:
            emb = embedding
        elif self.embedder is not None:
            emb = self.embedder.embed_document(canonical_text)
        else:
            emb = stub_hash_embedding(canonical_text)

        # Query nearest existing propositions
        nearest = self.storage.query_nearest_propositions(emb, limit=1)

        if nearest:
            best_id, sim = nearest[0]
            if sim >= self.t_dedup:
                # Merge into existing proposition
                existing = self.storage.get_proposition(best_id)
                if existing:
                    subject_ids = list(set(existing.subject_ids + [subject_id]))
                    updated = Proposition(
                        proposition_id=existing.proposition_id,
                        canonical_text=existing.canonical_text,
                        embedding_ref=existing.embedding_ref,
                        subject_ids=subject_ids,
                        claim_count=existing.claim_count + 1,
                        status=existing.status,
                        quarantine_reason=existing.quarantine_reason,
                    )
                    self.storage.insert_proposition(updated)
                    return DedupDecision(
                        proposition_id=best_id,
                        is_new=False,
                        similarity=sim,
                        canonical_text=existing.canonical_text,
                    )

        # Create new proposition
        prop_id = compute_proposition_id(canonical_text)
        existing = self.storage.get_proposition(prop_id)
        if existing:
            subject_ids = list(set(existing.subject_ids + [subject_id]))
            updated = Proposition(
                proposition_id=existing.proposition_id,
                canonical_text=existing.canonical_text,
                embedding_ref=existing.embedding_ref,
                subject_ids=subject_ids,
                claim_count=existing.claim_count + 1,
                status=existing.status,
                quarantine_reason=existing.quarantine_reason,
            )
            self.storage.insert_proposition(updated)
            return DedupDecision(
                proposition_id=prop_id,
                is_new=False,
                similarity=1.0,
                canonical_text=existing.canonical_text,
            )

        prop = Proposition(
            proposition_id=prop_id,
            canonical_text=canonical_text,
            subject_ids=[subject_id],
            claim_count=1,
            status="active",
            quarantine_reason=None,
        )
        self.storage.insert_proposition(prop)
        self.storage.insert_proposition_embedding(prop_id, emb)

        best_sim = nearest[0][1] if nearest else 0.0
        return DedupDecision(
            proposition_id=prop_id,
            is_new=True,
            similarity=best_sim,
            canonical_text=canonical_text,
        )
