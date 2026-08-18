"""Proposition canonicalisation, embedding generation, and semantic deduplication.

Implements Parameter 002 (T_dedup) and design_claim_extraction.md §1 & §4.

WARNING / STUB NOTICE:
`stub_hash_embedding` is a bag-of-words hash vectoriser stub for 768-dim embeddings.
It has NO semantic capability: 'licensing' and 'permitting' hash to unrelated slots and
score ~0 similarity. Dedup merges only near-identical strings until real semantic model
(nomic-embed-text-v1.5) lands in V2. T_dedup = 0.88 is provisional and carries no semantic
information until V2.
"""

import hashlib
from typing import NamedTuple

import numpy as np

from worker.entities import Proposition
from worker.storage import Storage, compute_proposition_id


class DedupDecision(NamedTuple):
    proposition_id: str
    is_new: bool
    similarity: float
    canonical_text: str


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

    Parameter 002: T_dedup (default 0.88).
    """

    def __init__(self, storage: Storage, t_dedup: float = 0.88) -> None:
        self.storage = storage
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
        canonical_text = raw_proposition_text.strip().lower()
        emb = embedding if embedding is not None else stub_hash_embedding(canonical_text)

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
        prop = Proposition(
            proposition_id=prop_id,
            canonical_text=canonical_text,
            subject_ids=[subject_id],
            claim_count=1,
        )
        self.storage.insert_proposition(prop)
        self.storage.insert_proposition_embedding(prop_id, emb)

        return DedupDecision(
            proposition_id=prop_id,
            is_new=True,
            similarity=1.0,
            canonical_text=canonical_text,
        )
