"""Core entity dataclasses matching design_data_layer.md §2 verbatim."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Subject:
    subject_id: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    handles: dict[str, str] = field(default_factory=dict)
    enrollment_ref: str | None = None
    corpus_stats: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Source:
    source_id: str
    title: str
    publisher: str
    canonical_url: str
    artifact_hash: str
    citation_url_template: str | None = None
    interlocutor: str | None = None
    recorded_at: str = ""
    published_at: str = ""
    authorship_confidence: float | None = None
    ingest_job_id: str | None = None
    transcription_model: str | None = None
    ingested_at: str | None = None
    audio_deleted_at: str | None = None


@dataclass
class SourceSubjectRole:
    role_id: str
    source_id: str
    subject_id: str
    tier: Literal["A", "B", "C", "D", "E"]
    venue_type: Literal["own_channel", "guest", "institutional", "authored", "self_published_text"] = "own_channel"
    audience_stance: Literal["friendly", "neutral", "adversarial", "unknown"] = "unknown"
    is_adversarial: bool = False


@dataclass
class Utterance:
    utterance_id: str
    source_id: str
    subject_id: str
    text_verbatim: str
    start_ms: int
    end_ms: int
    speaker_label: str
    attribution_confidence: Literal["high", "low", "discard"] | float | str
    attribution_method: str
    word_timestamps_ref: str | None = None
    language: str = "en"
    transcription_pass_count: int = 2
    dual_pass_agreement: bool = True
    negation_uncertain: bool = False


@dataclass
class Claim:
    claim_id: str
    subject_id: str
    utterance_id: str
    proposition_id: str
    stance: Literal["support", "oppose", "mixed", "hedge"]
    hedging_level: float
    is_own_assertion: bool
    exclusion_reason: (
        Literal[
            "reported_speech",
            "hypothetical",
            "sarcasm",
            "steelman",
            "joke",
            "question",
            "quote_agreement_unclear",
        ]
        | str
        | None
    ) = None
    confidence: float = 1.0
    quote_span: tuple[int, int] = (0, 0)
    condition: str | None = None
    prior_stance_reported: Literal["support", "oppose"] | None = None
    change_marker: dict[str, Any] | None = None
    extraction_model: str = ""
    prompt_version: str = ""
    extraction_version: str = ""
    recorded_at: str = ""
    quote_text: str | None = None


@dataclass
class Proposition:
    proposition_id: str
    canonical_text: str
    embedding_ref: str | None = None
    subject_ids: list[str] = field(default_factory=list)
    claim_count: int = 0
    status: Literal["active", "quarantined"] = "active"
    quarantine_reason: str | None = None


@dataclass
class Principle:
    principle_id: str
    canonical_text: str
    actor_role: str = ""
    actor_slot_examples: list[str] = field(default_factory=list)
    embedding_ref: str | None = None
    subject_ids: list[str] = field(default_factory=list)


@dataclass
class PrincipleApplication:
    application_id: str
    principle_id: str
    claim_id: str
    subject_id: str
    actor: str
    actor_affinity: Literal["ally", "opponent", "neutral", "self", "unknown"] = "unknown"
    verdict: Literal["applies", "does_not_apply", "applies_partially"] = "applies"
    stated_distinction: str | None = None
    confidence: float = 1.0
    recorded_at: str = ""


@dataclass
class Topic:
    topic_id: str
    subject_id: str
    label: str
    proposition_ids: list[str] = field(default_factory=list)
    global_topic_id: str | None = None


@dataclass
class Tension:
    tension_id: str
    type: Literal[
        "unacknowledged_reversal",
        "acknowledged_update",
        "principle_conflict",
        "audience_divergence",
    ]
    claim_a_id: str
    claim_b_id: str
    proposition_id: str | None = None
    principle_id: str | None = None
    severity: float = 0.0
    detector_version: str = ""
    status: Literal["published", "quarantined", "dismissed"] = "published"
    quarantine_reason: str | None = None


@dataclass
class Assessment:
    assessment_id: str
    subject_id: str
    topic_id: str
    rubric_version: str
    extraction_model_set: list[str] = field(default_factory=list)
    detector_version: str = ""
    embedding_model: str = ""
    nlp_version: str = ""
    sufficiency: dict[str, Any] = field(default_factory=dict)
    axes: dict[str, Any] = field(default_factory=dict)
    axis_evidence: dict[str, list[str]] = field(default_factory=dict)
    computed_at: str = ""


@dataclass
class IngestJob:
    job_id: str
    subject_id: str
    adapter: str
    status: str
    stage: str
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str | None = None
