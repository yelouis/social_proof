"""Unit, integration, and falsification tests for YouTubeAdapter (U2)."""

from pathlib import Path

from worker.adapters.base import SourceRef
from worker.adapters.youtube import YouTubeAdapter, extract_youtube_video_id
from worker.entities import Source, Subject
from worker.storage import Storage


def test_extract_youtube_video_id() -> None:
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://example.com/not_youtube") is None


def test_youtube_adapter_discovery_and_fetch(tmp_path: Path) -> None:
    adapter = YouTubeAdapter(cache_dir=tmp_path / "media")
    subject = Subject(
        subject_id="subj_yt_01",
        display_name="Podcast Host",
        handles={"youtube": "https://www.youtube.com/watch?v=abcdef12345"},
    )
    refs = list(adapter.discover(subject))
    assert len(refs) == 1
    ref = refs[0]
    assert ref.locator == "https://www.youtube.com/watch?v=abcdef12345"
    assert ref.tier == "B"

    # Fetch with deterministic test content
    raw = adapter.fetch(ref, mocked_bytes=b"RIFF_AUDIO_DATA_FOR_TEST_01")
    assert raw.content_hash != ""
    assert raw.media_path is not None and raw.media_path.exists()

    normalized = adapter.normalize(raw)
    source = normalized.source
    role = adapter.role(ref, subject)

    # Assert source fields and role fields
    assert source.source_id != ""
    assert not hasattr(source, "tier")
    assert role.tier == "B"
    assert role.venue_type == "own_channel"
    assert role.audience_stance in ["friendly", "neutral", "adversarial", "unknown"]
    assert source.recorded_at != ""
    assert source.published_at != ""
    assert source.citation_url_template == "https://youtu.be/abcdef12345?t={seconds}"


def test_citation_url_exact_second_offset() -> None:
    adapter = YouTubeAdapter()
    source = Source(
        source_id="src_yt_01",
        title="Episode",
        publisher="Host",
        canonical_url="https://www.youtube.com/watch?v=abcdef12345",
        artifact_hash="hash_01",
        citation_url_template="https://youtu.be/abcdef12345?t={seconds}",
    )

    # 3,723,000 ms = 3723 seconds = 1 hour, 2 minutes, 3 seconds (01:02:03)
    url = adapter.citation_url(source, 3_723_000)
    assert url == "https://youtu.be/abcdef12345?t=3723"
    assert "t=3723" in url

    # Zero offset
    assert adapter.citation_url(source, 0) == "https://youtu.be/abcdef12345?t=0"

    # Negative offset returns None
    assert adapter.citation_url(source, -100) is None

    # Source without deep-link capability returns None, NEVER bare URL
    no_link_source = Source(
        source_id="src_nolink",
        title="Book",
        publisher="Press",
        canonical_url="https://books.example.com/123",
        artifact_hash="hash_book",
        citation_url_template=None,  # No deep link support
    )
    assert adapter.citation_url(no_link_source, 5000) is None


def test_content_hash_caching_and_url_independence(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    adapter = YouTubeAdapter(cache_dir=tmp_path / "media")

    audio_payload = b"IDENTICAL_AUDIO_PAYLOAD_DIFFERENT_URLS"

    # Fetch 1: via URL 1
    ref1 = SourceRef(locator="https://www.youtube.com/watch?v=vid11111111", tier="B")
    raw1 = adapter.fetch(ref1, mocked_bytes=audio_payload)
    norm1 = adapter.normalize(raw1)
    store.insert_source(norm1.source)

    # Fetch 2: via URL 2 (e.g. short link or CDN alias) with identical audio payload
    ref2 = SourceRef(locator="https://youtu.be/vid22222222", tier="B")
    raw2 = adapter.fetch(ref2, mocked_bytes=audio_payload)
    norm2 = adapter.normalize(raw2)

    # Both must share identical content/artifact hash
    assert raw1.content_hash == raw2.content_hash
    assert norm1.source.artifact_hash == norm2.source.artifact_hash


def test_falsification_bare_url_fallback_fails_deep_link_test() -> None:
    """Falsification test: If citation_url falls back to bare URL, deep link assertion fails."""
    class BrokenAdapter(YouTubeAdapter):
        def citation_url(self, source: Source, offset_ms: int) -> str | None:
            # Bad fallback: returns bare canonical_url
            return source.canonical_url

    broken = BrokenAdapter()
    source = Source(
        source_id="src_yt_01",
        title="Episode",
        publisher="Host",
        canonical_url="https://www.youtube.com/watch?v=abcdef12345",
        artifact_hash="hash_01",
        citation_url_template="https://youtu.be/abcdef12345?t={seconds}",
    )
    bad_url = broken.citation_url(source, 3_723_000)
    assert bad_url is not None
    # Must FAIL the t=3723 deep link assertion
    assert "t=3723" not in bad_url  # Falsification confirmed!
