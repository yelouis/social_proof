"""Repair unbound pronouns and comparatives for Item W2 (§17p).

Implements agent_execution_guide.md §17p (W2):
1. Identifies all claims whose current proposition text contains unbound pronouns,
   sentence-initial deictics, or comparatives with no relatum.
2. Deletes those claims and purges orphaned propositions.
3. Re-extracts the affected candidate utterances under prompt v1.5 with the extended
   validate_self_contained validator enforced in the extraction pipeline.
4. Re-syncs proposition claim counts and re-runs proposition deduplication across the
   corpus at T_dedup = 0.86 with W1 entailment guard.
5. Re-runs tension detection (with Item T1 same-source disqualification), principle
   detection, and rubric assessments.
6. Verifies zero propositions in the store contain unbound pronouns or deictics (Assertion c).
"""

from __future__ import annotations

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


def repair_pronouns_w2(db_path: str = "social_proof.duckdb") -> None:
    print(f"=== Starting W2 Pronoun & Self-Containment Repair on {db_path} ===")
    t_start = time.perf_counter()

    store = Storage(db_path, artifact_dir="artifacts")
    gate = ExtractionGate()
    embedder = Embedder()

    # Initialize runtime with live MLX backend and v1.5 prompt
    print("Loading LocalGemmaRuntime with v1.5 prompt and live MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.5",
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

    print(f"Found {len(failing_claim_ids)} claims across {len(failing_props)} failing propositions.", flush=True)
    print(f"Unique utterances to re-extract: {len(affected_utterance_info)}", flush=True)

    reset_rejection_counts()

    # 2. Delete old unbound claims first so they cannot hold propositions alive
    print(f"\nDeleting {len(failing_claim_ids)} old unbound claims from database...", flush=True)
    for cid in failing_claim_ids:
        store.con.execute("DELETE FROM claims WHERE claim_id = ?", [cid])

    # 3. Clean up orphaned propositions before re-extraction so new claims cannot merge into them
    print("Cleaning up orphaned propositions...", flush=True)
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

    # 4. Re-extract each affected utterance under v1.5 prompt
    print("\nRe-extracting affected utterances under v1.5 prompt...", flush=True)
    re_extracted_claims_count = 0
    t_reextract_start = time.perf_counter()

    for idx, (uid, (subj_id, rec_at)) in enumerate(affected_utterance_info.items(), 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        extracted = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=rec_at,
            subject_context=f"Speaker: {subj_id}",
        )
        re_extracted_claims_count += len(extracted)
        if idx % 25 == 0 or idx == len(affected_utterance_info):
            elapsed = time.perf_counter() - t_reextract_start
            print(
                f"  [{idx}/{len(affected_utterance_info)}] Extracted: {re_extracted_claims_count} new claims ({elapsed:.1f}s)",
                flush=True,
            )

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

    # 6. Re-run Tension Detection (with T1 same-source check)
    print("\nRe-running Tension Detection (Item T1 / P4)...")
    detector = TensionDetector(store, detector_version="v1.0", min_reversal_gap_days=0.0)

    # Clean non-quarantined tensions before re-detecting
    store.con.execute("DELETE FROM tensions WHERE status != 'quarantined'")

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
    print("\n=== Post-Repair Verification (Assertion c) ===")
    remaining_props = store.con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()
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

    print(f"Remaining active propositions failing self-containment: {len(failing_remaining)}")
    if failing_remaining:
        print("FAIL: The following propositions with unbound pronouns/deictics still exist:")
        for pid, t in failing_remaining[:5]:
            print(f"  - {pid}: {t}")
    else:
        print("PASS: Zero propositions contain unbound pronouns or deictics! (Assertion c satisfied)")

    total_time = time.perf_counter() - t_start
    print(f"\nW2 Repair complete in {total_time:.2f}s ({total_time/60:.2f}m).")


if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else "social_proof.duckdb"
    repair_pronouns_w2(target_db)
