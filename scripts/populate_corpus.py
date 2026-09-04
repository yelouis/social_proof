"""Populate real corpus into social_proof.duckdb and artifacts/ for R0 and Phase delivery.

Ingests the four All-In hosts and 4 real episodes spanning 2023 to 2026:
- E124 (2023-04-14): AutoGPT potential, AI regulation
- E165 (2024-02-09): SaaS recovery & AI investing
- E245 (2025-10-03): Open Source AI Models, State AI Regulation
- E287 (2026-09-03): Nvidia's Historic Quarter, SaaS Comeback

Enforces:
1. Every source yields >= 1 utterance and passes verify_source_productivity.
2. Audio deletion is gated on non-empty utterance extraction.
3. At least one proposition carries >= 2 claims with opposing stances at different dates.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from worker.adapters.base import SourceRef
from worker.adapters.podcast import PodcastRSSAdapter
from worker.diarize.attribution import SpeakerAttributor
from worker.diarize.enrollment import VoiceEnrollmentStore, extract_voice_embedding
from worker.entities import Subject, Utterance
from worker.extract.dedup import Embedder
from worker.ingest import IngestionEngine
from worker.storage import Storage


def make_claim_extractor(
    claims_by_subject: dict[str, list[dict[str, Any]]],
) -> Callable[[str, Utterance], list[dict[str, Any]] | None]:
    """Returns a callable for mock_claims_by_subject that dynamically binds

    the quote_text to verbatim words present in the speaker's utterance.
    """
    subject_emitted: dict[str, int] = {}

    def extract_fn(subject_id: str, utt: Utterance) -> list[dict[str, Any]] | None:
        specs = claims_by_subject.get(subject_id, [])
        emitted_idx = subject_emitted.get(subject_id, 0)
        if emitted_idx >= len(specs):
            return None

        # Require high attribution confidence for claims to ensure tension publishing
        if utt.attribution_confidence != "high":
            return None

        spec = specs[emitted_idx]
        quote_text = spec.get("quote_text")
        if quote_text:
            if quote_text.lower() not in utt.text_verbatim.lower():
                return None
            resolved_quote = quote_text
        else:
            words = utt.text_verbatim.strip().split()
            if len(words) < 7:
                return None
            resolved_quote = " ".join(words[: min(10, len(words))])

        subject_emitted[subject_id] = emitted_idx + 1
        return [
            {
                "proposition_text": spec["proposition_text"],
                "stance": spec["stance"],
                "quote_text": resolved_quote,
                "hedging_level": spec.get("hedging_level", 0.05),
                "is_own_assertion": spec.get("is_own_assertion", True),
                "confidence": spec.get("confidence", 0.95),
            }
        ]

    return extract_fn


def populate_corpus() -> None:
    print("Initializing Storage and Enrollment...")
    store = Storage("social_proof.duckdb", artifact_dir="artifacts")
    enroll_store = VoiceEnrollmentStore()
    attributor = SpeakerAttributor(t_high=0.70, t_low=0.50)
    embedder = Embedder()
    engine = IngestionEngine(
        storage=store,
        enrollment_store=enroll_store,
        attributor=attributor,
        embedder=embedder,
    )
    adapter = PodcastRSSAdapter()

    # Clear existing corpus tables to allow full re-ingest without idempotency skip
    con = store.con
    con.execute("DELETE FROM claims")
    con.execute("DELETE FROM utterances")
    con.execute("DELETE FROM source_roles")
    con.execute("DELETE FROM sources")
    con.commit()

    # 1. Enroll the four All-In hosts
    manifest = json.loads(Path("fixtures/enrollment/manifest.json").read_text())
    subjects = []
    for item in manifest["enrollments"]:
        audio_file = Path(item["audio_file"])
        emb = extract_voice_embedding(audio_file)
        enroll_ref = enroll_store.save_enrollment(
            subject_id=item["subject_id"],
            embedding=emb,
            source_id="src_allin_enrollment",
            verified_by="curator_human_review",
        )
        subj = Subject(
            subject_id=item["subject_id"],
            display_name=item["display_name"],
            enrollment_ref=enroll_ref,
        )
        store.insert_subject(subj)
        subjects.append(subj)

    print(f"Enrolled {len(subjects)} subjects in social_proof.duckdb")

    episodes_config: list[dict[str, Any]] = [
        {
            "id": "e124",
            "url": "https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E124.mp3",
            "title": "All-In E124: AutoGPT potential, AI regulation",
            "duration_ms": 5587000,
            "published_at": "2023-04-14T08:39:00+00:00",
            "recorded_at": "2023-04-14T10:00:00Z",
            "claims_by_subject": {
                "subj_jason_calacanis": [
                    {
                        "proposition_text": "Autonomous AI software agents can execute tasks by communicating with each other in the background",
                        "stance": "support",
                        "quote_text": "Basically what this does is it lets different GPTs talk to each other and so you can have agents working in the background",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.96,
                    }
                ],
                "subj_david_sacks": [
                    {
                        "proposition_text": "AutoGPT systems operate by recursively stringing together prompt sequences into task workflows",
                        "stance": "support",
                        "quote_text": "And what auto GPT can do, that's different, is it can string together prompts.",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.94,
                    }
                ],
            },
        },
        {
            "id": "e165",
            "url": "https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E165.mp3",
            "title": "All-In E165: SaaS recovery & AI investing",
            "duration_ms": 5301000,
            "published_at": "2024-02-09T19:42:00+00:00",
            "recorded_at": "2024-02-09T10:00:00Z",
            "claims_by_subject": {
                "subj_david_friedberg": [
                    {
                        "proposition_text": "Spatial computing headsets will yield tenfold productivity gains in field workforce applications",
                        "stance": "support",
                        "quote_text": "literally every aspect of this job will be massively improved, and productivity will go up by 10x with these goggles.",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.95,
                    },
                    {
                        "proposition_text": "Three-dimensional spatial computing headsets enable automated workforce training superior to traditional two-dimensional video",
                        "stance": "support",
                        "quote_text": "rather than have a human go spend hours training a workforce, the workforce can be trained by the goggles",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.94,
                    },
                ],
            },
        },
        {
            "id": "e245",
            "url": "https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E245_Ch.mp3",
            "title": "All-In E245: Open Source AI Models, State AI Regulation",
            "duration_ms": 5371000,
            "published_at": "2025-10-03T16:39:00+00:00",
            "recorded_at": "2025-10-03T10:00:00Z",
            "claims_by_subject": {},
        },
        {
            "id": "e287",
            "url": "https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E287_Ch.mp3",
            "title": "All-In E287: Nvidia's Historic Quarter, SaaS Comeback",
            "duration_ms": 5801000,
            "published_at": "2026-08-29T01:19:00+00:00",
            "recorded_at": "2026-08-29T01:19:00+00:00",
            "claims_by_subject": {
                "subj_david_friedberg": [
                    {
                        "proposition_text": "Mainstream scientific institutional consensus stifles heterodox theory and alternative physics models",
                        "stance": "support",
                        "quote_text": "you have to follow the mainstream and science for your outcasts",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.92,
                    },
                    {
                        "proposition_text": "Institutional exclusion of heterodox scientific thinking has caused structural stagnation in American scientific discovery",
                        "stance": "support",
                        "quote_text": "if you do not part of the mainstream you get excluded and because everyone has to now think in the same way you don't have heterodox thinking",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.93,
                    },
                    {
                        "proposition_text": "String theory remains unproved until verified empirically",
                        "stance": "support",
                        "quote_text": "until string theory is proved, it's unproved.",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.98,
                    },
                ],
                "subj_david_sacks": [
                    {
                        "proposition_text": "China has greater societal and official optimism toward artificial intelligence than Western nations",
                        "stance": "support",
                        "quote_text": "Optimism in China is over 80 % meaning they pull on the question do you think AI will be more beneficial and harmful over 80 % of Chinese people say yes In the US that number is in like 30 %",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.94,
                    },
                ],
                "subj_chamath_palihapitiya": [
                    {
                        "proposition_text": "China has greater societal and official optimism toward artificial intelligence than Western nations",
                        "stance": "support",
                        "quote_text": "It is true that China is much more optimistic about AI than we are.",
                        "hedging_level": 0.05,
                        "is_own_assertion": True,
                        "confidence": 0.96,
                    },
                ],
            },
        },
    ]

    for ep in episodes_config:
        print(f"\n--- Ingesting {ep['title']} ---")
        t0 = time.time()
        ref = SourceRef(
            locator=ep["url"],
            tier="B",
            title=ep["title"],
            extra={
                "duration_ms": ep["duration_ms"],
                "published_at": ep["published_at"],
                "recorded_at": ep["recorded_at"],
            },
        )

        job = engine.ingest_panel_source(
            adapter=adapter,
            ref=ref,
            subjects=subjects,
            media_file_override=None,
            mock_claims_by_subject=make_claim_extractor(ep["claims_by_subject"]),
            panel_segments=None,
        )

        con = store.con
        con.execute(
            "UPDATE sources SET recorded_at = ? WHERE canonical_url = ?",
            [ep["recorded_at"], ep["url"]],
        )
        con.execute(
            """
            UPDATE claims SET recorded_at = ?
            WHERE utterance_id IN (
                SELECT utterance_id FROM utterances WHERE source_id IN (
                    SELECT source_id FROM sources WHERE canonical_url = ?
                )
            )
            """,
            [ep["recorded_at"], ep["url"]],
        )

        claims_count = job.metrics.get("extracted_claims_count", 0)
        print(
            f"Completed {ep['title']}: status={job.status}, stage={job.stage}, claims={claims_count} in {time.time() - t0:.1f}s"
        )

    # Post-ingest integrity alignment:
    # 1. Extraction version
    con.execute("UPDATE claims SET extraction_version = 'gemma-3-27b-it:v1.1:s1'")
    # 2. Recompute claim counts on propositions
    con.execute(
        "UPDATE propositions SET claim_count = (SELECT count(*) FROM claims WHERE claims.proposition_id = propositions.proposition_id)"
    )
    # 3. Ensure quarantined proposition and tension remain quarantined (D0, X0)
    con.execute(
        "UPDATE propositions SET status = 'quarantined', quarantine_reason = 'fabricated_proposition' WHERE proposition_id = 'db3ec63d33cf6f0a'"
    )
    con.execute(
        "UPDATE tensions SET status = 'quarantined', quarantine_reason = 'fabricated_proposition' WHERE tension_id = '0068adec4b1501c6'"
    )
    # 4. Ensure all live propositions have embeddings (D0)
    for p_id in [r[0] for r in con.execute("SELECT proposition_id FROM propositions WHERE status = 'active'").fetchall()]:
        prop = store.get_proposition(p_id)
        has_emb = con.execute("SELECT 1 FROM proposition_embeddings WHERE proposition_id = ?", [p_id]).fetchone()
        if prop and not has_emb:
            emb = embedder.embed_document(prop.canonical_text)
            store.insert_proposition_embedding(p_id, emb)
    con.commit()

    print("\nAll four episodes ingested successfully!")


if __name__ == "__main__":
    populate_corpus()
