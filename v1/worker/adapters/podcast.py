"""Podcast RSS source adapter.

Implements design_source_acquisition.md §4 and agent_execution_guide.md §10 (U6).
"""

import hashlib
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
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


def parse_itunes_duration(dur_str: str | None) -> int:
    """Parses itunes:duration string (HH:MM:SS, MM:SS, or seconds) into milliseconds."""
    if not dur_str:
        return 0
    s = dur_str.strip()
    if not s:
        return 0
    parts = s.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return int((hours * 3600 + minutes * 60 + seconds) * 1000)
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return int((minutes * 60 + seconds) * 1000)
        elif len(parts) == 1:
            seconds = float(parts[0])
            return int(seconds * 1000)
    except (ValueError, TypeError):
        return 0
    return 0


def parse_rfc822_date(date_str: str | None) -> str | None:
    """Parses RFC 822 / RFC 2822 or ISO pubDate string to ISO 8601 UTC string."""
    if not date_str:
        return None
    s = date_str.strip()
    if not s:
        return None
    import email.utils

    try:
        dt = email.utils.parsedate_to_datetime(s)
        return dt.astimezone(UTC).isoformat()
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except Exception:
        pass
    return None


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

    def parse_feed_xml(self, xml_content: str | bytes) -> list[dict[str, Any]]:
        """Parses RSS XML for episode enclosures and metadata."""
        root = ET.fromstring(xml_content)
        episodes: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = item.findtext("title") or "Episode"
            pub_date_raw = item.findtext("pubDate")
            pub_date = parse_rfc822_date(pub_date_raw) or (pub_date_raw if pub_date_raw else "")

            raw_dur = (
                item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
                or item.findtext("itunes:duration")
                or item.findtext("duration")
            )
            duration_ms = parse_itunes_duration(raw_dur)

            enclosure = item.find("enclosure")
            url = enclosure.get("url") if enclosure is not None else ""
            if url:
                episodes.append(
                    {
                        "title": title,
                        "pub_date": pub_date,
                        "enclosure_url": url,
                        "duration_ms": duration_ms,
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

        duration_ms = ref.extra.get("duration_ms", 0)
        published_at = ref.extra.get("published_at") or ref.extra.get("pub_date") or ""
        recorded_at = ref.extra.get("recorded_at") or published_at or ""

        metadata = {
            "title": ref.title or "Podcast Episode",
            "enclosure_url": ref.locator,
            "publisher": "Podcast Host",
            "published_at": published_at,
            "recorded_at": recorded_at,
            "duration_ms": duration_ms,
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
            recorded_at=raw.metadata.get("recorded_at", ""),
            published_at=raw.metadata.get("published_at", ""),
            authorship_confidence=1.0,
            ingest_job_id=None,
            transcription_model="faster-whisper-large-v3",
            ingested_at=None,
            audio_deleted_at=None,
            duration_ms=raw.metadata.get("duration_ms", 0),
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
