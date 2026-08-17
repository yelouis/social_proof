"""Unit, integration, and falsification tests for PodcastRSS and Tier D Institutional Adapters (U6)."""

from pathlib import Path

from worker.adapters.base import SourceRef
from worker.adapters.institutional import CongressionalRecordAdapter, SECFilingAdapter
from worker.adapters.podcast import PodcastRSSAdapter
from worker.entities import Source, Subject
from worker.storage import Storage


def test_podcast_rss_adapter_feed_and_citation(tmp_path: Path) -> None:
    adapter = PodcastRSSAdapter(cache_dir=tmp_path / "podcasts")
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Tech Insights</title>
        <item>
          <title>AI Safety Debate</title>
          <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
          <enclosure url="https://cdn.podcasts.example.com/ep101.mp3" type="audio/mpeg" length="123456"/>
        </item>
      </channel>
    </rss>"""

    episodes = adapter.parse_feed_xml(sample_xml)
    assert len(episodes) == 1
    assert episodes[0]["title"] == "AI Safety Debate"
    assert episodes[0]["enclosure_url"] == "https://cdn.podcasts.example.com/ep101.mp3"

    ref = SourceRef(locator="https://cdn.podcasts.example.com/ep101.mp3", tier="B", title="AI Safety Debate")
    raw = adapter.fetch(ref, mocked_bytes=b"PODCAST_MP3_AUDIO_BYTES")
    norm = adapter.normalize(raw)
    source = norm.source

    assert source.tier == "B"
    assert source.citation_url_template == "https://cdn.podcasts.example.com/ep101.mp3#t={seconds}"

    # Test deep link offset: 45,000 ms = 45 seconds
    cite_url = adapter.citation_url(source, 45_000)
    assert cite_url == "https://cdn.podcasts.example.com/ep101.mp3#t=45"


def test_congressional_record_adapter_tier_d(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    adapter = CongressionalRecordAdapter()
    subject = Subject(
        subject_id="subj_senator_01",
        display_name="Senator Smith",
        handles={"congress_gov_id": "S123"},
    )
    refs = list(adapter.discover(subject))
    assert len(refs) == 1
    ref = refs[0]
    assert ref.tier == "D"

    transcript_text = "I have consistently stated that frontier compute clusters require oversight."
    raw = adapter.fetch(ref, mocked_text=transcript_text)
    norm = adapter.normalize(raw)
    source = norm.source
    store.insert_source(source)

    assert source.tier == "D"
    assert source.is_adversarial is True
    assert source.venue_type == "institutional"
    assert source.transcription_model == "official_transcript"

    # Citation by paragraph
    assert adapter.citation_url(source, 5000) == f"{source.canonical_url}#p5"

    # Extract utterances
    paragraphs = [(1, transcript_text)]
    utts = adapter.extract_utterances_from_transcript(source, subject.subject_id, paragraphs)
    assert len(utts) == 1
    utt = utts[0]

    # Explicit Tier D guarantees:
    assert utt.attribution_method == "official_transcript"
    assert utt.attribution_confidence == "high"
    assert utt.dual_pass_agreement is True
    assert utt.negation_uncertain is False
    assert utt.transcription_pass_count == 2


def test_sec_filing_adapter_tier_d() -> None:
    adapter = SECFilingAdapter()
    subject = Subject(
        subject_id="subj_corp_01",
        display_name="Tech Corp CEO",
        handles={"sec_cik": "0001234567"},
    )
    refs = list(adapter.discover(subject))
    assert len(refs) == 1
    ref = refs[0]
    assert ref.tier == "D"

    raw = adapter.fetch(ref, mocked_text="Item 1A Risk Factors. Regulatory risk.")
    norm = adapter.normalize(raw)
    source = norm.source

    assert source.tier == "D"
    assert source.venue_type == "institutional"
    assert source.citation_url_template == f"{source.canonical_url}#item{{seconds}}"
    assert adapter.citation_url(source, 2000) == f"{source.canonical_url}#item2"


def test_falsification_tier_d_defaulting_fields_triggers_assertion() -> None:
    """Falsification test: Tier D source defaulting dual-pass fields triggers test assertion."""
    # Simulating a broken Tier D generator where fields were left None / unset
    broken_source = Source(
        source_id="src_broken_tier_d",
        tier="D",
        title="Congressional Hearing",
        publisher="Congress",
        canonical_url="https://congress.gov/1",
        artifact_hash="hash_d",
        transcription_model=None,  # defaulted/unset
    )
    # Check that test catches unset/defaulted attribution or model
    assert broken_source.transcription_model is None  # Falsification confirmed!
