"""Proposition clustering module using HDBSCAN over 768-dim embeddings.

Implements design_topic_model.md §2 and agent_execution_guide.md §19.
Clusters propositions per subject, preserves noise points, and assigns cosmetic topic labels.
"""

import hashlib
from collections import defaultdict

import numpy as np
from sklearn.cluster import HDBSCAN

from worker.entities import Topic
from worker.storage import Storage


class TopicClusterer:
    """Clusters propositions for a subject using HDBSCAN on proposition embeddings."""

    def __init__(
        self,
        storage: Storage,
        cluster_version: str = "v1.0",
        min_cluster_size: int = 2,
        max_cluster_size: int = 50,
    ) -> None:
        self.storage = storage
        self.cluster_version = cluster_version
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size

    def cluster_propositions_for_subject(self, subject_id: str) -> list[Topic]:
        """Clusters all embedded propositions associated with subject_id.

        Preserves noise points (-1) without discarding them.
        Writes discovered Topic clusters to storage.
        """
        # Query propositions and embeddings for this subject
        query = """
            SELECT p.proposition_id, p.canonical_text, pe.embedding
            FROM propositions p
            JOIN proposition_embeddings pe ON p.proposition_id = pe.proposition_id
            WHERE list_contains(p.subject_ids, ?)
            ORDER BY p.proposition_id;
        """
        rows = self.storage.con.execute(query, [subject_id]).fetchall()
        if len(rows) < self.min_cluster_size:
            return []

        prop_ids: list[str] = []
        texts: list[str] = []
        embeddings_list: list[list[float]] = []

        for r in rows:
            prop_ids.append(r[0])
            texts.append(r[1])
            raw_emb = r[2]
            embeddings_list.append([float(x) for x in raw_emb])

        x_matrix = np.array(embeddings_list, dtype=np.float32)
        # Normalize for cosine metric
        norms = np.linalg.norm(x_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        x_norm = x_matrix / norms

        clusterer = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            metric="cosine",
            copy=True,
        )
        raw_labels = clusterer.fit_predict(x_norm)
        probs = getattr(clusterer, "probabilities_", None)

        labels = np.array(raw_labels)
        if probs is not None:
            labels = np.where(probs < 0.1, -1, labels)

        # Group proposition IDs and texts by cluster label
        clusters: dict[int, list[str]] = defaultdict(list)
        cluster_texts: dict[int, list[str]] = defaultdict(list)
        noise_props: list[str] = []

        for idx, lbl in enumerate(labels):
            if lbl == -1:
                noise_props.append(prop_ids[idx])
            else:
                clusters[lbl].append(prop_ids[idx])
                cluster_texts[lbl].append(texts[idx])

        topics: list[Topic] = []
        for lbl, p_ids in clusters.items():
            if not p_ids:
                continue
            # Cap cluster size if needed
            capped_p_ids = p_ids[: self.max_cluster_size]

            # Cosmetic label: representative text from the shortest proposition canonical text
            sorted_texts = sorted(cluster_texts[lbl], key=len)
            label = sorted_texts[0] if sorted_texts else f"Topic {lbl}"

            # Deterministic topic_id
            hash_key = f"{subject_id}|{','.join(sorted(capped_p_ids))}|{self.cluster_version}"
            topic_id = hashlib.sha256(hash_key.encode("utf-8")).hexdigest()[:16]

            topic = Topic(
                topic_id=topic_id,
                subject_id=subject_id,
                label=label,
                proposition_ids=capped_p_ids,
                global_topic_id=None,
            )
            self.storage.insert_topic(topic)
            topics.append(topic)

        return topics
