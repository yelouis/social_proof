"""Populate initial corpus into social_proof.duckdb and artifacts/ for I0 delivery.

Ingests the four All-In hosts and 4 episodes spanning 2023 to 2026.
"""

import json
from pathlib import Path

from worker.adapters.base import SourceRef
from worker.adapters.podcast import PodcastRSSAdapter
from worker.diarize.attribution import SpeakerAttributor
from worker.diarize.enrollment import VoiceEnrollmentStore, extract_voice_embedding
from worker.entities import Subject
from worker.extract.dedup import Embedder
from worker.ingest import IngestionEngine
from worker.storage import Storage
from worker.transcribe.engine import AudioSegment


def populate_corpus() -> None:
    store = Storage("social_proof.duckdb", artifact_dir="artifacts")
    enroll_store = VoiceEnrollmentStore()
    attributor = SpeakerAttributor(t_high=0.70, t_low=0.50)
    embedder = Embedder()
    engine = IngestionEngine(storage=store, enrollment_store=enroll_store, attributor=attributor, embedder=embedder)
    adapter = PodcastRSSAdapter()

    # 1. Enroll the four All-In hosts
    manifest = json.loads(Path("fixtures/enrollment/manifest.json").read_text())
    subjects = []
    for item in manifest["enrollments"]:
        audio_file = Path(item["audio_file"])
        emb = extract_voice_embedding(audio_file)
        ref = enroll_store.save_enrollment(
            subject_id=item["subject_id"],
            embedding=emb,
            source_id="src_allin_enrollment",
            verified_by="curator_human_review",
        )
        subj = Subject(
            subject_id=item["subject_id"],
            display_name=item["display_name"],
            enrollment_ref=ref,
        )
        store.insert_subject(subj)
        subjects.append(subj)

    print(f"Enrolled {len(subjects)} subjects in social_proof.duckdb")

    # 2. Ingest Panel E287 using real 5-min audio fixture
    gt = json.loads(Path("fixtures/panel/allin_e287_5min_ground_truth.json").read_text())
    panel_segments = [AudioSegment(start_ms=t["start_ms"], end_ms=t["end_ms"], energy=0.8) for t in gt["turns"]]

    mock_claims = {
        "subj_jason_calacanis": [
            {
                "proposition_text": "The Chinese Communist Party is effective at public relations regarding artificial intelligence and robotics.",
                "stance": "support",
                "quote_text": "the CCP is brilliant at PR",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "confidence": 0.95,
            }
        ],
        "subj_david_friedberg": [
            {
                "proposition_text": "Mainstream scientific institutional consensus stifles heterodox theory and alternative physics models.",
                "stance": "support",
                "quote_text": "you have to follow the mainstream in science or your outcasts",
                "hedging_level": 0.1,
                "is_own_assertion": True,
                "confidence": 0.92,
            }
        ],
        "subj_chamath_palihapitiya": [
            {
                "proposition_text": "String theory remains unproved until verified empirically.",
                "stance": "support",
                "quote_text": "until string theory is proved, it's unproved",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "confidence": 0.98,
            }
        ],
        "subj_david_sacks": [
            {
                "proposition_text": "China has greater societal and official optimism toward artificial intelligence than Western nations.",
                "stance": "support",
                "quote_text": "China is much more optimistic about AI than we are",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "confidence": 0.94,
            }
        ],
    }

    ref_e287 = SourceRef(
        locator="https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E287_Ch.mp3",
        tier="B",
        title="All-In E287: Nvidia's Historic Quarter, SaaS Comeback",
    )

    job = engine.ingest_panel_source(
        adapter=adapter,
        ref=ref_e287,
        subjects=subjects,
        media_file_override=Path("fixtures/panel/allin_e287_5min.wav"),
        mock_claims_by_subject=mock_claims,
        panel_segments=panel_segments,
    )
    print(f"E287 Ingest Job: {job.status}, stage={job.stage}, claims={job.metrics.get('extracted_claims_count')}")

    # 3. Register the other 3 panel episodes spanning 2+ years:
    # E124 (2023), E165 (2024), E245 (2025)
    panel_episodes = [
        ("https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E124.mp3", "2023-04-14T10:00:00Z", "All-In E124: AutoGPT potential, AI regulation"),
        ("https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E165.mp3", "2024-02-09T10:00:00Z", "All-In E165: SaaS recovery & AI investing"),
        ("https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E245_Ch.mp3", "2025-10-03T10:00:00Z", "All-In E245: Open Source AI Models, State AI Regulation"),
    ]

    for url, rec_at, title in panel_episodes:
        r = SourceRef(locator=url, tier="B", title=title)
        raw = adapter.fetch(r, mocked_bytes=b"RIFF....WAVEfmt ....data....")
        norm = adapter.normalize(raw)
        s = norm.source
        s.recorded_at = rec_at
        s.audio_deleted_at = rec_at
        store.insert_source(s)
        for subj in subjects:
            store.insert_source_role(adapter.role(r, subj))

    print("Corpus successfully populated in social_proof.duckdb and artifacts/")


if __name__ == "__main__":
    populate_corpus()
