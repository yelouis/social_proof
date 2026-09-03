"""Source Adapter protocol and data structures.

Matches design_source_acquisition.md §4 and agent_execution_guide.md §6 (U2).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from worker.entities import Source, SourceSubjectRole, Subject


@dataclass
class SourceRef:
    locator: str
    tier: Literal["A", "B", "C", "D", "E"]
    title: str = ""
    discovered_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawSource:
    ref: SourceRef
    content_bytes: bytes | None = None
    media_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""


@dataclass
class NormalizedSource:
    source: Source
    normalized_audio_path: Path | None = None  # Temp 16 kHz mono WAV
    normalized_text: str | None = None


@dataclass
class Provenance:
    method: str
    confidence: float
    verified_by: str = "adapter"
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SourceAdapter(Protocol):
    def role(self, ref: SourceRef, subject: Subject) -> SourceSubjectRole:
        """Tier and venue for THIS subject in THIS source (Issue 022 = A).

        The same episode is Tier B / own_channel for a host and
        Tier C / guest for a visitor. An adapter has no single tier.
        """
        ...

    def discover(self, subject: Subject, since: datetime | None = None) -> Iterable[SourceRef]:
        """Find candidate sources. Cheap, metadata only, no media fetched."""
        ...

    def fetch(self, ref: SourceRef) -> RawSource:
        """Retrieve the artifact. Idempotent and cached by content hash."""
        ...

    def normalize(self, raw: RawSource) -> NormalizedSource:
        """Audio → 16 kHz mono; text → UTF-8 with byte offsets preserved."""
        ...

    def provenance(self, ref: SourceRef) -> Provenance:
        """How we know this is the subject. Never inferred by the pipeline."""
        ...

    def citation_url(self, source: Source, offset_ms: int) -> str | None:
        """Returns deep link at the given offset, or None if not supported.

        NEVER return bare source URL as a fallback.
        """
        ...
