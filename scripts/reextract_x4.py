"""Item X4 (§11) — Full corpus re-extraction under Prompt v1.9 with reachable decline branch.

1. Backs up social_proof.duckdb to social_proof.duckdb.pre_x4.bak.
2. Snapshots pre-X4 tables to claims_pre_x4, propositions_pre_x4, etc.
3. Re-extracts candidate utterances with LocalGemmaRuntime (prompt v1.9 with decline branch).
4. Persists position_frame on every claim.
5. Re-runs proposition deduplication at T_dedup = 0.96 untouched (deferred to D9).
6. Re-runs TensionDetector, PrincipleConflictDetector, and RubricEngine.
7. Reconciles claim count change with rejection and exclusion counters (including reports_fact).
8. Checks Parameter 033 (MIN_CLAIMS_PER_HOUR = 3.0) across all 23 sources.
9. Audits tension candidate pairs by reading both stored position_frame sentences and quotes.
10. Validates (c): Draws 40 random own-assertion claims with recorded seed 20260910 to verify >= 80% genuine positions.
11. Asserts both directions by utterance ID:
    - 03821a2c2f50bc9a (Azure Fed ramp) produces no claim
    - 73c1f91e3d98e960 (spend millions) produces AGAINST
12. Runs integrity suite (worker.integrity) to ensure all checks PASS.
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

    bak_path = Path(f"{db_path}.pre_x4.bak")
    print(f"1. Backing up {db_path} to {bak_path}...")
    shutil.copy2(p, bak_path)
    print("   Backup complete.")

    store = Storage(db_path, artifact_dir="artifacts")

    # Snapshot existing tables inside DuckDB for auditability
    print("2. Archiving pre-X4 tables into claims_pre_x4 and propositions_pre_x4...")
    store.con.execute("CREATE TABLE IF NOT EXISTS claims_pre_x4 AS SELECT * FROM claims;")
    store.con.execute(
        "CREATE TABLE IF NOT EXISTS propositions_pre_x4 AS SELECT * FROM propositions;"
    )
    store.con.execute(
        "CREATE TABLE IF NOT EXISTS proposition_embeddings_pre_x4 AS SELECT * FROM proposition_embeddings;"
    )
    store.con.execute("CREATE TABLE IF NOT EXISTS tensions_pre_x4 AS SELECT * FROM tensions;")
    store.con.commit()

    pre_claims_count = (
        r[0] if (r := store.con.execute("SELECT count(*) FROM claims_pre_x4").fetchone()) else 0
    )
    pre_props_count = (
        r[0]
        if (r := store.con.execute("SELECT count(*) FROM propositions_pre_x4").fetchone())
        else 0
    )
    print(f"   Pre-X4 baseline: {pre_claims_count} claims, {pre_props_count} propositions.")

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

    # Initialize extraction pipeline with prompt v1.9 and live MLX backend
    print("\n5. Initializing LocalGemmaRuntime with prompt v1.9 and MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.9",
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

    print(f"\n6. Starting full re-extraction under prompt v1.9 (T_dedup={DEFAULT_T_DEDUP})...")
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

    print("\n--- STEP 3 RECONCILIATION ---")
    print(f"Pre-X4 claims: {pre_claims_count}")
    print(f"Post-X4 extracted: {claims_total} claims")

    rejections = get_rejection_counts()
    exclusions = get_exclusion_counts()
    print("\nValidator Rejection Counters:")
    for reason, cnt in sorted(rejections.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")
    print("\nValidator Exclusion Counters (Non-own assertions):")
    for reason, cnt in sorted(exclusions.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}")

    # Proposition Deduplication & Re-resolution at T_dedup = 0.96 (untouched per §11 Step 3)
    print(
        f"\n7. Re-running proposition deduplication consolidation at T_dedup = {DEFAULT_T_DEDUP}..."
    )
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
    for t in all_tensions:
        ca = store.get_claim(t.claim_a_id)
        cb = store.get_claim(t.claim_b_id)
        print(f"\n   --- TENSION {t.tension_id} ({t.status}) ---")
        print(
            f"   Claim A ({t.claim_a_id}): frame='{ca.position_frame if ca else None}' | quote='{ca.quote_text if ca else None}'"
        )
        print(
            f"   Claim B ({t.claim_b_id}): frame='{cb.position_frame if cb else None}' | quote='{cb.quote_text if cb else None}'"
        )

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
    """Runs all verification steps on the extracted DuckDB database."""
    store = Storage(db_path, read_only=True)

    print("\n--- CORPUS SUMMARY STATS ---")
    c_count = r[0] if (r := store.con.execute("SELECT count(*) FROM claims").fetchone()) else 0
    p_count = (
        r[0]
        if (
            r := store.con.execute(
                "SELECT count(*) FROM propositions WHERE status = 'active'"
            ).fetchone()
        )
        else 0
    )
    stances = store.con.execute(
        "SELECT stance, count(*) FROM claims GROUP BY 1 ORDER BY 1"
    ).fetchall()
    print(f"Total claims       : {c_count}")
    print(f"Active propositions: {p_count}")
    print(f"Stance distribution: {stances}")

    # Calculate support share
    total_stances = sum(cnt for _, cnt in stances)
    support_cnt = sum(cnt for st, cnt in stances if st == "support")
    oppose_cnt = sum(cnt for st, cnt in stances if st == "oppose")
    mixed_cnt = sum(cnt for st, cnt in stances if st == "mixed")
    support_pct = (support_cnt / total_stances * 100) if total_stances > 0 else 0
    oppose_pct = (oppose_cnt / total_stances * 100) if total_stances > 0 else 0
    mixed_pct = (mixed_cnt / total_stances * 100) if total_stances > 0 else 0
    print(
        f"Stance breakdown: support={support_pct:.1f}% ({support_cnt}), oppose={oppose_pct:.1f}% ({oppose_cnt}), mixed={mixed_pct:.1f}% ({mixed_cnt})"
    )

    # Check Parameter 033: MIN_CLAIMS_PER_HOUR = 3.0 across all 23 sources
    print("\n--- PARAMETER 033 CHECK (MIN_CLAIMS_PER_HOUR = 3.0) ---")
    src_stats = store.con.execute("""
        SELECT
            src.source_id,
            src.title,
            src.duration_ms,
            count(c.claim_id) as claim_count
        FROM sources src
        LEFT JOIN utterances u ON src.source_id = u.source_id
        LEFT JOIN claims c ON u.utterance_id = c.utterance_id
        GROUP BY src.source_id, src.title, src.duration_ms
        ORDER BY src.source_id
    """).fetchall()

    min_rate = 999.0
    failed_sources = []
    print(f"{'Source ID':<18} | {'Duration (m)':<12} | {'Claims':<6} | {'Claims/hr':<9} | Status")
    print("-" * 65)
    for sid, name, dur_ms, cc in src_stats:
        dur_h = (dur_ms / 1000.0 / 3600.0) if dur_ms and dur_ms > 0 else 1.0
        dur_m = (dur_ms / 1000.0 / 60.0) if dur_ms and dur_ms > 0 else 0.0
        rate = cc / dur_h
        min_rate = min(min_rate, rate)
        status = "PASS" if rate >= 3.0 else "BELOW_FLOOR"
        if rate < 3.0:
            failed_sources.append((sid, name, rate))
        print(f"{sid:<18} | {dur_m:<12.1f} | {cc:<6d} | {rate:<9.2f} | {status}")

    print(f"\nMinimum claims/hour across 23 sources: {min_rate:.2f}")
    if failed_sources:
        print(f"WARNING: {len(failed_sources)} source(s) below MIN_CLAIMS_PER_HOUR = 3.0 floor:")
        for sid, name, rate in failed_sources:
            print(f"  {sid} ({name}): {rate:.2f} claims/hr")
    else:
        print("PASS: All 23 sources cleared MIN_CLAIMS_PER_HOUR = 3.0 floor.")

    # Check both directions by utterance ID
    print("\n--- BOTH DIRECTIONS BY UTTERANCE ID ---")
    # Direction 1: Azure Fed ramp (03821a2c2f50bc9a) -> no claim
    azure_claims = store.con.execute(
        "SELECT claim_id, position_frame FROM claims WHERE utterance_id = '03821a2c2f50bc9a'"
    ).fetchall()
    print(f"Azure Fed ramp (03821a2c2f50bc9a) claims count: {len(azure_claims)}")
    if azure_claims:
        print(f"  FAIL: Azure Fed ramp produced claims: {azure_claims}")
    else:
        print("  PASS: Azure Fed ramp produced NO claims.")

    # Direction 2: Hardware spend (73c1f91e3d98e960) -> produces AGAINST
    spend_claims = store.con.execute(
        "SELECT claim_id, stance, position_frame FROM claims WHERE utterance_id = '73c1f91e3d98e960'"
    ).fetchall()
    print(f"Hardware spend (73c1f91e3d98e960) claims count: {len(spend_claims)}")
    if spend_claims:
        for cid, stance, frame in spend_claims:
            print(f"  Claim {cid}: stance={stance} | frame='{frame}'")
            if stance == "oppose":
                print("  PASS: Hardware spend produced AGAINST.")
    else:
        print("  FAIL: Hardware spend produced no claims.")

    # Assertion (c) Validation: Draw 40 own-assertion claims with seed 20260910
    print("\n--- ASSERTION (c) VALIDATION SAMPLE (N=40, seed=20260910) ---")
    own_claims = store.con.execute("""
        SELECT
            c.claim_id,
            c.utterance_id,
            c.stance,
            c.position_frame,
            p.canonical_text,
            c.quote_text
        FROM claims c
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE c.is_own_assertion = true
        ORDER BY c.claim_id
    """).fetchall()

    rng = random.Random(20260910)
    sample_40 = rng.sample(own_claims, min(40, len(own_claims)))

    print(f"Drawn {len(sample_40)} own-assertion claims.")
    for idx, (cid, uid, _stance, frame, prop, quote) in enumerate(sample_40, 1):
        print(f"\nClaim [{idx:02d}/40] {cid} (utt: {uid})")
        print(f"  Frame: {frame}")
        print(f"  Prop:  {prop}")
        print(f'  Quote: "{quote}"')

    # Run Integrity Checks
    print("\n--- RUNNING INTEGRITY SUITE ---")
    store.close()
    integrity_res = run_integrity_corpus(db_path)
    all_passed = all(r.passed for r in integrity_res)
    print(f"Integrity Suite Result: {'ALL PASS' if all_passed else 'SOME FAILED'}")
    for chk in integrity_res:
        print(f"  {chk.name:<35}: {'PASS' if chk.passed else 'FAIL'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="social_proof.duckdb")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        run_post_extraction_verification(args.db_path)
    else:
        run_full_reextraction(args.db_path)
