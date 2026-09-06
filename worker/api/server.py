"""FastAPI server for the local analysis engine.

Implements design_local_api_and_clients.md and agent_execution_guide.md §22 (P7).
Enforces:
1. Bind 127.0.0.1 loopback only.
2. Bearer token auth & strict CORS.
3. Selection-triggered /resolve without persisting any page context (Journey J8).
4. Head-to-head comparison version mismatch guard (HTTP 409).
"""

import asyncio
import json
import uuid
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from worker.api.models import (
    ClaimTimelineItem,
    CompareResponse,
    HealthResponse,
    IngestJobRequest,
    IngestJobResponse,
    ResolvedProposition,
    ResolvedTopic,
    ResolveRequest,
    ResolveResponse,
    SubjectDetailResponse,
    SubjectSummary,
    TensionDetailResponse,
    TimelineResponse,
    TopicSummary,
)
from worker.api.queries import (
    get_all_subjects,
    get_claim_panel,
    get_episode_detail,
    get_episodes_list,
    get_person_detail,
)
from worker.api.security import TokenManager, auth_middleware, validate_host
from worker.api.templates import (
    render_claim_panel_page,
    render_episode_page,
    render_index_page,
    render_person_page,
)
from worker.entities import Assessment, IngestJob, Tension
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.topics.resolve import TopicResolver


def create_app(
    storage: Storage,
    token: str | None = None,
    embedder: Any = None,
    host: str = "127.0.0.1",
) -> FastAPI:
    """Application factory for Social Proof Local API."""
    validate_host(host)

    app = FastAPI(
        title="Social Proof Local API",
        version="0.1.0",
        docs_url=None,  # Disable Swagger UI to eliminate discovery surface
        redoc_url=None,
    )

    token_manager = TokenManager(token=token)
    app.state.token_manager = token_manager
    app.state.storage = storage
    app.state.rubric_engine = RubricEngine(storage=storage)
    app.state.resolver = TopicResolver(storage=storage, embedder=embedder)
    app.state.embedder = embedder

    if storage.read_only:
        read_only_con = duckdb.connect(str(storage.db_path), read_only=True)
    else:
        try:
            read_only_con = duckdb.connect(str(storage.db_path), read_only=True)
        except Exception:
            read_only_con = storage.con.cursor()
    app.state.read_only_con = read_only_con

    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

    # --- Review Site HTML Routes (Issue 028 & Issue 033) ---

    @app.get("/", response_class=HTMLResponse)
    def review_index(token: str | None = None) -> HTMLResponse:
        """Route 1: Episodes catalog (newest first) & Persons."""
        episodes = get_episodes_list(app.state.read_only_con)
        subjects = get_all_subjects(app.state.read_only_con)
        html_content = render_index_page(episodes, subjects, token=token)
        return HTMLResponse(content=html_content)

    @app.get("/episode/{source_id}", response_class=HTMLResponse)
    def review_episode(source_id: str, token: str | None = None) -> HTMLResponse:
        """Route 2: Episode detail with claims grouped by person in timestamp order."""
        ep_detail = get_episode_detail(app.state.read_only_con, source_id)
        if not ep_detail:
            raise HTTPException(status_code=404, detail="Episode not found")
        html_content = render_episode_page(ep_detail, token=token)
        return HTMLResponse(content=html_content)

    @app.get("/claim/{claim_id}", response_class=HTMLResponse)
    def review_claim(claim_id: str, token: str | None = None) -> HTMLResponse:
        """Route 3: Social Proof Panel (Depth 2)."""
        panel_data = get_claim_panel(app.state.read_only_con, claim_id)
        if not panel_data:
            raise HTTPException(status_code=404, detail="Claim not found")
        html_content = render_claim_panel_page(panel_data, token=token)
        return HTMLResponse(content=html_content)

    @app.get("/person/{subject_id}", response_class=HTMLResponse)
    def review_person(subject_id: str, token: str | None = None) -> HTMLResponse:
        """Route 4: Person dossier across all episodes."""
        person_data = get_person_detail(app.state.read_only_con, subject_id)
        if not person_data:
            raise HTTPException(status_code=404, detail="Person not found")
        html_content = render_person_page(person_data, token=token)
        return HTMLResponse(content=html_content)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        r_subjs = storage.con.execute("SELECT count(*) FROM subjects").fetchone()
        subjs = int(r_subjs[0]) if r_subjs else 0
        r_claims = storage.con.execute("SELECT count(*) FROM claims").fetchone()
        claims = int(r_claims[0]) if r_claims else 0
        r_tensions = storage.con.execute(
            "SELECT count(*) FROM tensions WHERE status = 'published'"
        ).fetchone()
        tensions = int(r_tensions[0]) if r_tensions else 0
        return HealthResponse(
            status="ok",
            version="0.1.0",
            corpus_stats={
                "subjects_count": subjs,
                "claims_count": claims,
                "tensions_count": tensions,
            },
            worker_status="idle",
        )

    @app.get("/subjects", response_model=list[SubjectSummary])
    def get_subjects(q: str = Query(default="")) -> list[SubjectSummary]:
        rows = storage.con.execute(
            "SELECT subject_id, display_name FROM subjects"
        ).fetchall()
        results: list[SubjectSummary] = []
        q_clean = q.strip().lower()
        for sid, name in rows:
            if not q_clean or q_clean in name.lower():
                results.append(SubjectSummary(subject_id=sid, display_name=name))
        return results

    @app.get("/subjects/{subject_id}", response_model=SubjectDetailResponse)
    def get_subject_detail(subject_id: str) -> SubjectDetailResponse:
        subj = storage.get_subject(subject_id)
        if not subj:
            raise HTTPException(status_code=404, detail="Subject not found")

        r_c = storage.con.execute(
            "SELECT count(*) FROM claims WHERE subject_id = ?", [subject_id]
        ).fetchone()
        claims_count = int(r_c[0]) if r_c else 0

        r_t = storage.con.execute(
            "SELECT count(*) FROM tensions WHERE status = 'published' AND ("
            "claim_a_id IN (SELECT claim_id FROM claims WHERE subject_id = ?) OR "
            "claim_b_id IN (SELECT claim_id FROM claims WHERE subject_id = ?))",
            [subject_id, subject_id],
        ).fetchone()
        tensions_count = int(r_t[0]) if r_t else 0

        topics = storage.get_topics_for_subject(subject_id)
        return SubjectDetailResponse(
            subject_id=subj.subject_id,
            display_name=subj.display_name,
            corpus_stats={
                "claims_count": claims_count,
                "tensions_count": tensions_count,
            },
            available_topics=[t.label for t in topics],
        )

    @app.post("/resolve", response_model=ResolveResponse)
    def resolve(req: ResolveRequest) -> ResolveResponse:
        """Selection-triggered resolution (design_local_api_and_clients.md §4).

        Selected text and context live in a request-scoped buffer and are NEVER
        written to DuckDB or disk artifacts (Journey J8 & Invariant I2).
        A proposition is MATCHED, never created.
        """
        text = req.selected_text.strip()
        full_context = f"{req.context_before} {text} {req.context_after}".lower()

        # 1. Match candidates by subject name/display_name in selection or context
        all_subjs = storage.con.execute(
            "SELECT subject_id, display_name FROM subjects"
        ).fetchall()
        matched_subjs: list[SubjectSummary] = []
        for sid, name in all_subjs:
            tokens = [tok.lower() for tok in name.split() if len(tok) >= 3]
            if any(tok in full_context for tok in tokens):
                matched_subjs.append(
                    SubjectSummary(subject_id=sid, display_name=name, confidence=0.95)
                )

        if not matched_subjs and all_subjs:
            # Fallback to all enrolled subjects
            for sid, name in all_subjs:
                matched_subjs.append(
                    SubjectSummary(subject_id=sid, display_name=name, confidence=0.50)
                )

        # 2. Try proposition match (highest precision)
        resolved_prop: ResolvedProposition | None = None
        if app.state.embedder is not None and matched_subjs:
            target_sid = matched_subjs[0].subject_id
            target_emb = app.state.embedder.embed_query(text)

            best_match = storage.con.execute(
                """
                SELECT p.proposition_id, p.canonical_text,
                       array_cosine_similarity(pe.embedding, ?::FLOAT[768]) as sim
                FROM propositions p
                JOIN proposition_embeddings pe ON p.proposition_id = pe.proposition_id
                WHERE p.status = 'active'
                  AND EXISTS (SELECT 1 FROM claims c WHERE c.proposition_id = p.proposition_id)
                  AND list_contains(p.subject_ids, ?)
                ORDER BY sim DESC
                LIMIT 1;
                """,
                [target_emb, target_sid],
            ).fetchone()

            if best_match and best_match[2] is not None and best_match[2] >= 0.70:
                resolved_prop = ResolvedProposition(
                    id=best_match[0],
                    canonical_text=best_match[1],
                    confidence=round(float(best_match[2]), 4),
                )

        # 3. Try topic fallback
        resolved_topics: list[ResolvedTopic] = []
        if resolved_prop is None and matched_subjs:
            target_sid = matched_subjs[0].subject_id
            _, pids, status_str = app.state.resolver.resolve_topic(
                target_sid, text, expand_clusters=True
            )
            if status_str == "ok" and pids:
                resolved_topics.append(
                    ResolvedTopic(query_string=text, confidence=0.85)
                )

        return ResolveResponse(
            subjects=matched_subjs,
            proposition=resolved_prop,
            topics=resolved_topics,
        )

    @app.get("/subjects/{subject_id}/topics", response_model=list[TopicSummary])
    def get_subject_topics(subject_id: str) -> list[TopicSummary]:
        topics = storage.get_topics_for_subject(subject_id)
        return [
            TopicSummary(
                topic_id=t.topic_id,
                label=t.label,
                proposition_count=len(t.proposition_ids),
            )
            for t in topics
        ]

    @app.get("/subjects/{subject_id}/assessment")
    def get_assessment(
        subject_id: str,
        topic: str = Query(default="global"),
    ) -> dict[str, Any]:
        subj = storage.get_subject(subject_id)
        if not subj:
            raise HTTPException(status_code=404, detail="Subject not found")

        assessment = app.state.rubric_engine.assess_subject_topic(
            subject_id=subject_id,
            topic_id=topic,
        )
        return {
            "assessment_id": assessment.assessment_id,
            "subject_id": assessment.subject_id,
            "topic_id": assessment.topic_id,
            "rubric_version": assessment.rubric_version,
            "extraction_model_set": assessment.extraction_model_set,
            "detector_version": assessment.detector_version,
            "embedding_model": assessment.embedding_model,
            "nlp_version": assessment.nlp_version,
            "sufficiency": assessment.sufficiency,
            "axes": assessment.axes,
            "axis_evidence": assessment.axis_evidence,
            "computed_at": assessment.computed_at,
        }

    @app.get("/subjects/{subject_id}/timeline", response_model=TimelineResponse)
    def get_timeline(
        subject_id: str,
        topic: str = Query(default="global"),
    ) -> TimelineResponse:
        claims = storage.get_claims_for_subject(subject_id)
        items: list[ClaimTimelineItem] = []
        for c in claims:
            # Query source metadata
            utt = storage.get_utterance(c.utterance_id)
            src_title = "Unknown Source"
            src_url = ""
            if utt:
                src = storage.get_source(utt.source_id)
                if src:
                    src_title = src.title
                    src_url = src.canonical_url

            items.append(
                ClaimTimelineItem(
                    claim_id=c.claim_id,
                    quote_text=c.quote_text or "",
                    stance=c.stance,
                    hedging_level=c.hedging_level,
                    recorded_at=c.recorded_at,
                    source_title=src_title,
                    source_url=src_url,
                )
            )

        return TimelineResponse(
            subject_id=subject_id,
            topic=topic,
            claims=items,
        )

    @app.get("/tensions/{tension_id}", response_model=TensionDetailResponse)
    def get_tension_detail(tension_id: str) -> TensionDetailResponse:
        t: Tension | None = storage.get_tension(tension_id)
        if not t:
            raise HTTPException(status_code=404, detail="Tension not found")

        claim_a = storage.get_claim(t.claim_a_id)
        claim_b = storage.get_claim(t.claim_b_id)

        return TensionDetailResponse(
            tension_id=t.tension_id,
            type=t.type,
            claim_a={
                "claim_id": claim_a.claim_id if claim_a else t.claim_a_id,
                "stance": claim_a.stance if claim_a else "",
                "quote_text": claim_a.quote_text if claim_a else "",
                "recorded_at": claim_a.recorded_at if claim_a else "",
            },
            claim_b={
                "claim_id": claim_b.claim_id if claim_b else t.claim_b_id,
                "stance": claim_b.stance if claim_b else "",
                "quote_text": claim_b.quote_text if claim_b else "",
                "recorded_at": claim_b.recorded_at if claim_b else "",
            },
            stated_distinction=t.quarantine_reason if t.status == "dismissed" else None,
            severity=t.severity,
            detector_version=t.detector_version,
        )

    @app.get("/compare", response_model=CompareResponse)
    def compare(
        a: str = Query(..., description="Subject ID A"),
        b: str = Query(..., description="Subject ID B"),
        topic: str = Query(default="global"),
    ) -> CompareResponse:
        """Head-to-head comparison.

        Enforces rubric_version compatibility. Returns HTTP 409 Conflict if
        assessments were computed under different versions.
        """
        ass_a: Assessment = app.state.rubric_engine.assess_subject_topic(a, topic)
        ass_b: Assessment = app.state.rubric_engine.assess_subject_topic(b, topic)

        if ass_a.rubric_version != ass_b.rubric_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Cannot compare assessments computed under different rubric versions ({ass_a.rubric_version} vs {ass_b.rubric_version})",
            )

        return CompareResponse(
            subject_a={"subject_id": a, "axes": ass_a.axes},
            subject_b={"subject_id": b, "axes": ass_b.axes},
            rubric_version=ass_a.rubric_version,
            topic=topic,
        )

    @app.post("/ingest", response_model=IngestJobResponse, status_code=status.HTTP_202_ACCEPTED)
    def enqueue_ingest(req: IngestJobRequest) -> IngestJobResponse:
        """Enqueues an ingest job (Invariant I8: never writes to claim store directly)."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = IngestJob(
            job_id=job_id,
            subject_id=req.subject_id,
            adapter=",".join(req.adapters) if req.adapters else "PodcastRSSAdapter",
            status="queued",
            stage="queued",
        )
        storage.insert_ingest_job(job)
        return IngestJobResponse(
            job_id=job.job_id,
            status=job.status,
            stage=job.stage,
            metrics={},
        )

    @app.get("/ingest/{job_id}", response_model=IngestJobResponse)
    def get_ingest_status(job_id: str) -> IngestJobResponse:
        job = storage.get_ingest_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Ingest job not found")
        return IngestJobResponse(
            job_id=job.job_id,
            status=job.status,
            stage=job.stage,
            metrics=job.metrics,
        )

    @app.get("/ingest/{job_id}/stream")
    async def stream_ingest(job_id: str) -> StreamingResponse:
        """SSE progress stream for long-running ingest jobs."""
        async def event_generator() -> Any:
            for _ in range(5):
                job = storage.get_ingest_job(job_id)
                current_stage = job.stage if job else "unknown"
                yield f"data: {json.dumps({'job_id': job_id, 'stage': current_stage})}\n\n"
                await asyncio.sleep(0.01)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app


def run_server(
    storage: Storage,
    host: str = "127.0.0.1",
    port: int = 8787,
    token: str | None = None,
) -> None:
    """Entrypoint to run the local API server via uvicorn on loopback only."""
    import uvicorn
    validate_host(host)
    app = create_app(storage=storage, token=token, host=host)
    uvicorn.run(app, host=host, port=port)
