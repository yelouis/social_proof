"""Repair indexical propositions and re-extract affected claims for Item W0 (§17m).

Implements agent_execution_guide.md §17m (W0):
1. Identifies all claims whose current proposition text contains unbound indexicals
   or sentence-initial unbound pronouns (violating design_data_layer.md §2).
2. Re-extracts those candidate utterances under the fixed prompt (prompt_version="v1.3")
   with validate_self_contained enforced in the extraction pipeline.
3. Removes old indexical claims from the database and inserts clean new claims.
4. Cleans up orphaned indexical propositions.
5. Re-runs proposition deduplication across the corpus at T_dedup = 0.86 with
   entailment validation on re-pointing (Item W1).
6. Re-runs tension detection, principle detection, and rubric assessments.
7. Reports all candidate pairs considered by the tension detector and why each was accepted/rejected.
"""

import sys
import time

from worker.extract.dedup import Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    get_rejection_counts,
    reset_rejection_counts,
    validate_self_contained,
)
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def repair_indexical_propositions(db_path: str = "social_proof.duckdb") -> None:
    print(f"=== Starting W0 Indexical Proposition Repair on {db_path} ===")
    t_start = time.perf_counter()

    store = Storage(db_path, artifact_dir="artifacts")
    gate = ExtractionGate()
    embedder = Embedder()

    # Initialize runtime with live MLX backend and v1.3 prompt
    print("Loading LocalGemmaRuntime with v1.3 prompt and live MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.3",
        schema_version="s1",
        load_live_backend=True,
    )
    print(f"Runtime loaded with extraction_version: {runtime.extraction_version}")

    pipeline = ClaimExtractionPipeline(
        storage=store,
        runtime=runtime,
        gate=gate,
        embedder=embedder,
    )

    # 1. Identify all claims whose propositions fail validate_self_contained
    claims = store.con.execute("""
        SELECT c.claim_id, c.utterance_id, c.proposition_id, p.canonical_text, c.subject_id, c.recorded_at
        FROM claims c
        JOIN propositions p ON c.proposition_id = p.proposition_id
    """).fetchall()

    failing_claim_ids: list[str] = []
    affected_utterance_info: dict[str, tuple[str, str]] = {}  # uid -> (subject_id, recorded_at)
    failing_props: set[str] = set()

    for cid, uid, pid, ptext, subj_id, rec_at in claims:
        dummy = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote text",
            confidence=0.9,
        )
        outcome = validate_self_contained(dummy)
        if not outcome.is_valid:
            failing_claim_ids.append(cid)
            failing_props.add(pid)
            affected_utterance_info[uid] = (subj_id, rec_at)

    print(f"Found {len(failing_claim_ids)} claims across {len(failing_props)} indexical propositions.", flush=True)
    print(f"Unique utterances to re-extract: {len(affected_utterance_info)}", flush=True)

    reset_rejection_counts()

    # 2. Delete old indexical claims first so they cannot hold propositions alive
    print(f"\nDeleting {len(failing_claim_ids)} old indexical claims from database...", flush=True)
    for cid in failing_claim_ids:
        store.con.execute("DELETE FROM claims WHERE claim_id = ?", [cid])

    # 3. Clean up orphaned indexical propositions before re-extraction so new claims cannot merge into them
    print("Cleaning up orphaned indexical propositions...", flush=True)
    orphan_props = store.con.execute("""
        SELECT proposition_id, canonical_text
        FROM propositions
        WHERE status != 'quarantined'
          AND proposition_id NOT IN (SELECT DISTINCT proposition_id FROM claims)
    """).fetchall()

    for pid, _text in orphan_props:
        store.con.execute("DELETE FROM propositions WHERE proposition_id = ?", [pid])
        store.con.execute("DELETE FROM proposition_embeddings WHERE proposition_id = ?", [pid])
        store.con.execute("DELETE FROM claim_entailment_cache WHERE proposition_id = ?", [pid])
    print(f"Deleted {len(orphan_props)} orphaned propositions.", flush=True)

    # 4. Re-extract each affected utterance under v1.3 prompt
    print("\nRe-extracting affected utterances under v1.3 prompt...", flush=True)
    re_extracted_claims_count = 0
    t_reextract_start = time.perf_counter()

    for idx, (uid, (subj_id, rec_at)) in enumerate(affected_utterance_info.items(), 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        # We pass through pipeline.extract_from_utterance
        # This enforces all validators, including validate_self_contained and validate_entailment
        extracted = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=rec_at,
            subject_context=f"Speaker: {subj_id}",
        )
        re_extracted_claims_count += len(extracted)
        if idx % 25 == 0 or idx == len(affected_utterance_info):
            elapsed = time.perf_counter() - t_reextract_start
            print(f"  [{idx}/{len(affected_utterance_info)}] Extracted: {re_extracted_claims_count} new claims ({elapsed:.1f}s)", flush=True)

    print(f"\nRe-extraction complete: {re_extracted_claims_count} new valid claims produced.", flush=True)
    print("Rejection counts during re-extraction:", get_rejection_counts(), flush=True)

    # Re-sync claim_count on all surviving propositions
    store.con.execute("""
        UPDATE propositions
        SET claim_count = (
            SELECT count(*)
            FROM claims c
            WHERE c.proposition_id = propositions.proposition_id
        )
    """)

    # 5. Re-run proposition deduplication across the corpus at T_dedup = 0.86 with W1 entailment guard
    print("\nRe-running proposition deduplication across corpus (T_dedup = 0.86)...")
    t_dedup_start = time.perf_counter()
    dedup_results = store.reresolve_propositions(
        t_dedup=0.86,
        validate_entailment_on_repoint=True,
    )
    print(f"Deduplication finished in {time.perf_counter() - t_dedup_start:.2f}s:", flush=True)
    print(f"  Total survivor propositions: {dedup_results['surviving_propositions']}", flush=True)
    print(f"  Merged away: {dedup_results['merged_away_propositions']}", flush=True)
    print(f"  Claims re-pointed: {dedup_results['repointed_propositions_count']}", flush=True)
    print(f"  Multi-source diff-date propositions: {dedup_results['multi_source_diff_date_propositions']}", flush=True)
    print(f"  Candidate pairs: {dedup_results['candidate_pairs']}", flush=True)

    # 6. Re-run Tension Detection, Principle Detection, Rubric Engine
    print("\nRe-running Tension Detection (P4)...")
    detector = TensionDetector(store, detector_version="v1.0")

    # Clean non-quarantined tensions before re-detecting
    store.con.execute("DELETE FROM tensions WHERE status != 'quarantined'")

    # Enumerate candidate pairs and record outcomes per Assertion (c)
    cand_pairs = store.con.execute("""
        SELECT a.claim_id, b.claim_id, a.proposition_id, p.canonical_text,
               a.subject_id, a.stance, b.stance, a.recorded_at, b.recorded_at
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.recorded_at < b.recorded_at
        JOIN propositions p ON a.proposition_id = p.proposition_id
        WHERE a.is_own_assertion AND b.is_own_assertion
    """).fetchall()

    print(f"\nCandidate pairs considered across all subjects: {len(cand_pairs)}")
    for r in cand_pairs:
        cid_a, cid_b, pid, ptext, s_id, st_a, st_b, dt_a, dt_b = r
        cand_outcome = "opposing_stance (tension candidate)" if st_a != st_b else "concordant_stances (no tension)"
        print(f"  Pair: ({cid_a[:8]}, {cid_b[:8]}) | Subject: {s_id} | Prop: \"{ptext[:60]}...\" | Stances: {st_a} vs {st_b} ({cand_outcome})")

    # Run detection per subject
    subjects = store.con.execute("SELECT subject_id FROM subjects WHERE enrollment_ref IS NOT NULL").fetchall()
    total_detected = 0
    for (s_id,) in subjects:
        t_list = detector.detect_tensions_for_subject(s_id)
        total_detected += len(t_list)

    print(f"Tension detection complete: {total_detected} total tensions in store.")
    pub_t_row = store.con.execute("SELECT count(*) FROM tensions WHERE status = 'published'").fetchone()
    pub_t = pub_t_row[0] if pub_t_row is not None else 0
    quar_t_row = store.con.execute("SELECT count(*) FROM tensions WHERE status = 'quarantined'").fetchone()
    quar_t = quar_t_row[0] if quar_t_row is not None else 0
    print(f"  Published tensions: {pub_t} | Quarantined tensions: {quar_t}")

    # Re-run Principle Conflict Detection (P5)
    print("\nRe-running Principle Conflict Detection (P5)...", flush=True)
    p_detector = PrincipleConflictDetector(store)
    total_p_conflicts = 0
    for (s_id,) in subjects:
        conflicts, _dist = p_detector.detect_conflicts_for_subject(s_id)
        total_p_conflicts += len(conflicts)
    print(f"Principle conflicts detected: {total_p_conflicts}", flush=True)

    # Re-run Rubric Engine (P6)
    print("\nRe-running Rubric Engine (P6)...", flush=True)
    engine = RubricEngine(store)
    assessments = []
    for (s_id,) in subjects:
        for top_id in ["global", "top_ai_reg"]:
            a = engine.assess_subject_topic(s_id, top_id, persist=True)
            assessments.append(a)
    print(f"Evaluated {len(assessments)} assessments.", flush=True)

    # 7. Final Verification
    print("\n=== Post-Repair Verification ===")
    remaining_props = store.con.execute("SELECT proposition_id, canonical_text FROM propositions").fetchall()
    failing_remaining = []
    for pid, text in remaining_props:
        dummy = ExtractedClaim(
            proposition_text=text,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote text",
            confidence=0.9,
        )
        if not validate_self_contained(dummy).is_valid:
            failing_remaining.append((pid, text))

    print(f"Remaining propositions matching indexical patterns: {len(failing_remaining)}")
    if failing_remaining:
        print("FAIL: The following indexical propositions still exist:")
        for pid, t in failing_remaining[:5]:
            print(f"  - {pid}: {t}")
    else:
        print("PASS: Zero propositions match indexical patterns!")

    total_time = time.perf_counter() - t_start
    print(f"\nW0 Repair complete in {total_time:.2f}s ({total_time/60:.2f}m).")


if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else "social_proof.duckdb"
    repair_indexical_propositions(target_db)
