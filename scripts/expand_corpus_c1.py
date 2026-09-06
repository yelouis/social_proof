"""Expand the corpus chronologically under Issue 030 = A for Item C1 (§17s).

Pre-registered Selection Rule:
- 20 most recent contiguous episodes from All-In podcast feed (https://allinchamathjason.libsyn.com/rss)
- Spanning 2026-07-03T22:12:00+00:00 (E279) through 2026-09-04T23:10:00+00:00 (E288).
- Every episode in this range is ingested without exception.

Implements:
1. Audio ingest (fetch, Whisper transcribe, sentence-bounded segment, attribution).
2. Role enrolment using compute_role_id (4 hosts per source).
3. Audio disposal immediately upon non-empty utterance creation.
4. Claim extraction with LocalGemmaRuntime (v1.5 prompt, validators 1-7).
5. Proposition deduplication (T_dedup = 0.86 with W1 entailment guard).
6. Tension detection with T1 same-source disqualification and candidate reporting.
7. P5 principles & P6 rubric assessments.
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.request
from collections import Counter
from typing import Any

from worker.adapters.base import SourceRef
from worker.adapters.podcast import PodcastRSSAdapter
from worker.diarize.attribution import SpeakerAttributor
from worker.diarize.enrollment import VoiceEnrollmentStore
from worker.entities import Source, SourceSubjectRole, Subject, Utterance
from worker.extract.dedup import DEFAULT_T_DEDUP, Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.ingest import IngestionEngine
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import (
    Storage,
    compute_role_id,
    compute_source_id,
)
from worker.tension.detect import TensionDetector

ALL_IN_RSS_URL = "https://allinchamathjason.libsyn.com/rss"


def fetch_20_contiguous_episodes() -> list[dict[str, Any]]:
    """Fetches the 20 most recent contiguous episodes from the feed, oldest to newest."""
    req = urllib.request.Request(ALL_IN_RSS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()

    adapter = PodcastRSSAdapter()
    raw_episodes = adapter.parse_feed_xml(content)
    recent_20 = raw_episodes[:20]

    episodes: list[dict[str, Any]] = []
    for ep in reversed(recent_20):
        raw_url = ep["enclosure_url"]
        # Normalize to direct libsyn URL by stripping tracking prefixes and query strings
        m = re.search(r"traffic\.libsyn\.com/([^?]+)", raw_url)
        clean_url = f"https://traffic.libsyn.com/{m.group(1)}" if m else raw_url.split("?")[0]
        sid = compute_source_id(clean_url)
        episodes.append({
            "source_id": sid,
            "title": ep["title"],
            "pub_date": ep["pub_date"],
            "duration_ms": ep["duration_ms"],
            "url": clean_url,
            "raw_url": raw_url,
        })

    return episodes


def ingest_episode(
    ep: dict[str, Any],
    store: Storage,
    engine: IngestionEngine,
    adapter: PodcastRSSAdapter,
    subjects: list[Subject],
) -> tuple[Source, list[Utterance], float]:
    """Ingests a single episode with audio deletion and role enrolment."""
    sid = ep["source_id"]
    t0 = time.perf_counter()

    # Check if already ingested with audio deleted
    existing_src = store.get_source(sid)
    if existing_src is not None and existing_src.audio_deleted_at is not None:
        utts = [
            u for (uid,) in store.con.execute(
                "SELECT utterance_id FROM utterances WHERE source_id = ?", [sid]
            ).fetchall()
            if (u := store.get_utterance(uid)) is not None
        ]
        print(f"  [Idempotent Skip] {ep['title'][:50]} already ingested ({len(utts)} utterances).")
        return existing_src, utts, 0.0

    print(f"\n--- Ingesting {ep['title']} ---")
    print(f"  Duration: {ep['duration_ms'] / 60000:.1f} min | Published: {ep['pub_date']}")
    print(f"  URL: {ep['url']}")

    ref = SourceRef(
        locator=ep["url"],
        tier="B",
        title=ep["title"],
        extra={
            "duration_ms": ep["duration_ms"],
            "published_at": ep["pub_date"],
            "recorded_at": ep["pub_date"],
        },
    )

    # Use ingest_panel_source with mock_claims skipping to decouple audio ingest from extraction
    job = engine.ingest_panel_source(
        adapter=adapter,
        ref=ref,
        subjects=subjects,
        mock_claims_by_subject=lambda _s, _u: [],
    )

    if job.status != "completed":
        raise RuntimeError(f"Ingest failed for {ep['title']}: {job.errors}")

    elapsed = time.perf_counter() - t0
    source = store.get_source(sid)
    assert source is not None, f"Source {sid} not found after ingest"

    utts = [
        u for (uid,) in store.con.execute(
            "SELECT utterance_id FROM utterances WHERE source_id = ?", [sid]
        ).fetchall()
        if (u := store.get_utterance(uid)) is not None
    ]

    print(f"  Completed audio ingest in {elapsed:.1f}s ({elapsed/60:.2f}m): {len(utts)} utterances.")

    # Enforce role enrolment for all 4 hosts (Trap 40: compute_role_id)
    for subj in subjects:
        r_id = compute_role_id(sid, subj.subject_id)
        role = SourceSubjectRole(
            role_id=r_id,
            source_id=sid,
            subject_id=subj.subject_id,
            tier="B",
            venue_type="own_channel",
            audience_stance="friendly",
            is_adversarial=False,
        )
        store.insert_source_role(role)

    return source, utts, elapsed


def extract_claims_for_source(
    source: Source,
    store: Storage,
    pipeline: ClaimExtractionPipeline,
) -> tuple[int, float]:
    """Extracts claims from high-confidence utterances of enrolled subjects."""
    t0 = time.perf_counter()
    utts = store.con.execute("""
        SELECT utterance_id, subject_id, text_verbatim
        FROM utterances
        WHERE source_id = ? AND subject_id LIKE 'subj_%' AND attribution_confidence = 'high'
        ORDER BY start_ms
    """, [source.source_id]).fetchall()

    print(f"  Extracting claims from {len(utts)} high-confidence candidate utterances...")
    claims_count = 0
    for idx, (uid, subj_id, _text) in enumerate(utts, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        subj = store.get_subject(subj_id)
        subj_name = subj.display_name if subj else subj_id

        claims = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=source.recorded_at,
            subject_context=f"Speaker: {subj_name}",
        )
        claims_count += len(claims)

        if idx % 50 == 0 or idx == len(utts):
            el = time.perf_counter() - t0
            print(f"    [{idx}/{len(utts)}] claims extracted: {claims_count} | {idx/el:.1f} utts/s")

    elapsed = time.perf_counter() - t0
    print(f"  Extraction for {source.source_id} finished in {elapsed:.1f}s ({elapsed/60:.2f}m): {claims_count} claims.")
    return claims_count, elapsed


def recompute_downstream(store: Storage) -> None:
    """Recomputes proposition counts, embeddings, tensions, principles, and rubric assessments."""
    print("\n=== Recomputing Downstream Phases ===")

    # 1. Recompute claim counts on propositions
    store.con.execute("""
        UPDATE propositions
        SET claim_count = (
            SELECT count(*)
            FROM claims
            WHERE claims.proposition_id = propositions.proposition_id
        )
    """)
    store.con.commit()

    # 2. Backfill embeddings for any active proposition missing one
    embedder = Embedder()
    active_props = store.con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()
    missing_emb = 0
    for pid, txt in active_props:
        has_emb = store.con.execute("SELECT 1 FROM proposition_embeddings WHERE proposition_id = ?", [pid]).fetchone()
        if not has_emb:
            emb = embedder.embed_document(txt)
            store.insert_proposition_embedding(pid, emb)
            missing_emb += 1
    if missing_emb > 0:
        print(f"  Backfilled {missing_emb} proposition embeddings.")

    # 3. Re-run Tension Detection (with same-source disqualification)
    print("  Running TensionDetector...")
    detector = TensionDetector(storage=store)
    report = detector.evaluate_candidate_pairs()
    print("  Candidate Evaluation Report:")
    print(f"    Total pairs examined: {report.total_pairs_examined}")
    print(f"    Accepted candidates: {report.candidates_accepted}")
    print(f"    Rejections by reason: {report.rejections_by_reason}")

    if report.candidates_accepted > 0:
        print("\n  *** ACCEPTED CANDIDATE REVERSAL PAIRS (FOR HAND REVIEW) ***")
        for tension in report.accepted_tensions:
            c_a = store.get_claim(tension.claim_a_id)
            c_b = store.get_claim(tension.claim_b_id)
            prop = store.get_proposition(tension.proposition_id) if tension.proposition_id else None
            subj = c_a.subject_id if c_a else "unknown"
            st_a = c_a.stance if c_a else "unknown"
            st_b = c_b.stance if c_b else "unknown"
            print(f"    Tension ID: {tension.tension_id}")
            print(f"      Subject: {subj}")
            print(f"      Proposition ID: {tension.proposition_id}")
            print(f"      Proposition Text: {prop.canonical_text if prop else '???'}")
            print(f"      Claim A ({tension.claim_a_id}): {st_a}")
            print(f"      Claim B ({tension.claim_b_id}): {st_b}")
            print(f"      Severity: {tension.severity}")

    # 4. Re-run Principle Detection
    print("  Running PrincipleConflictDetector...")
    p_detector = PrincipleConflictDetector(storage=store)
    subjects = [r[0] for r in store.con.execute("SELECT subject_id FROM subjects").fetchall()]
    total_conflicts = 0
    for subj_id in subjects:
        conflicts, _dist = p_detector.detect_conflicts_for_subject(subj_id)
        total_conflicts += len(conflicts)
    print(f"    Principle conflicts detected across all subjects: {total_conflicts}")

    # 5. Re-run Rubric Engine
    print("  Running RubricEngine...")
    engine = RubricEngine(storage=store)
    for subj_id in subjects:
        engine.assess_subject_topic(subj_id, "global", persist=True)
        engine.assess_subject_topic(subj_id, "top_ai_reg", persist=True)
    print(f"    Assessed {len(subjects)} subjects across global and top_ai_reg topics.")


def report_corpus_metrics(store: Storage) -> None:
    """Prints merge histogram, multi-episode propositions, and composition skew."""
    print("\n=== Corpus Metrics & Composition Report ===")

    # Total sources, utterances, claims, propositions
    r_src = store.con.execute("SELECT count(*) FROM sources").fetchone()
    src_cnt = r_src[0] if r_src else 0
    r_utt = store.con.execute("SELECT count(*) FROM utterances").fetchone()
    utt_cnt = r_utt[0] if r_utt else 0
    r_clm = store.con.execute("SELECT count(*) FROM claims").fetchone()
    claim_cnt = r_clm[0] if r_clm else 0
    r_prp = store.con.execute("SELECT count(*) FROM propositions WHERE status = 'active'").fetchone()
    prop_cnt = r_prp[0] if r_prp else 0
    r_rol = store.con.execute("SELECT count(*) FROM source_roles").fetchone()
    role_cnt = r_rol[0] if r_rol else 0

    print(f"Sources: {src_cnt}")
    print(f"SourceSubjectRoles: {role_cnt}")
    print(f"Utterances: {utt_cnt}")
    print(f"Claims: {claim_cnt}")
    print(f"Active Propositions: {prop_cnt}")

    # Multi-episode propositions
    multi_ep_props = store.con.execute("""
        SELECT c.proposition_id, count(DISTINCT u.source_id) as ep_count
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        GROUP BY c.proposition_id
        HAVING count(DISTINCT u.source_id) >= 2
        ORDER BY ep_count DESC
    """).fetchall()

    print(f"\nMulti-episode propositions (>= 2 episodes): {len(multi_ep_props)}")
    for pid, ep_c in multi_ep_props[:15]:
        p = store.get_proposition(pid)
        txt = p.canonical_text if p else "???"
        print(f"  - [{ep_c} eps] {pid}: {txt[:80]}...")

    # Merge histogram
    counts_dist: Counter[int] = Counter()
    all_ep_counts = store.con.execute("""
        SELECT count(DISTINCT u.source_id)
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        GROUP BY c.proposition_id
    """).fetchall()
    for (c,) in all_ep_counts:
        counts_dist[c] += 1

    print("\nEpisode Overlap Histogram:")
    for num_eps in sorted(counts_dist.keys()):
        print(f"  Appearing in {num_eps} episode(s): {counts_dist[num_eps]} propositions")

    # Composition skew declaration (Trap 24)
    print("\nComposition Skew Notice (Trap 24):")
    print("  Corpus medium: 100% podcast audio (Tier B own_channel).")
    print("  Corpus publisher: 100% All-In Podcast.")
    print("  Enlarging the corpus does not fix cross-medium or cross-venue composition skew.")


def run_expansion(limit: int | None = None, db_path: str = "social_proof.duckdb") -> None:
    """Executes chronological corpus expansion."""
    store = Storage(db_path, artifact_dir="artifacts")
    enroll_store = VoiceEnrollmentStore()
    attributor = SpeakerAttributor(t_high=0.70, t_low=0.50)
    embedder = Embedder()
    gate = ExtractionGate()

    engine = IngestionEngine(
        storage=store,
        enrollment_store=enroll_store,
        attributor=attributor,
        embedder=embedder,
    )
    adapter = PodcastRSSAdapter()

    # Load subjects
    subj_rows = store.con.execute("SELECT subject_id, display_name, enrollment_ref FROM subjects").fetchall()
    subjects = [Subject(subject_id=r[0], display_name=r[1], enrollment_ref=r[2]) for r in subj_rows]

    # Initialize live extraction pipeline
    print("Loading LocalGemmaRuntime with live MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.5",
        schema_version="s1",
        load_live_backend=True,
    )
    pipeline = ClaimExtractionPipeline(
        storage=store,
        runtime=runtime,
        gate=gate,
        embedder=embedder,
        t_dedup=DEFAULT_T_DEDUP,
    )

    all_20_episodes = fetch_20_contiguous_episodes()
    print(f"Fetched {len(all_20_episodes)} contiguous episodes from RSS feed.")

    target_episodes = all_20_episodes
    if limit is not None and limit > 0:
        # Process the N newest episodes
        target_episodes = all_20_episodes[-limit:]

    print(f"Processing {len(target_episodes)} target episodes...")

    total_ingest_time = 0.0
    total_extract_time = 0.0

    for ep in target_episodes:
        # 1. Ingest audio & enrol roles
        source, utts, t_ingest = ingest_episode(
            ep=ep,
            store=store,
            engine=engine,
            adapter=adapter,
            subjects=subjects,
        )
        total_ingest_time += t_ingest

        # 2. Extract claims if source has no claims yet
        claim_count_row = store.con.execute("""
            SELECT count(*)
            FROM claims c
            JOIN utterances u ON c.utterance_id = u.utterance_id
            WHERE u.source_id = ?
        """, [source.source_id]).fetchone()
        existing_claims = claim_count_row[0] if claim_count_row else 0

        if existing_claims == 0:
            new_claims, t_ext = extract_claims_for_source(
                source=source,
                store=store,
                pipeline=pipeline,
            )
            total_extract_time += t_ext
            if new_claims == 0:
                print(f"  WARNING: Source {source.source_id} yielded 0 claims!")
        else:
            print(f"  [Skip Extraction] Source {source.source_id} already has {existing_claims} claims.")

    print(f"\nTotal audio ingest time: {total_ingest_time:.1f}s ({total_ingest_time/60:.2f}m)")
    print(f"Total claim extraction time: {total_extract_time:.1f}s ({total_extract_time/60:.2f}m)")

    # 3. Recompute downstream layers
    recompute_downstream(store)

    # 4. Report corpus metrics
    report_corpus_metrics(store)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chronological Corpus Expansion (Item C1)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of episodes to process")
    parser.add_argument("--db", type=str, default="social_proof.duckdb", help="Path to DuckDB database")
    args = parser.parse_args()

    run_expansion(limit=args.limit, db_path=args.db)
