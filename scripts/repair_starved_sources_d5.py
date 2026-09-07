"""Item D5 (§13x) Step 5: Repair starved sources by extracting host utterances omitted by D1."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import DEFAULT_T_DEDUP, Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.storage import Storage


def repair_starved_sources(db_path: str = "social_proof.duckdb") -> None:
    store = Storage(db_path, artifact_dir="artifacts")

    # The two starved sources that were omitted from D1 candidate expansion query
    starved_sids = ["79e5cda81c5740e9", "04ff0000906a6d10"]

    print("Loading candidate utterances for starved sources...")
    target_utts = store.con.execute("""
        SELECT
            u.utterance_id,
            u.source_id,
            u.subject_id,
            s.display_name,
            src.recorded_at,
            u.start_ms,
            u.text_verbatim
        FROM utterances u
        JOIN sources src ON u.source_id = src.source_id
        JOIN subjects s ON u.subject_id = s.subject_id
        WHERE u.source_id IN ('79e5cda81c5740e9', '04ff0000906a6d10')
          AND u.subject_id IS NOT NULL
        ORDER BY src.recorded_at, u.source_id, u.start_ms
    """).fetchall()

    print(f"Found {len(target_utts)} host utterances across starved sources.")

    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.6",
        schema_version="s1",
        load_live_backend=True,
    )
    embedder = Embedder()
    gate = ExtractionGate()

    pipeline = ClaimExtractionPipeline(
        storage=store,
        runtime=runtime,
        gate=gate,
        embedder=embedder,
        t_dedup=DEFAULT_T_DEDUP,
    )

    row_before = store.con.execute("SELECT count(*) FROM claims").fetchone()
    claims_before = int(row_before[0]) if row_before else 0
    print(f"Total claims in database BEFORE repair: {claims_before}")

    new_claims_count = 0
    for idx, (uid, _sid, _subj_id, name, rec_at, _start_ms, _text) in enumerate(target_utts, 1):
        # Check if this utterance already has claims in live table
        row_existing = store.con.execute("SELECT count(*) FROM claims WHERE utterance_id = ?", [uid]).fetchone()
        existing = int(row_existing[0]) if row_existing else 0
        if existing > 0:
            continue

        utt = store.get_utterance(uid)
        if not utt:
            continue

        claims = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=rec_at,
            subject_context=f"Speaker: {name}",
        )
        if claims:
            new_claims_count += len(claims)
            print(f"  [{idx}/{len(target_utts)}] Utterance {uid} produced {len(claims)} claims:")
            for c in claims:
                q_text = (c.quote_text or "")[:60]
                print(f"     - Prop: {c.proposition_id} | Quote: {q_text}")

    print(f"\nExtraction complete. Extracted {new_claims_count} new claims.")

    # Re-resolve and deduplicate propositions
    print("\nRe-resolving propositions with semantic deduplication at T_dedup = 0.86...")
    dedup_stats = store.reresolve_propositions(
        t_dedup=DEFAULT_T_DEDUP,
        validate_entailment_on_repoint=True,
        embedder=embedder,
    )
    print(f"  Dedup stats: {dedup_stats}")

    # Backfill missing embeddings for any newly created active propositions
    active_props = store.con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()
    missing_emb = 0
    for pid, txt in active_props:
        has_emb = store.con.execute("SELECT 1 FROM proposition_embeddings WHERE proposition_id = ?", [pid]).fetchone()
        if not has_emb:
            emb = embedder.embed_document(txt)
            store.insert_proposition_embedding(pid, emb)
            missing_emb += 1
    if missing_emb > 0:
        print(f"  Backfilled {missing_emb} missing proposition embeddings.")

    # Recompute claim counts on propositions
    store.con.execute("""
        UPDATE propositions
        SET claim_count = (
            SELECT count(*)
            FROM claims
            WHERE claims.proposition_id = propositions.proposition_id
        )
    """)
    store.con.commit()

    row_after = store.con.execute("SELECT count(*) FROM claims").fetchone()
    claims_after = int(row_after[0]) if row_after else 0
    row_props = store.con.execute("SELECT count(*) FROM propositions WHERE status = 'active'").fetchone()
    props_after = int(row_props[0]) if row_props else 0
    print(f"\nTotal claims AFTER repair: {claims_after} (net change: +{claims_after - claims_before})")
    print(f"Total active propositions AFTER repair: {props_after}")

    # Display new claims per hour for starved sources
    print("\nUpdated rates for starved sources:")
    for sid in starved_sids:
        r = store.con.execute("""
            SELECT s.title, s.duration_ms / 1000.0 / 3600.0, count(c.claim_id)
            FROM sources s
            LEFT JOIN utterances u ON s.source_id = u.source_id
            LEFT JOIN claims c ON u.utterance_id = c.utterance_id
            WHERE s.source_id = ?
            GROUP BY s.source_id, s.title, s.duration_ms
        """, [sid]).fetchone()
        if r is not None:
            rate = float(r[2]) / float(r[1]) if r[1] and float(r[1]) > 0 else 0.0
            print(f"  '{r[0]}' ({sid}): {r[2]} claims in {r[1]:.2f}h ({rate:.2f} claims/hr)")


if __name__ == "__main__":
    repair_starved_sources()
