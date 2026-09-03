"""Pydantic request and response schemas for the local HTTP API.

Implements design_local_api_and_clients.md §3 and §4.
"""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    corpus_stats: dict[str, int] = Field(default_factory=dict)
    worker_status: str = "idle"


class SubjectSummary(BaseModel):
    subject_id: str
    display_name: str
    confidence: float = 1.0


class SubjectDetailResponse(BaseModel):
    subject_id: str
    display_name: str
    corpus_stats: dict[str, Any] = Field(default_factory=dict)
    available_topics: list[str] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    selected_text: str
    context_before: str = ""
    context_after: str = ""
    page_url: str = ""
    page_title: str = ""


class ResolvedProposition(BaseModel):
    id: str
    canonical_text: str
    confidence: float


class ResolvedTopic(BaseModel):
    query_string: str
    confidence: float


class ResolveResponse(BaseModel):
    subjects: list[SubjectSummary] = Field(default_factory=list)
    proposition: ResolvedProposition | None = None
    topics: list[ResolvedTopic] = Field(default_factory=list)


class TopicSummary(BaseModel):
    topic_id: str
    label: str
    proposition_count: int


class ClaimTimelineItem(BaseModel):
    claim_id: str
    quote_text: str
    stance: str
    hedging_level: float
    recorded_at: str
    source_title: str
    source_url: str
    venue_type: str = "podcast"


class TimelineResponse(BaseModel):
    subject_id: str
    topic: str
    claims: list[ClaimTimelineItem] = Field(default_factory=list)


class TensionDetailResponse(BaseModel):
    tension_id: str
    type: str
    claim_a: dict[str, Any]
    claim_b: dict[str, Any]
    stated_distinction: str | None = None
    severity: float = 0.0
    detector_version: str = ""


class CompareResponse(BaseModel):
    subject_a: dict[str, Any]
    subject_b: dict[str, Any]
    rubric_version: str
    topic: str


class IngestJobRequest(BaseModel):
    subject_id: str
    adapters: list[str] = Field(default_factory=list)
    since: str = ""


class IngestJobResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    metrics: dict[str, Any] = Field(default_factory=dict)
