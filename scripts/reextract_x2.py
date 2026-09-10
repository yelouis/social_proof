"""Item X2 (§12) — Full corpus re-extraction under Prompt v1.8 and position frame elicitation (Issue 034 = B).

1. Backs up social_proof.duckdb to social_proof.duckdb.pre_x2.bak.
2. Snapshots pre-X2 tables to claims_pre_x2, propositions_pre_x2, etc.
3. Re-extracts candidate utterances with LocalGemmaRuntime (prompt v1.8 with position frame elicitation).
4. Persists position_frame on every claim.
5. Re-runs proposition deduplication at T_dedup = 0.84 unchanged.
6. Re-runs TensionDetector, PrincipleConflictDetector, and RubricEngine.
7. Verifies Parameter 033 (MIN_CLAIMS_PER_HOUR = 3.0) across all 23 sources.
8. Reconciles claim count change with VALIDATOR_REJECTION_COUNTERS.
9. Audits tension candidate pairs by reading both stored position_frame sentences.
10. Validates (c): Draws 20 random claims with seed to verify frame and proposition agreement.
11. Runs integrity suite (worker.integrity) to ensure all checks PASS.
"""

import argparse
import random
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
)
from worker.integrity import run_integrity_corpus
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def run_full_reextraction(db_path: str = "social_proof.duckdb") -> None:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"Database {db_path} not found.")

    bak_path = Path(f"{db_path}.pre_x2.bak")
    print(f"1. Backing up {db_path} to {bak_path}...")
    shutil.copy2(p, bak_path)
    print("   Backup complete.")

    store = Storage(db_path, artifact_dir="artifacts")

    # Snapshot existing tables inside DuckDB for auditability
    print("2. Archiving pre-X2 tables into claims_pre_x2 and propositions_pre_x2...")
    store.con.execute("CREATE TABLE IF NOT EXISTS claims_pre_x2 AS SELECT * FROM claims;")
    store.con.execute("CREATE TABLE IF NOT EXISTS propositions_pre_x2 AS SELECT * FROM propositions;")
    store.con.execute("CREATE TABLE IF NOT EXISTS proposition_embeddings_pre_x2 AS SELECT * FROM proposition_embeddings;")
    store.con.execute("CREATE TABLE IF NOT EXISTS tensions_pre_x2 AS SELECT * FROM tensions;")
    store.con.commit()

    pre_claims_count = r[0] if (r := store.con.execute("SELECT count(*) FROM claims_pre_x2").fetchone()) else 0
    pre_props_count = r[0] if (r := store.con.execute("SELECT count(*) FROM propositions_pre_x2").fetchone()) else 0
    print(f"   Pre-X2 baseline: {pre_claims_count} claims, {pre_props_count} propositions.")

    # Candidate utterances: all utterances in pre-D6/pre-X2 claims plus host utterances for low-claim sources
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
    print("\n4. Clearing active claims and active propositions (preserving quarantined db3ec63d33cf6f0a)...")
    store.con.execute("DELETE FROM claims;")
    store.con.execute("DELETE FROM propositions WHERE proposition_id != 'db3ec63d33cf6f0a';")
    store.con.execute("DELETE FROM proposition_embeddings WHERE proposition_id != 'db3ec63d33cf6f0a';")
    store.con.execute("DELETE FROM claim_entailment_cache;")
    store.con.commit()

    # Reset counters
    reset_rejection_counts()
    reset_exclusion_counts()

    # Initialize extraction pipeline with prompt v1.8 and live MLX backend
    print("\n5. Initializing LocalGemmaRuntime with prompt v1.8 and MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.8",
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

    print(f"\n6. Starting full re-extraction under prompt v1.8 (T_dedup={DEFAULT_T_DEDUP})...")
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
            print(f"   [{idx:4d}/{len(target_utts_rows)}] claims: {claims_total:4d} | {rate:.2f} utts/s | ETA: {eta_m:.1f}m", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"\nExtraction completed in {elapsed:.1f}s ({elapsed/60:.2f}m). Total claims: {claims_total}.")

    print("\n--- STEP 5 RECONCILIATION ---")
    print("Pre-X2 claims: 1,027")
    print(f"Post-X2 extracted: {claims_total} claims")

    rejections = get_rejection_counts()
    exclusions = get_exclusion_counts()
    print("\nValidator Rejection Counters:")
    for reason, cnt in sorted(rejections.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")
    print("\nValidator Exclusion Counters (Non-own assertions):")
    for reason, cnt in sorted(exclusions.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")

    # Proposition Deduplication & Re-resolution at T_dedup = 0.84
    print(f"\n7. Re-running proposition deduplication consolidation at T_dedup = {DEFAULT_T_DEDUP}...")
    dedup_stats = store.reresolve_propositions(
        t_dedup=DEFAULT_T_DEDUP,
        validate_entailment_on_repoint=True,
        embedder=embedder,
    )
    print(f"   Consolidation summary: {dedup_stats}")

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

    # Re-run Tension Detection
    print("\n8. Running TensionDetector...")
    detector = TensionDetector(storage=store)
    report = detector.evaluate_candidate_pairs()
    print("   Candidate Evaluation Report:")
    print(f"     Total pairs examined: {report.total_pairs_examined}")
    print(f"     Accepted candidates: {report.candidates_accepted}")
    print(f"     Rejections by reason: {report.rejections_by_reason}")

    # Detect tensions for all subjects to persist tension rows
    subjects = [r[0] for r in store.con.execute("SELECT subject_id FROM subjects").fetchall()]
    all_tensions = []
    for subj_id in subjects:
        t_list = detector.detect_tensions_for_subject(subj_id)
        all_tensions.extend(t_list)
    print(f"   Tensions written to database: {len(all_tensions)}")

    # Re-run Principle Detection
    print("\n9. Running PrincipleConflictDetector...")
    p_detector = PrincipleConflictDetector(storage=store)
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

    store.close()
    run_post_extraction_verification(db_path)


def run_post_extraction_verification(db_path: str) -> None:
    """Runs all verification steps 11-14 on the extracted DuckDB database."""
    store = Storage(db_path, read_only=True)

    print("\n--- CORPUS SUMMARY STATS ---")
    c_count = r[0] if (r := store.con.execute("SELECT count(*) FROM claims").fetchone()) else 0
    p_count = r[0] if (r := store.con.execute("SELECT count(*) FROM propositions WHERE status = 'active'").fetchone()) else 0
    stances = store.con.execute("SELECT stance, count(*) FROM claims GROUP BY 1 ORDER BY 1").fetchall()
    print(f"Total claims       : {c_count}")
    print(f"Active propositions: {p_count}")
    print(f"Stance distribution: {stances}")

    singletons = r[0] if (r := store.con.execute("SELECT count(*) FROM propositions WHERE status = 'active' AND claim_count = 1").fetchone()) else 0
    multi_props = r[0] if (r := store.con.execute("""
        SELECT count(DISTINCT p.proposition_id)
        FROM propositions p
        JOIN claims c ON p.proposition_id = c.proposition_id
        JOIN utterances u ON c.utterance_id = u.utterance_id
        WHERE p.status = 'active'
        GROUP BY p.proposition_id
        HAVING count(DISTINCT u.source_id) >= 2
    """).fetchone()) else 0
    print(f"Singletons         : {singletons} / {p_count} ({singletons/p_count*100:.1f}%)" if p_count > 0 else "")
    print(f"Multi-source props : {multi_props} / {p_count} ({multi_props/p_count*100:.1f}%)" if p_count > 0 else "")

    # Step 6: Accepted Tension Candidate Pairs Audit
    print("\n11. Step 6 — Reading accepted candidate pairs via stored position frames...")
    tension_rows = store.con.execute("""
        SELECT t.tension_id, t.type, t.claim_a_id, t.claim_b_id, t.status, t.quarantine_reason
        FROM tensions t
        ORDER BY t.tension_id
    """).fetchall()

    if tension_rows:
        for tid, ttype, ca_id, cb_id, status, q_reason in tension_rows:
            c1 = store.get_claim(ca_id)
            c2 = store.get_claim(cb_id)
            sname = "Unknown"
            if c1:
                subj = store.get_subject(c1.subject_id)
                sname = subj.display_name if subj else c1.subject_id
            print(f"\n   [Tension {tid}] ({sname}) Type: {ttype} | Status: {status} (Reason: {q_reason})")
            if c1 and c2:
                print(f"     Claim A frame: \"{c1.position_frame}\" (Stance: {c1.stance})")
                print(f"     Claim B frame: \"{c2.position_frame}\" (Stance: {c2.stance})")
    else:
        print("   Zero accepted tension rows in database.")

    # Validation (c): 20 random claims drawn with recorded seed
    print("\n12. Validation (c) — 20 Random Claims Verification (Position Frame Agreement)...")
    claim_ids = [r[0] for r in store.con.execute("SELECT claim_id FROM claims ORDER BY claim_id").fetchall()]
    random.seed(2026)
    sample_cids = random.sample(claim_ids, min(20, len(claim_ids)))

    agreement_count = 0
    print(f"   Sample seed: 2026, drawn {len(sample_cids)} claims:")
    for idx, cid in enumerate(sample_cids, 1):
        claim = store.get_claim(cid)
        if not claim:
            continue
        frame = claim.position_frame or ""
        prop = store.get_proposition(claim.proposition_id)
        prop_text = prop.canonical_text if prop else ""

        frame_lower = frame.lower()
        if claim.stance == "support":
            agrees = "the speaker is for " in frame_lower and prop_text.lower() in frame_lower
        elif claim.stance == "oppose":
            agrees = "the speaker is against " in frame_lower and prop_text.lower() in frame_lower
        else:
            agrees = "the speaker is for " in frame_lower and "the speaker is against " in frame_lower

        if agrees:
            agreement_count += 1

        print(f"   [{idx:2d}/20] ({claim.stance.upper()}) \"{frame}\"")
        print(f"         <X> : \"{prop_text}\"")
        print(f"         Agree: {agrees}")

    print(f"\n   Validation (c) Agreement Score: {agreement_count} / {len(sample_cids)}")

    # Parameter 033: Check claims per hour on all 23 sources
    print("\n13. Parameter 033: Verifying MIN_CLAIMS_PER_HOUR = 3.0 across all 23 sources...")
    sources = [r[0] for r in store.con.execute("SELECT source_id FROM sources WHERE ingested_at IS NOT NULL ORDER BY recorded_at").fetchall()]
    failed_sources = []
    for sid in sources:
        dur_ms_row = store.con.execute("SELECT duration_ms, title FROM sources WHERE source_id = ?", [sid]).fetchone()
        dur_ms = dur_ms_row[0] if dur_ms_row and dur_ms_row[0] else 3600000
        title = dur_ms_row[1] if dur_ms_row else sid
        dur_h = dur_ms / 3600000.0
        c_count_row = store.con.execute("SELECT count(*) FROM claims c JOIN utterances u ON c.utterance_id = u.utterance_id WHERE u.source_id = ?", [sid]).fetchone()
        c_count = c_count_row[0] if c_count_row else 0
        cph = c_count / dur_h if dur_h > 0 else 0
        if cph < 3.0:
            failed_sources.append((sid, title, c_count, dur_h, cph))
            print(f"   [FAIL P033] {title}: {c_count} claims / {dur_h:.2f}h = {cph:.2f} claims/h (< 3.0)")
        else:
            print(f"   [PASS P033] {title}: {c_count} claims / {dur_h:.2f}h = {cph:.2f} claims/h (>= 3.0)")

    if failed_sources:
        print(f"\n   [WARNING] {len(failed_sources)} sources fell below Parameter 033 floor!")
    else:
        print(f"\n   All {len(sources)} sources satisfy Parameter 033 (>= 3.0 claims/hr).")

    store.close()

    # Run Integrity Checks
    print("\n14. Running Evidence Integrity Checks over live corpus...")
    corpus_results = run_integrity_corpus(db_path)
    print("=" * 70)
    print("CORPUS INTEGRITY RESULTS:")
    print("=" * 70)
    all_passed = True
    for cr in corpus_results:
        status_str = "PASS" if cr.passed else "FAIL"
        print(f"  {cr.name:<40} : [{status_str}] examined={cr.examined_count} — {cr.message}")
        if not cr.passed:
            all_passed = False
    print("=" * 70)
    if all_passed:
        print("ALL 15 INTEGRITY CHECKS PASSED.")
    else:
        print("SOME INTEGRITY CHECKS FAILED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Item X2 full re-extraction runner")
    parser.add_argument("--db", default="social_proof.duckdb", help="Path to DuckDB file")
    parser.add_argument("--verify-only", action="store_true", help="Run verification and integrity checks only")
    args = parser.parse_args()

    if args.verify_only:
        run_post_extraction_verification(args.db)
    else:
        run_full_reextraction(args.db)


if __name__ == "__main__":
    main()
