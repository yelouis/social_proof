"""Data layer: DuckDB storage, schema, deterministic IDs, vector search, and artifact store.

Implements design_data_layer.md §1-§4 and agent_execution_guide.md §5 (U1).
"""

import hashlib
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from worker.entities import (
    Assessment,
    Claim,
    Principle,
    Proposition,
    Source,
    SourceSubjectRole,
    Subject,
    Tension,
    Topic,
    Utterance,
)


def compute_source_id(canonical_locator: str) -> str:
    return hashlib.sha256(canonical_locator.strip().encode("utf-8")).hexdigest()[:16]


def compute_utterance_id(source_id: str, start_ms: int, text_verbatim: str) -> str:
    key = f"{source_id}|{start_ms}|{text_verbatim.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def compute_proposition_id(canonical_text: str) -> str:
    normalized = " ".join(canonical_text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def compute_claim_id(
    utterance_id: str,
    proposition_id: str,
    stance: str,
    extraction_version: str,
) -> str:
    key = f"{utterance_id}|{proposition_id}|{stance}|{extraction_version}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def compute_principle_id(canonical_text: str) -> str:
    normalized = " ".join(canonical_text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def compute_tension_id(claim_a_id: str, claim_b_id: str, tension_type: str) -> str:
    first = min(claim_a_id, claim_b_id)
    second = max(claim_a_id, claim_b_id)
    key = f"{first}:{second}|{tension_type}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def compute_assessment_id(subject_id: str, topic_id: str, rubric_version: str) -> str:
    key = f"{subject_id}|{topic_id}|{rubric_version}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def compute_role_id(source_id: str, subject_id: str) -> str:
    """Computes deterministic role_id = sha256(source_id | subject_id)[:16]."""
    key = f"{source_id}|{subject_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


class ArtifactStore:
    """Content-addressed local disk artifact store for transcripts and Parquet word timestamps."""

    def __init__(self, base_dir: str | Path = "artifacts") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put_text(self, text: str, prefix: str = "txt") -> str:
        data = text.encode("utf-8")
        content_hash = hashlib.sha256(data).hexdigest()
        file_path = self.base_dir / f"{prefix}_{content_hash}.txt"
        if not file_path.exists():
            file_path.write_bytes(data)
        return content_hash

    def get_text(self, content_hash: str, prefix: str = "txt") -> str | None:
        file_path = self.base_dir / f"{prefix}_{content_hash}.txt"
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def put_word_timestamps(self, words: list[dict[str, Any]]) -> str:
        """Stores word timestamps as Parquet and returns the content hash."""
        # Schema: word (str), start_ms (int64), end_ms (int64), confidence (float64)
        word_list = [w["word"] for w in words]
        start_list = [int(w["start_ms"]) for w in words]
        end_list = [int(w["end_ms"]) for w in words]
        conf_list = [float(w.get("confidence", 1.0)) for w in words]

        table = pa.Table.from_arrays(
            [
                pa.array(word_list, type=pa.string()),
                pa.array(start_list, type=pa.int64()),
                pa.array(end_list, type=pa.int64()),
                pa.array(conf_list, type=pa.float64()),
            ],
            names=["word", "start_ms", "end_ms", "confidence"],
        )

        sink = pa.BufferOutputStream()
        pq.write_table(table, sink)
        buf = sink.getvalue().to_pybytes()

        content_hash = hashlib.sha256(buf).hexdigest()
        file_path = self.base_dir / f"words_{content_hash}.parquet"
        if not file_path.exists():
            file_path.write_bytes(buf)
        return content_hash

    def get_word_timestamps(self, content_hash: str) -> list[dict[str, Any]] | None:
        file_path = self.base_dir / f"words_{content_hash}.parquet"
        if not file_path.exists():
            return None
        table = pq.read_table(file_path)
        words = []
        for i in range(len(table)):
            words.append({
                "word": table["word"][i].as_py(),
                "start_ms": table["start_ms"][i].as_py(),
                "end_ms": table["end_ms"][i].as_py(),
                "confidence": table["confidence"][i].as_py(),
            })
        return words


class Storage:
    """DuckDB persistence engine and analytical mirror with VSS 768-dim embeddings."""

    def __init__(self, db_path: str = ":memory:", artifact_dir: str | Path = "artifacts") -> None:
        self.db_path = db_path
        self.con = duckdb.connect(db_path)
        self.artifacts = ArtifactStore(artifact_dir)
        self._init_schema()

    @property
    def artifact_store(self) -> ArtifactStore:
        return self.artifacts

    def close(self) -> None:
        self.con.close()

    def _init_schema(self) -> None:
        # Load VSS extension for vector search
        self.con.execute("INSTALL vss; LOAD vss;")
        self.con.execute("SET hnsw_enable_experimental_persistence = true;")

        self.con.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id VARCHAR PRIMARY KEY,
                display_name VARCHAR,
                aliases VARCHAR[],
                handles VARCHAR, -- JSON string
                enrollment_ref VARCHAR,
                corpus_stats VARCHAR, -- JSON string
                created_at VARCHAR,
                updated_at VARCHAR
            );

            CREATE TABLE IF NOT EXISTS sources (
                source_id VARCHAR PRIMARY KEY,
                title VARCHAR,
                publisher VARCHAR,
                canonical_url VARCHAR,
                artifact_hash VARCHAR,
                citation_url_template VARCHAR,
                interlocutor VARCHAR,
                recorded_at VARCHAR,
                published_at VARCHAR,
                authorship_confidence DOUBLE,
                ingest_job_id VARCHAR,
                transcription_model VARCHAR,
                ingested_at VARCHAR,
                audio_deleted_at VARCHAR
            );

            CREATE TABLE IF NOT EXISTS source_roles (
                role_id VARCHAR PRIMARY KEY,
                source_id VARCHAR,
                subject_id VARCHAR,
                tier VARCHAR,
                venue_type VARCHAR,
                audience_stance VARCHAR,
                is_adversarial BOOLEAN,
                FOREIGN KEY (source_id) REFERENCES sources(source_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            );
            CREATE INDEX IF NOT EXISTS idx_source_roles_pair ON source_roles(source_id, subject_id);

            CREATE TABLE IF NOT EXISTS utterances (
                utterance_id VARCHAR PRIMARY KEY,
                source_id VARCHAR,
                subject_id VARCHAR,
                text_verbatim VARCHAR,
                start_ms BIGINT,
                end_ms BIGINT,
                speaker_label VARCHAR,
                attribution_confidence VARCHAR,
                attribution_method VARCHAR,
                word_timestamps_ref VARCHAR,
                language VARCHAR,
                transcription_pass_count INTEGER,
                dual_pass_agreement BOOLEAN,
                negation_uncertain BOOLEAN
            );

            CREATE TABLE IF NOT EXISTS claims (
                claim_id VARCHAR PRIMARY KEY,
                subject_id VARCHAR,
                utterance_id VARCHAR,
                proposition_id VARCHAR,
                stance VARCHAR,
                hedging_level DOUBLE,
                is_own_assertion BOOLEAN,
                exclusion_reason VARCHAR,
                confidence DOUBLE,
                quote_span_start INTEGER,
                quote_span_end INTEGER,
                condition VARCHAR,
                prior_stance_reported VARCHAR,
                change_marker VARCHAR, -- JSON string
                extraction_model VARCHAR,
                prompt_version VARCHAR,
                extraction_version VARCHAR,
                recorded_at VARCHAR,
                quote_text VARCHAR
            );

            CREATE TABLE IF NOT EXISTS propositions (
                proposition_id VARCHAR PRIMARY KEY,
                canonical_text VARCHAR,
                embedding_ref VARCHAR,
                subject_ids VARCHAR[],
                claim_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS principles (
                principle_id VARCHAR PRIMARY KEY,
                canonical_text VARCHAR,
                actor_role VARCHAR,
                actor_slot_examples VARCHAR[],
                embedding_ref VARCHAR,
                subject_ids VARCHAR[]
            );

            CREATE TABLE IF NOT EXISTS topics (
                topic_id VARCHAR PRIMARY KEY,
                subject_id VARCHAR,
                label VARCHAR,
                proposition_ids VARCHAR[],
                global_topic_id VARCHAR
            );

            CREATE TABLE IF NOT EXISTS topic_resolutions (
                resolution_key VARCHAR PRIMARY KEY,
                subject_id VARCHAR,
                normalized_query VARCHAR,
                embedding_model VARCHAR,
                cluster_version VARCHAR,
                proposition_ids VARCHAR[],
                resolved_at VARCHAR
            );
            CREATE INDEX IF NOT EXISTS idx_topic_resolutions_lookup ON topic_resolutions(subject_id, normalized_query);

            CREATE TABLE IF NOT EXISTS tensions (
                tension_id VARCHAR PRIMARY KEY,
                type VARCHAR,
                claim_a_id VARCHAR,
                claim_b_id VARCHAR,
                proposition_id VARCHAR,
                principle_id VARCHAR,
                severity DOUBLE,
                detector_version VARCHAR,
                status VARCHAR,
                quarantine_reason VARCHAR
            );

            CREATE TABLE IF NOT EXISTS assessments (
                assessment_id VARCHAR PRIMARY KEY,
                subject_id VARCHAR,
                topic_id VARCHAR,
                rubric_version VARCHAR,
                extraction_model_set VARCHAR[],
                detector_version VARCHAR,
                embedding_model VARCHAR,
                nlp_version VARCHAR,
                sufficiency VARCHAR, -- JSON string
                axes VARCHAR, -- JSON string
                axis_evidence VARCHAR, -- JSON string
                computed_at VARCHAR
            );

            CREATE TABLE IF NOT EXISTS ingest_jobs (
                job_id VARCHAR PRIMARY KEY,
                subject_id VARCHAR,
                adapter VARCHAR,
                status VARCHAR,
                stage VARCHAR,
                counts VARCHAR, -- JSON string
                errors VARCHAR[],
                started_at VARCHAR,
                finished_at VARCHAR
            );

            -- 768-dim embeddings for nomic-embed-text-v1.5 (Issue 005 Option A)
            CREATE TABLE IF NOT EXISTS proposition_embeddings (
                proposition_id VARCHAR PRIMARY KEY,
                embedding FLOAT[768]
            );

            CREATE TABLE IF NOT EXISTS principle_embeddings (
                principle_id VARCHAR PRIMARY KEY,
                embedding FLOAT[768]
            );
        """)

        # Create HNSW index with cosine distance
        self.con.execute("""
            CREATE INDEX IF NOT EXISTS prop_hnsw ON proposition_embeddings
                USING HNSW (embedding) WITH (metric = 'cosine');
            CREATE INDEX IF NOT EXISTS princ_hnsw ON principle_embeddings
                USING HNSW (embedding) WITH (metric = 'cosine');
        """)

    def insert_subject(self, s: Subject) -> None:
        import json
        self.con.execute(
            """
            INSERT INTO subjects VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (subject_id) DO UPDATE SET
                display_name = excluded.display_name,
                aliases = excluded.aliases,
                handles = excluded.handles,
                enrollment_ref = excluded.enrollment_ref,
                corpus_stats = excluded.corpus_stats,
                updated_at = excluded.updated_at
            """,
            [
                s.subject_id,
                s.display_name,
                s.aliases,
                json.dumps(s.handles),
                s.enrollment_ref,
                json.dumps(s.corpus_stats),
                s.created_at,
                s.updated_at,
            ],
        )

    def get_subject(self, subject_id: str) -> Subject | None:
        import json
        res = self.con.execute("SELECT * FROM subjects WHERE subject_id = ?", [subject_id]).fetchone()
        if not res:
            return None
        return Subject(
            subject_id=res[0],
            display_name=res[1],
            aliases=res[2] or [],
            handles=json.loads(res[3]) if res[3] else {},
            enrollment_ref=res[4],
            corpus_stats=json.loads(res[5]) if res[5] else {},
            created_at=res[6],
            updated_at=res[7],
        )

    def insert_source(self, s: Source) -> None:
        self.con.execute(
            """
            INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_id) DO UPDATE SET
                title = excluded.title,
                publisher = excluded.publisher,
                citation_url_template = excluded.citation_url_template,
                audio_deleted_at = excluded.audio_deleted_at
            """,
            [
                s.source_id,
                s.title,
                s.publisher,
                s.canonical_url,
                s.artifact_hash,
                s.citation_url_template,
                s.interlocutor,
                s.recorded_at,
                s.published_at,
                s.authorship_confidence,
                s.ingest_job_id,
                s.transcription_model,
                s.ingested_at,
                s.audio_deleted_at,
            ],
        )

    def get_source(self, source_id: str) -> Source | None:
        res = self.con.execute("SELECT * FROM sources WHERE source_id = ?", [source_id]).fetchone()
        if not res:
            return None
        return Source(
            source_id=res[0],
            title=res[1],
            publisher=res[2],
            canonical_url=res[3],
            artifact_hash=res[4],
            citation_url_template=res[5],
            interlocutor=res[6],
            recorded_at=res[7],
            published_at=res[8],
            authorship_confidence=res[9],
            ingest_job_id=res[10],
            transcription_model=res[11],
            ingested_at=res[12],
            audio_deleted_at=res[13],
        )

    def insert_source_role(self, r: SourceSubjectRole) -> None:
        self.con.execute(
            """
            INSERT INTO source_roles VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (role_id) DO UPDATE SET
                tier = excluded.tier,
                venue_type = excluded.venue_type,
                audience_stance = excluded.audience_stance,
                is_adversarial = excluded.is_adversarial
            """,
            [
                r.role_id,
                r.source_id,
                r.subject_id,
                r.tier,
                r.venue_type,
                r.audience_stance,
                r.is_adversarial,
            ],
        )

    def get_source_role(self, source_id: str, subject_id: str) -> SourceSubjectRole | None:
        res = self.con.execute(
            "SELECT role_id, source_id, subject_id, tier, venue_type, audience_stance, is_adversarial FROM source_roles WHERE source_id = ? AND subject_id = ?",
            [source_id, subject_id],
        ).fetchone()
        if not res:
            return None
        return SourceSubjectRole(
            role_id=res[0],
            source_id=res[1],
            subject_id=res[2],
            tier=res[3],
            venue_type=res[4],
            audience_stance=res[5],
            is_adversarial=bool(res[6]),
        )

    def get_source_roles_for_source(self, source_id: str) -> list[SourceSubjectRole]:
        rows = self.con.execute(
            "SELECT role_id, source_id, subject_id, tier, venue_type, audience_stance, is_adversarial FROM source_roles WHERE source_id = ?",
            [source_id],
        ).fetchall()
        return [
            SourceSubjectRole(
                role_id=row[0],
                source_id=row[1],
                subject_id=row[2],
                tier=row[3],
                venue_type=row[4],
                audience_stance=row[5],
                is_adversarial=bool(row[6]),
            )
            for row in rows
        ]

    def insert_utterance(self, u: Utterance) -> None:
        self.con.execute(
            """
            INSERT INTO utterances VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (utterance_id) DO UPDATE SET
                subject_id = excluded.subject_id,
                speaker_label = excluded.speaker_label,
                attribution_confidence = excluded.attribution_confidence,
                attribution_method = excluded.attribution_method,
                text_verbatim = excluded.text_verbatim,
                word_timestamps_ref = excluded.word_timestamps_ref,
                dual_pass_agreement = excluded.dual_pass_agreement,
                negation_uncertain = excluded.negation_uncertain
            """,
            [
                u.utterance_id,
                u.source_id,
                u.subject_id,
                u.text_verbatim,
                u.start_ms,
                u.end_ms,
                u.speaker_label,
                str(u.attribution_confidence),
                u.attribution_method,
                u.word_timestamps_ref,
                u.language,
                u.transcription_pass_count,
                u.dual_pass_agreement,
                u.negation_uncertain,
            ],
        )

    def get_utterance(self, utterance_id: str) -> Utterance | None:
        res = self.con.execute("SELECT * FROM utterances WHERE utterance_id = ?", [utterance_id]).fetchone()
        if not res:
            return None
        return Utterance(
            utterance_id=res[0],
            source_id=res[1],
            subject_id=res[2],
            text_verbatim=res[3],
            start_ms=res[4],
            end_ms=res[5],
            speaker_label=res[6],
            attribution_confidence=res[7],
            attribution_method=res[8],
            word_timestamps_ref=res[9],
            language=res[10],
            transcription_pass_count=res[11],
            dual_pass_agreement=res[12],
            negation_uncertain=res[13],
        )

    def get_utterances_for_source(self, source_id: str) -> list[Utterance]:
        rows = self.con.execute(
            "SELECT utterance_id FROM utterances WHERE source_id = ? ORDER BY start_ms ASC",
            [source_id],
        ).fetchall()
        utts: list[Utterance] = []
        for r in rows:
            u = self.get_utterance(r[0])
            if u is not None:
                utts.append(u)
        return utts

    def insert_claim(self, c: Claim) -> None:
        import json
        self.con.execute(
            """
            INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (claim_id) DO UPDATE SET
                stance = excluded.stance,
                hedging_level = excluded.hedging_level,
                is_own_assertion = excluded.is_own_assertion,
                exclusion_reason = excluded.exclusion_reason,
                confidence = excluded.confidence,
                recorded_at = excluded.recorded_at,
                quote_text = excluded.quote_text
            """,
            [
                c.claim_id,
                c.subject_id,
                c.utterance_id,
                c.proposition_id,
                c.stance,
                c.hedging_level,
                c.is_own_assertion,
                c.exclusion_reason,
                c.confidence,
                c.quote_span[0],
                c.quote_span[1],
                c.condition,
                c.prior_stance_reported,
                json.dumps(c.change_marker) if c.change_marker else None,
                c.extraction_model,
                c.prompt_version,
                c.extraction_version,
                c.recorded_at,
                c.quote_text,
            ],
        )

    def get_claim(self, claim_id: str) -> Claim | None:
        import json
        res = self.con.execute("SELECT * FROM claims WHERE claim_id = ?", [claim_id]).fetchone()
        if not res:
            return None
        return Claim(
            claim_id=res[0],
            subject_id=res[1],
            utterance_id=res[2],
            proposition_id=res[3],
            stance=res[4],
            hedging_level=res[5],
            is_own_assertion=res[6],
            exclusion_reason=res[7],
            confidence=res[8],
            quote_span=(res[9], res[10]),
            condition=res[11],
            prior_stance_reported=res[12],
            change_marker=json.loads(res[13]) if res[13] else None,
            extraction_model=res[14],
            prompt_version=res[15],
            extraction_version=res[16],
            recorded_at=res[17],
            quote_text=res[18] if len(res) > 18 else None,
        )

    def insert_proposition(self, p: Proposition) -> None:
        self.con.execute(
            """
            INSERT INTO propositions VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (proposition_id) DO UPDATE SET
                canonical_text = excluded.canonical_text,
                embedding_ref = excluded.embedding_ref,
                subject_ids = excluded.subject_ids,
                claim_count = excluded.claim_count
            """,
            [
                p.proposition_id,
                p.canonical_text,
                p.embedding_ref,
                p.subject_ids,
                p.claim_count,
            ],
        )

    def get_proposition(self, proposition_id: str) -> Proposition | None:
        res = self.con.execute("SELECT * FROM propositions WHERE proposition_id = ?", [proposition_id]).fetchone()
        if not res:
            return None
        return Proposition(
            proposition_id=res[0],
            canonical_text=res[1],
            embedding_ref=res[2],
            subject_ids=list(res[3]) if res[3] else [],
            claim_count=res[4],
        )

    def insert_proposition_embedding(self, proposition_id: str, embedding: list[float]) -> None:
        if len(embedding) != 768:
            raise ValueError(f"Vector width must be exactly 768, got {len(embedding)}")
        self.con.execute(
            """
            INSERT INTO proposition_embeddings VALUES (?, ?::FLOAT[768])
            ON CONFLICT (proposition_id) DO UPDATE SET embedding = excluded.embedding
            """,
            [proposition_id, embedding],
        )

    def query_nearest_propositions(self, query_embedding: list[float], limit: int = 5) -> list[tuple[str, float]]:
        """Queries nearest propositions by cosine distance."""
        if len(query_embedding) != 768:
            raise ValueError(f"Query vector width must be exactly 768, got {len(query_embedding)}")
        res = self.con.execute(
            """
            SELECT proposition_id, array_cosine_similarity(embedding, ?::FLOAT[768]) as sim
            FROM proposition_embeddings
            ORDER BY sim DESC
            LIMIT ?
            """,
            [query_embedding, limit],
        ).fetchall()
        return [(r[0], float(r[1])) for r in res]

    def insert_principle(self, p: Principle) -> None:
        self.con.execute(
            """
            INSERT INTO principles VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (principle_id) DO UPDATE SET
                canonical_text = excluded.canonical_text,
                actor_role = excluded.actor_role,
                actor_slot_examples = excluded.actor_slot_examples,
                embedding_ref = excluded.embedding_ref,
                subject_ids = excluded.subject_ids
            """,
            [
                p.principle_id,
                p.canonical_text,
                p.actor_role,
                p.actor_slot_examples,
                p.embedding_ref,
                p.subject_ids,
            ],
        )

    def insert_principle_embedding(self, principle_id: str, embedding: list[float]) -> None:
        if len(embedding) != 768:
            raise ValueError(f"Vector width must be exactly 768, got {len(embedding)}")
        self.con.execute(
            """
            INSERT INTO principle_embeddings VALUES (?, ?::FLOAT[768])
            ON CONFLICT (principle_id) DO UPDATE SET embedding = excluded.embedding
            """,
            [principle_id, embedding],
        )

    def insert_topic(self, t: Topic) -> None:
        self.con.execute(
            """
            INSERT INTO topics VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (topic_id) DO UPDATE SET
                label = excluded.label,
                proposition_ids = excluded.proposition_ids,
                global_topic_id = excluded.global_topic_id
            """,
            [
                t.topic_id,
                t.subject_id,
                t.label,
                t.proposition_ids,
                t.global_topic_id,
            ],
        )

    def get_topic(self, topic_id: str) -> Topic | None:
        res = self.con.execute("SELECT * FROM topics WHERE topic_id = ?", [topic_id]).fetchone()
        if not res:
            return None
        return Topic(
            topic_id=res[0],
            subject_id=res[1],
            label=res[2],
            proposition_ids=res[3] if res[3] is not None else [],
            global_topic_id=res[4],
        )

    def get_topics_for_subject(self, subject_id: str) -> list[Topic]:
        rows = self.con.execute("SELECT * FROM topics WHERE subject_id = ?", [subject_id]).fetchall()
        return [
            Topic(
                topic_id=r[0],
                subject_id=r[1],
                label=r[2],
                proposition_ids=r[3] if r[3] is not None else [],
                global_topic_id=r[4],
            )
            for r in rows
        ]

    def insert_topic_resolution(
        self,
        resolution_key: str,
        subject_id: str,
        normalized_query: str,
        embedding_model: str,
        cluster_version: str,
        proposition_ids: list[str],
        resolved_at: str,
    ) -> None:
        self.con.execute(
            """
            INSERT INTO topic_resolutions VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (resolution_key) DO UPDATE SET
                proposition_ids = excluded.proposition_ids,
                resolved_at = excluded.resolved_at
            """,
            [
                resolution_key,
                subject_id,
                normalized_query,
                embedding_model,
                cluster_version,
                proposition_ids,
                resolved_at,
            ],
        )

    def get_topic_resolution(self, resolution_key: str) -> list[str] | None:
        res = self.con.execute(
            "SELECT proposition_ids FROM topic_resolutions WHERE resolution_key = ?",
            [resolution_key],
        ).fetchone()
        if not res:
            return None
        return list(res[0]) if res[0] is not None else []

    def insert_tension(self, t: Tension) -> None:
        self.con.execute(
            """
            INSERT INTO tensions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tension_id) DO UPDATE SET
                type = excluded.type,
                claim_a_id = excluded.claim_a_id,
                claim_b_id = excluded.claim_b_id,
                severity = excluded.severity,
                status = excluded.status,
                quarantine_reason = excluded.quarantine_reason
            """,
            [
                t.tension_id,
                t.type,
                t.claim_a_id,
                t.claim_b_id,
                t.proposition_id,
                t.principle_id,
                t.severity,
                t.detector_version,
                t.status,
                t.quarantine_reason,
            ],
        )

    def get_tension(self, tension_id: str) -> Tension | None:
        res = self.con.execute("SELECT * FROM tensions WHERE tension_id = ?", [tension_id]).fetchone()
        if not res:
            return None
        return Tension(
            tension_id=res[0],
            type=res[1],
            claim_a_id=res[2],
            claim_b_id=res[3],
            proposition_id=res[4],
            principle_id=res[5],
            severity=float(res[6]),
            detector_version=res[7],
            status=res[8],
            quarantine_reason=res[9],
        )

    def get_tensions_for_subject(self, subject_id: str, status: str | None = None) -> list[Tension]:
        query = """
            SELECT t.* FROM tensions t
            JOIN claims c ON t.claim_a_id = c.claim_id
            WHERE c.subject_id = ?
        """
        params: list[Any] = [subject_id]
        if status is not None:
            query += " AND t.status = ?"
            params.append(status)
        rows = self.con.execute(query, params).fetchall()
        return [
            Tension(
                tension_id=r[0],
                type=r[1],
                claim_a_id=r[2],
                claim_b_id=r[3],
                proposition_id=r[4],
                principle_id=r[5],
                severity=float(r[6]),
                detector_version=r[7],
                status=r[8],
                quarantine_reason=r[9],
            )
            for r in rows
        ]

    def insert_assessment(self, a: Assessment) -> None:
        import json
        self.con.execute(
            """
            INSERT INTO assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (assessment_id) DO UPDATE SET
                sufficiency = excluded.sufficiency,
                axes = excluded.axes,
                axis_evidence = excluded.axis_evidence,
                computed_at = excluded.computed_at
            """,
            [
                a.assessment_id,
                a.subject_id,
                a.topic_id,
                a.rubric_version,
                a.extraction_model_set,
                a.detector_version,
                a.embedding_model,
                a.nlp_version,
                json.dumps(a.sufficiency),
                json.dumps(a.axes),
                json.dumps(a.axis_evidence),
                a.computed_at,
            ],
        )

    def detect_unacknowledged_reversals(self, subject_id: str) -> list[tuple[str, str, str]]:
        """Core detector query from design_data_layer.md §4.

        Finds contradictory claims over shared propositions for a subject.
        """
        query = """
            SELECT a.claim_id, b.claim_id, a.proposition_id
            FROM claims a JOIN claims b
              ON a.proposition_id = b.proposition_id
             AND a.subject_id     = b.subject_id
             AND a.recorded_at    < b.recorded_at
             AND a.stance <> b.stance
            WHERE a.subject_id = ?
              AND a.is_own_assertion AND b.is_own_assertion
              AND a.stance IN ('support', 'oppose') AND b.stance IN ('support', 'oppose')
        """
        res = self.con.execute(query, [subject_id]).fetchall()
        return [(r[0], r[1], r[2]) for r in res]
