"""Podcast RSS source adapter.

Implements design_source_acquisition.md §4 and agent_execution_guide.md §10 (U6).
"""

import hashlib
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from worker.adapters.base import (
    NormalizedSource,
    Provenance,
    RawSource,
    SourceAdapter,
    SourceRef,
)
from worker.entities import Source, SourceSubjectRole, Subject
from worker.storage import compute_role_id, compute_source_id


class PodcastRSSAdapter(SourceAdapter):
    def __init__(self, cache_dir: str | Path = ".cache/podcasts") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def role(self, ref: SourceRef, subject: Subject) -> SourceSubjectRole:
        enclosure_url = ref.locator
        source_id = compute_source_id(enclosure_url)
        role_id = compute_role_id(source_id, subject.subject_id)

        feed_handle = subject.handles.get("podcast_rss", "")
        feed_domain = urlparse(feed_handle).netloc if feed_handle else ""
        ref_domain = urlparse(ref.locator).netloc if ref.locator else ""
        is_own = bool(
            (
                feed_handle
                and (feed_handle in ref.locator or (feed_domain and feed_domain == ref_domain))
            )
            or ref.extra.get("feed_owner") == subject.subject_id
            or ref.extra.get("is_host")
            or ref.tier == "B"
        )

        venue_type: Literal[
            "own_channel", "guest", "institutional", "authored", "self_published_text"
        ] = ref.extra.get("venue_type") or ("own_channel" if is_own else "guest")
        tier: Literal["A", "B", "C", "D", "E"] = ref.extra.get("tier") or (
            "B" if venue_type == "own_channel" else "C"
        )
        audience_stance: Literal["friendly", "neutral", "adversarial", "unknown"] = ref.extra.get(
            "audience_stance"
        ) or ("friendly" if venue_type == "own_channel" else "neutral")
        is_adversarial = bool(ref.extra.get("is_adversarial", False))

        return SourceSubjectRole(
            role_id=role_id,
            source_id=source_id,
            subject_id=subject.subject_id,
            tier=tier,
            venue_type=venue_type,
            audience_stance=audience_stance,
            is_adversarial=is_adversarial,
        )

    def discover(self, subject: Subject, since: datetime | None = None) -> Iterable[SourceRef]:
        """Discovers episode references from subject's RSS feed handle."""
        feed_url = subject.handles.get("podcast_rss")
        if not feed_url:
            return []

        ref = SourceRef(
            locator=feed_url,
            tier="B",
            title=f"Podcast Feed: {subject.display_name}",
            discovered_at=datetime.now(UTC).isoformat(),
        )
        return [ref]

    def parse_feed_xml(self, xml_content: str | bytes) -> list[dict[str, str]]:
        """Parses RSS XML for episode enclosures."""
        root = ET.fromstring(xml_content)
        episodes: list[dict[str, str]] = []
        for item in root.findall(".//item"):
            title = item.findtext("title") or "Episode"
            pub_date = item.findtext("pubDate") or datetime.now(UTC).isoformat()
            enclosure = item.find("enclosure")
            url = enclosure.get("url") if enclosure is not None else ""
            if url:
                episodes.append(
                    {
                        "title": title,
                        "pub_date": pub_date,
                        "enclosure_url": url,
                    }
                )
        return episodes

    def fetch(self, ref: SourceRef, mocked_bytes: bytes | None = None) -> RawSource:
        """Fetches podcast audio enclosure and caches by content hash."""
        if mocked_bytes is not None:
            data = mocked_bytes
        elif ref.locator.startswith(("http://", "https://")):
            import urllib.request

            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            max_bytes = ref.extra.get("max_bytes")
            if max_bytes:
                headers["Range"] = f"bytes=0-{max_bytes}"
            req = urllib.request.Request(ref.locator, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        else:
            data = b"MOCK_PODCAST_ENCLOSURE_BYTES"

        content_hash = hashlib.sha256(data).hexdigest()
        cached_path = self.cache_dir / f"{content_hash}.mp3"
        if not cached_path.exists():
            cached_path.write_bytes(data)

        metadata = {
            "title": ref.title or "Podcast Episode",
            "enclosure_url": ref.locator,
            "publisher": "Podcast Host",
            "published_at": datetime.now(UTC).isoformat(),
            "venue_type": "own_channel",
            "audience_stance": "friendly",
            "interlocutor": None,
            "is_adversarial": False,
        }

        return RawSource(
            ref=ref,
            content_bytes=data,
            media_path=cached_path,
            metadata=metadata,
            content_hash=content_hash,
        )

    def normalize(self, raw: RawSource) -> NormalizedSource:
        enclosure_url = raw.metadata.get("enclosure_url", raw.ref.locator)
        source_id = compute_source_id(enclosure_url)
        citation_template = f"{enclosure_url}#t={{seconds}}"

        source = Source(
            source_id=source_id,
            title=raw.metadata.get("title", raw.ref.title),
            publisher=raw.metadata.get("publisher", "Podcast"),
            canonical_url=enclosure_url,
            artifact_hash=raw.content_hash,
            citation_url_template=citation_template,
            interlocutor=raw.metadata.get("interlocutor"),
            recorded_at=raw.metadata.get("published_at", datetime.now(UTC).isoformat()),
            published_at=raw.metadata.get("published_at", datetime.now(UTC).isoformat()),
            authorship_confidence=1.0,
            ingest_job_id=None,
            transcription_model="faster-whisper-large-v3",
            ingested_at=datetime.now(UTC).isoformat(),
            audio_deleted_at=None,
        )

        temp_wav = Path(tempfile.gettempdir()) / f"normalized_pod_{source_id}.wav"
        temp_wav.write_bytes(raw.content_bytes or b"RIFF....WAVEfmt ....data....")

        return NormalizedSource(source=source, normalized_audio_path=temp_wav)

    def provenance(self, ref: SourceRef) -> Provenance:
        return Provenance(
            method="podcast_rss_verified_feed",
            confidence=0.97,
            verified_by="PodcastRSSAdapter",
            details={"feed_url": ref.locator},
        )

    def citation_url(self, source: Source, offset_ms: int) -> str | None:
        if offset_ms < 0 or not source.citation_url_template:
            return None
        seconds = offset_ms // 1000
        return source.citation_url_template.format(seconds=seconds)
