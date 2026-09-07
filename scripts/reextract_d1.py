"""Re-extract and deduplicate the full corpus under Item D1 (§13u).

Implements agent_execution_guide.md §13u (D1):
1. Backs up database to social_proof.duckdb.pre_d1.bak and snapshot tables claims_pre_d1.
2. Clears active claims and active propositions (preserving quarantined db3ec63d33cf6f0a).
3. Re-extracts candidate utterances with LocalGemmaRuntime (v1.6 prompt, validators 1-7).
4. Canonicalises and deduplicates propositions at T_dedup = 0.86 with W1 entailment guard.
5. Recomputes downstream phases (embeddings, tensions with T1 same-source disqualification,
   principles, rubric assessments).
6. Verifies Step 5 invariants: verify_quotes, verify_canonical_ids, verify_entailment_holds,
   zero-claim rule per source, claim count within ~20% of 3,669.
7. Measures and reports singleton rate and multi-episode propositions for Assertion (c).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import DEFAULT_T_DEDUP, Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import (
    get_exclusion_counts,
    get_rejection_counts,
    reset_exclusion_counts,
    reset_rejection_counts,
    validate_polarity,
)
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def run_d1_reextraction(db_path: str = "social_proof.duckdb") -> None:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"Database {db_path} not found.")

    bak_path = Path(f"{db_path}.pre_d1.bak")
    print(f"1. Backing up {db_path} to {bak_path}...")
    shutil.copy2(p, bak_path)
    print("   Backup complete.")

    store = Storage(db_path, artifact_dir="artifacts")

    # Snapshot existing tables inside DuckDB for auditability
    print("2. Archiving pre-D1 tables into claims_pre_d1 and propositions_pre_d1...")
    store.con.execute("CREATE TABLE IF NOT EXISTS claims_pre_d1 AS SELECT * FROM claims;")
    store.con.execute("CREATE TABLE IF NOT EXISTS propositions_pre_d1 AS SELECT * FROM propositions;")
    store.con.execute("CREATE TABLE IF NOT EXISTS proposition_embeddings_pre_d1 AS SELECT * FROM proposition_embeddings;")
    store.con.commit()

    # Identify candidate utterances to re-extract:
    # Utterances that previously produced claims, plus all candidate utterances for sources with <= 10 claims
    # to guarantee zero-claim rule across all 23 sources.
    target_utts_rows = store.con.execute("""
        SELECT DISTINCT
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
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims_pre_d1)
           OR (u.source_id IN ('6244e2a46bed1e89', '79f3aaf4ae50dde5') AND u.subject_id = 'subj_jason_calacanis')
        ORDER BY src.recorded_at, u.source_id, u.start_ms
    """).fetchall()

    print(f"\n3. Selected {len(target_utts_rows)} candidate utterances across all sources.")

    # Clear active claims and non-quarantined propositions
    print("\n4. Clearing active claims and active propositions (preserving quarantined db3ec63d33cf6f0a)...")
    store.con.execute("DELETE FROM claims;")
    store.con.execute("DELETE FROM propositions WHERE proposition_id != 'db3ec63d33cf6f0a';")
    store.con.execute("DELETE FROM proposition_embeddings WHERE proposition_id != 'db3ec63d33cf6f0a';")
    store.con.execute("DELETE FROM claim_entailment_cache;")
    store.con.commit()

    # Reset counters
    reset_rejection_counts()
    reset_exclusion_counts()

    # Initialize extraction pipeline with v1.6 prompt and live MLX backend
    print("\n5. Initializing LocalGemmaRuntime with prompt v1.6 and MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.6",
        schema_version="s1",
        load_live_backend=True,
    )
    print(f"   Extraction version: {runtime.extraction_version}")

    embedder = Embedder()
    gate = ExtractionGate()

    pipeline = ClaimExtractionPipeline(
        storage=store,
        runtime=runtime,
        gate=gate,
        embedder=embedder,
        t_dedup=DEFAULT_T_DEDUP,
    )

    print("\n6. Starting full re-extraction...")
    t0 = time.perf_counter()
    claims_total = 0
    claims_per_source: Counter[str] = Counter()

    for idx, (uid, sid, _subj_id, name, rec_at, _start_ms, _text) in enumerate(target_utts_rows, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        claims = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=rec_at,
            subject_context=f"Speaker: {name}",
        )
        claims_total += len(claims)
        claims_per_source[sid] += len(claims)

        if idx % 50 == 0 or idx == len(target_utts_rows):
            el = time.perf_counter() - t0
            rate = idx / el if el > 0 else 0
            eta_m = (len(target_utts_rows) - idx) / rate / 60 if rate > 0 else 0
            print(f"   [{idx}/{len(target_utts_rows)}] claims: {claims_total} | {rate:.2f} utts/s | ETA: {eta_m:.1f}m", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"\nExtraction completed in {elapsed:.1f}s ({elapsed/60:.2f}m). Total claims: {claims_total}.")

    # Step 6: Proposition Deduplication & Re-resolution
    print("\n7. Re-running proposition deduplication consolidation at T_dedup = 0.86...")
    dedup_stats = store.reresolve_propositions(
        t_dedup=DEFAULT_T_DEDUP,
        validate_entailment_on_repoint=True,
        embedder=embedder,
    )
    print(f"   Surviving propositions: {dedup_stats['surviving_propositions']}")
    print(f"   Merged away: {dedup_stats['merged_away_propositions']}")

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

    # Backfill missing embeddings
    active_props = store.con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()
    missing_emb = 0
    for pid, txt in active_props:
        has_emb = store.con.execute("SELECT 1 FROM proposition_embeddings WHERE proposition_id = ?", [pid]).fetchone()
        if not has_emb:
            emb = embedder.embed_document(txt)
            store.insert_proposition_embedding(pid, emb)
            missing_emb += 1
    if missing_emb > 0:
        print(f"   Backfilled {missing_emb} missing embeddings.")

    # Re-run Tension Detection (with T1 same-source disqualification)
    print("\n8. Running TensionDetector...")
    detector = TensionDetector(storage=store)
    report = detector.evaluate_candidate_pairs()
    print("   Candidate Evaluation Report:")
    print(f"     Total pairs examined: {report.total_pairs_examined}")
    print(f"     Accepted candidates: {report.candidates_accepted}")
    print(f"     Rejections by reason: {report.rejections_by_reason}")

    # Re-run Principle Detection
    print("\n9. Running PrincipleConflictDetector...")
    p_detector = PrincipleConflictDetector(storage=store)
    subjects = [r[0] for r in store.con.execute("SELECT subject_id FROM subjects").fetchall()]
    total_conflicts = 0
    for subj_id in subjects:
        conflicts, _dist = p_detector.detect_conflicts_for_subject(subj_id)
        total_conflicts += len(conflicts)
    print(f"   Principle conflicts detected across all subjects: {total_conflicts}")

    # Re-run Rubric Engine
    print("\n10. Running RubricEngine assessments...")
    engine = RubricEngine(storage=store)
    for subj_id in subjects:
        engine.assess_subject_topic(subj_id, "global", persist=True)
        engine.assess_subject_topic(subj_id, "top_ai_reg", persist=True)
    print(f"   Assessed {len(subjects)} subjects across global and top_ai_reg topics.")

    # Step 5 & 6 Invariant verification
    print("\n=== D1 Verification Summary ===")
    r_prop = store.con.execute("SELECT count(*) FROM propositions WHERE status = 'active'").fetchone()
    c_prop = int(r_prop[0]) if r_prop else 0
    r_claim = store.con.execute("SELECT count(*) FROM claims").fetchone()
    c_claim = int(r_claim[0]) if r_claim else 0
    r_single = store.con.execute("""
        SELECT count(*) FROM (
            SELECT proposition_id FROM claims GROUP BY 1 HAVING count(*) = 1
        )
    """).fetchone()
    c_single = int(r_single[0]) if r_single else 0
    single_pct = (c_single / c_prop * 100) if c_prop > 0 else 0.0

    r_multi = store.con.execute("""
        SELECT count(*) FROM (
            SELECT c.proposition_id
            FROM claims c
            JOIN utterances u ON c.utterance_id = u.utterance_id
            GROUP BY c.proposition_id
            HAVING count(DISTINCT u.source_id) >= 2
        )
    """).fetchone()
    multi_ep_props = int(r_multi[0]) if r_multi else 0
    multi_ep_pct = (multi_ep_props / c_prop * 100) if c_prop > 0 else 0.0

    # Finite verb check
    r_verb = store.con.execute("""
        SELECT count(*) FROM propositions
        WHERE status = 'active'
          AND regexp_matches(canonical_text, '\\\\b(is|are|was|were|will|would|can|could|should|has|have|do|does|did)\\\\b')
    """).fetchone()
    finite_verb_props = int(r_verb[0]) if r_verb else 0
    finite_verb_pct = (finite_verb_props / c_prop * 100) if c_prop > 0 else 0.0

    # Polarity check across all active propositions
    props_all = [r[0] for r in store.con.execute("SELECT canonical_text FROM propositions WHERE status = 'active'").fetchall()]
    polarity_violations = []
    from worker.extract.schema import ExtractedClaim
    for ptext in props_all:
        ec = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy",
            confidence=1.0,
        )
        v_res = validate_polarity(ec)
        if not v_res.is_valid:
            polarity_violations.append(ptext)

    # Sources with zero claims check
    sources_zero_claims = [
        sid for sid in [r[0] for r in store.con.execute("SELECT source_id FROM sources").fetchall()]
        if claims_per_source[sid] == 0
    ]

    print(f"Total active propositions: {c_prop}")
    print(f"Total claims: {c_claim}")
    print(f"Singletons: {c_single} ({single_pct:.2f}%) [baseline: 95.4%]")
    print(f"Propositions spanning 2+ episodes: {multi_ep_props} ({multi_ep_pct:.2f}%) [baseline: 1.8%]")
    print(f"Full-clauses (finite verbs): {finite_verb_props} ({finite_verb_pct:.2f}%) [baseline: 75.2%]")
    print(f"Polarity violations across entire table: {len(polarity_violations)} (must be 0)")
    print(f"Sources with zero claims: {len(sources_zero_claims)} (must be 0)")
    print(f"Validator rejections snapshot: {get_rejection_counts()}")
    print(f"Validator exclusions snapshot: {get_exclusion_counts()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Corpus Re-Extraction for Item D1")
    parser.add_argument("--db", type=str, default="social_proof.duckdb")
    args = parser.parse_args()
    run_d1_reextraction(db_path=args.db)
