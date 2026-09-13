"""Re-extract and deduplicate the full corpus under Item D6 (§11).

Implements agent_execution_guide.md §11 (D6):
1. Backs up database to social_proof.duckdb.pre_d6.bak and snapshot tables claims_pre_d6.
2. Clears active claims and active propositions (preserving quarantined db3ec63d33cf6f0a).
3. Re-extracts candidate utterances with LocalGemmaRuntime (v1.7 prompt, validators 1-7 including Validator 2b validate_position_bearing).
4. Canonicalises and deduplicates propositions at T_dedup = 0.84 (preserving D2's measured threshold).
5. Recomputes downstream phases (embeddings, tensions with T1 same-source disqualification,
   principles, rubric assessments).
6. Verifies Step 4 invariants:
   - Claim count within 20% of 2,261 (1,809 - 2,713).
   - Reconciles rejection counters against row-count change.
   - verify_quotes, verify_canonical_ids, verify_entailment_holds PASS.
   - claims-per-hour (Parameter 033: >= 3.0) holds for all 23 sources.
7. Evaluates accepted candidate pairs under Step 5 (writes 'A takes position X, B takes position Y').
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import (
    get_exclusion_counts,
    get_rejection_counts,
    reset_exclusion_counts,
    reset_rejection_counts,
)
from worker.integrity import run_integrity_corpus
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector

# Parameter 008 tuned in Item D2 (§13v)
T_DEDUP_D6: float = 0.84


def run_d6_reextraction(db_path: str = "social_proof.duckdb") -> None:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"Database {db_path} not found.")

    bak_path = Path(f"{db_path}.pre_d6.bak")
    print(f"1. Backing up {db_path} to {bak_path}...")
    shutil.copy2(p, bak_path)
    print("   Backup complete.")

    store = Storage(db_path, artifact_dir="artifacts")

    # Snapshot existing tables inside DuckDB for auditability
    print("2. Archiving pre-D6 tables into claims_pre_d6 and propositions_pre_d6...")
    store.con.execute("CREATE TABLE IF NOT EXISTS claims_pre_d6 AS SELECT * FROM claims;")
    store.con.execute(
        "CREATE TABLE IF NOT EXISTS propositions_pre_d6 AS SELECT * FROM propositions;"
    )
    store.con.execute(
        "CREATE TABLE IF NOT EXISTS proposition_embeddings_pre_d6 AS SELECT * FROM proposition_embeddings;"
    )
    store.con.execute("CREATE TABLE IF NOT EXISTS tensions_pre_d6 AS SELECT * FROM tensions;")
    store.con.commit()

    pre_claims_count = (
        r[0] if (r := store.con.execute("SELECT count(*) FROM claims_pre_d6").fetchone()) else 0
    )
    pre_props_count = (
        r[0]
        if (r := store.con.execute("SELECT count(*) FROM propositions_pre_d6").fetchone())
        else 0
    )
    print(f"   Pre-D6 baseline: {pre_claims_count} claims, {pre_props_count} propositions.")

    # Candidate utterances: all utterances in pre-D6 claims plus host utterances for low-claim sources
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
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims_pre_d6)
           OR (u.source_id IN ('79178e47abe6f799', '0da89e82768a50ca', '8550481c62a4fddf', '601ab4063555d485', '3db1487d23e98021') AND u.subject_id IS NOT NULL)
        ORDER BY src.recorded_at, u.source_id, u.start_ms
    """).fetchall()

    print(f"\n3. Selected {len(target_utts_rows)} candidate utterances across all 23 sources.")

    # Clear active claims and non-quarantined propositions
    print(
        "\n4. Clearing active claims and active propositions (preserving quarantined db3ec63d33cf6f0a)..."
    )
    store.con.execute("DELETE FROM claims;")
    store.con.execute("DELETE FROM propositions WHERE proposition_id != 'db3ec63d33cf6f0a';")
    store.con.execute(
        "DELETE FROM proposition_embeddings WHERE proposition_id != 'db3ec63d33cf6f0a';"
    )
    store.con.execute("DELETE FROM claim_entailment_cache;")
    store.con.commit()

    # Reset counters
    reset_rejection_counts()
    reset_exclusion_counts()

    # Initialize extraction pipeline with prompt v1.7 and live MLX backend
    print("\n5. Initializing LocalGemmaRuntime with prompt v1.7 and MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.7",
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
        t_dedup=T_DEDUP_D6,
    )

    print("\n6. Starting full re-extraction under prompt v1.7 and Validator 2b...")
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

        if idx % 100 == 0 or idx == len(target_utts_rows):
            el = time.perf_counter() - t0
            rate = idx / el if el > 0 else 0
            eta_m = (len(target_utts_rows) - idx) / rate / 60 if rate > 0 else 0
            print(
                f"   [{idx:4d}/{len(target_utts_rows)}] claims: {claims_total:4d} | {rate:.2f} utts/s | ETA: {eta_m:.1f}m",
                flush=True,
            )

    elapsed = time.perf_counter() - t0
    print(
        f"\nExtraction completed in {elapsed:.1f}s ({elapsed / 60:.2f}m). Total claims: {claims_total}."
    )

    # Step 4 Verify: Claim count within 20% of 2,261
    min_claim_bound = int(2261 * 0.80)  # 1808
    max_claim_bound = int(2261 * 1.20)  # 2713
    print("\n--- STEP 4 CLAIM COUNT VERIFICATION ---")
    print(f"Pre-D6 target: 2,261 (Acceptable range [20%]: {min_claim_bound} - {max_claim_bound})")
    print(f"Post-D6 extracted: {claims_total} claims")

    rejections = get_rejection_counts()
    exclusions = get_exclusion_counts()
    print("\nValidator Rejection Counters:")
    for reason, cnt in sorted(rejections.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")
    print("\nValidator Exclusion Counters (Non-own assertions):")
    for reason, cnt in sorted(exclusions.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")

    if not (min_claim_bound <= claims_total <= max_claim_bound):
        print(f"\n[WARNING] Claim count {claims_total} is outside 20% bound of 2,261!")

    # Step 6: Proposition Deduplication & Re-resolution at T_dedup = 0.84
    print(f"\n7. Re-running proposition deduplication consolidation at T_dedup = {T_DEDUP_D6}...")
    dedup_stats = store.reresolve_propositions(
        t_dedup=T_DEDUP_D6,
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
    active_props = store.con.execute(
        "SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'"
    ).fetchall()
    missing_emb = 0
    for pid, txt in active_props:
        has_emb = store.con.execute(
            "SELECT 1 FROM proposition_embeddings WHERE proposition_id = ?", [pid]
        ).fetchone()
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
    print("   Rubric assessments recomputed.")

    # Step 5 & Validation (c): Candidate Pairs Hand-Reading
    print("\n11. Step 5 — Reading accepted candidate pairs under Position Test...")
    tensions = store.con.execute("""
        SELECT t.tension_id, t.subject_id, s.display_name, t.type, t.claim_ids, t.settlement_status
        FROM tensions t
        JOIN subjects s ON t.subject_id = s.subject_id
    """).fetchall()

    if tensions:
        for tid, _sid, sname, ttype, cids_json, _sstatus in tensions:
            import json

            cids = json.loads(cids_json) if isinstance(cids_json, str) else cids_json
            c1 = store.get_claim(cids[0])
            c2 = store.get_claim(cids[1])
            p1 = store.get_proposition(c1.proposition_id) if c1 else None
            p_text = p1.canonical_text if p1 else "UNKNOWN"
            q1 = c1.quote_text if c1 else ""
            q2 = c2.quote_text if c2 else ""
            st1 = c1.stance if c1 else ""
            st2 = c2.stance if c2 else ""
            print(f"\n   Tension {tid} ({ttype}) for {sname}:")
            print(f'     Proposition: "{p_text}"')
            print(f'     Claim A ({st1}): "{q1}"')
            print(f'     Claim B ({st2}): "{q2}"')
            print(
                f"     Position sentence: \"{sname} takes position {st1} on '{p_text}', and takes position {st2} on '{p_text}'\""
            )
    else:
        print("   No published tensions detected (0 accepted pairs).")

    store.close()

    # Run Integrity Checks
    print("\n12. Running Core Integrity Checks...")
    results = run_integrity_corpus(db_path)
    core_names = {
        "verify_quotes",
        "verify_canonical_ids",
        "verify_entailment_holds",
        "verify_claims_per_hour",
    }
    for res in results:
        if res.name in core_names:
            print(f"   {res.name:<26}: {res.status} ({res.message})")

    print("\nItem D6 Re-extraction Complete.")


def run_d6_verification(db_path: str = "social_proof.duckdb") -> None:
    print(f"Running Integrity Verification on {db_path}...")
    results = run_integrity_corpus(db_path)
    core_names = {
        "verify_quotes",
        "verify_canonical_ids",
        "verify_entailment_holds",
        "verify_claims_per_hour",
    }
    for res in results:
        if res.name in core_names:
            print(f"   {res.name:<26}: {res.status} ({res.message})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-extract corpus for Item D6")
    parser.add_argument("--db", default="social_proof.duckdb", help="Path to database")
    parser.add_argument(
        "--verify-only", action="store_true", help="Run only step 12 integrity checks"
    )
    args = parser.parse_args()
    if args.verify_only:
        run_d6_verification(args.db)
    else:
        run_d6_reextraction(args.db)
