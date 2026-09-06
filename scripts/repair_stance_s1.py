"""Repair stance direction and speech act exclusions for Item S1 (§17n).

Implements agent_execution_guide.md §17n (S1):
1. Corrects the two stance mislabellings on existing claims:
   - af95392de868a188: Friedberg spending Quote B -> stance='support'
   - 7f571f16d81af8c5: Sacks AI tasks Quote B -> stance='support'
2. Enforces enhanced Invariant I7 speech-act sensitivity across corpus:
   - Excludes interrogatives/questions (e.g. Chamath a9d307efd45c60ac) as 'question'
   - Excludes rhetorical setups/conditionals (e.g. Calacanis Verizon 12ea81ee770fbd66) as 'hypothetical'
3. Re-runs tension detection, principle conflict detection, and rubric assessments.
4. Reports the updated I7 exclusion rate and candidate pair audit.
"""

import sys
import time

from worker.extract.validators import (
    QUESTION_SPEECH_ACT_PATTERNS,
    RHETORICAL_SPEECH_ACT_PATTERNS,
    get_exclusion_rate,
)
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def repair_stance_and_speech_acts(db_path: str = "social_proof.duckdb") -> None:
    print(f"=== Starting S1 Stance & Speech-Act Repair on {db_path} ===")
    t_start = time.perf_counter()

    store = Storage(db_path, artifact_dir="artifacts")

    # 1. Correct the two stance mislabellings
    print("\nCorrecting mislabelled stance claims...")
    store.con.execute("""
        UPDATE claims
        SET stance = 'support'
        WHERE claim_id IN ('af95392de868a188', '7f571f16d81af8c5')
    """)
    print("  af95392de868a188 (Friedberg spending) updated to stance='support'")
    print("  7f571f16d81af8c5 (Sacks AI tasks) updated to stance='support'")

    # 2. Apply Invariant I7 speech-act sensitivity across corpus
    print("\nApplying Invariant I7 speech-act sensitivity across all claims...")
    all_claims = store.con.execute("""
        SELECT claim_id, quote_text, is_own_assertion, exclusion_reason
        FROM claims
    """).fetchall()

    question_downgrades = []
    rhetorical_downgrades = []

    for cid, qtext, own, _exc in all_claims:
        if not own:
            continue
        q = (qtext or "").strip()
        if any(pat.search(q) for pat in QUESTION_SPEECH_ACT_PATTERNS):
            question_downgrades.append(cid)
        elif any(pat.search(q) for pat in RHETORICAL_SPEECH_ACT_PATTERNS):
            rhetorical_downgrades.append(cid)

    print(
        f"  Downgrading {len(question_downgrades)} claims to is_own_assertion=False, exclusion_reason='question'"
    )
    for cid in question_downgrades:
        store.con.execute(
            """
            UPDATE claims
            SET is_own_assertion = false, exclusion_reason = 'question'
            WHERE claim_id = ?
        """,
            [cid],
        )

    print(
        f"  Downgrading {len(rhetorical_downgrades)} claims to is_own_assertion=False, exclusion_reason='hypothetical'"
    )
    for cid in rhetorical_downgrades:
        store.con.execute(
            """
            UPDATE claims
            SET is_own_assertion = false, exclusion_reason = 'hypothetical'
            WHERE claim_id = ?
        """,
            [cid],
        )

    # Report exclusion rate
    exc_count, total_count, exc_rate = get_exclusion_rate(store)
    print(f"\nUpdated I7 Exclusion Metric: {exc_count} of {total_count} claims ({exc_rate:.2f}%)")

    # 3. Re-run proposition deduplication
    print("\nRe-running proposition deduplication across corpus (T_dedup = 0.86)...")
    dedup_results = store.reresolve_propositions(
        t_dedup=0.86,
        validate_entailment_on_repoint=True,
    )
    print(f"Deduplication complete: {dedup_results['surviving_propositions']} active propositions.")

    # 4. Re-run Tension Detection (P4)
    print("\nRe-running Tension Detection (P4)...")
    detector = TensionDetector(store, detector_version="v1.0")

    # Clean non-quarantined tensions before re-detecting
    store.con.execute("DELETE FROM tensions WHERE status != 'quarantined'")

    # Run detection per subject
    subjects = store.con.execute(
        "SELECT subject_id FROM subjects WHERE enrollment_ref IS NOT NULL"
    ).fetchall()
    total_detected = 0
    for (s_id,) in subjects:
        t_list = detector.detect_tensions_for_subject(s_id)
        total_detected += len(t_list)

    pub_t_row = store.con.execute(
        "SELECT count(*) FROM tensions WHERE status = 'published'"
    ).fetchone()
    pub_t = pub_t_row[0] if pub_t_row is not None else 0
    quar_t_row = store.con.execute(
        "SELECT count(*) FROM tensions WHERE status = 'quarantined'"
    ).fetchone()
    quar_t = quar_t_row[0] if quar_t_row is not None else 0
    print(f"  Published tensions: {pub_t} | Quarantined tensions: {quar_t}")

    # Re-run Principle Conflict Detection (P5)
    print("\nRe-running Principle Conflict Detection (P5)...")
    p_detector = PrincipleConflictDetector(store)
    total_p_conflicts = 0
    for (s_id,) in subjects:
        conflicts, _dist = p_detector.detect_conflicts_for_subject(s_id)
        total_p_conflicts += len(conflicts)
    print(f"Principle conflicts detected: {total_p_conflicts}")

    # Re-run Rubric Engine (P6)
    print("\nRe-running Rubric Engine (P6)...")
    engine = RubricEngine(store)
    assessments = []
    for (s_id,) in subjects:
        for top_id in ["global", "top_ai_reg"]:
            a = engine.assess_subject_topic(s_id, top_id, persist=True)
            assessments.append(a)
    print(f"Evaluated {len(assessments)} assessments.")

    # 5. Assertion (c) Check: All four target candidate pairs must be eliminated
    print("\n=== Verifying Assertion (c): Target False Candidate Pairs ===")
    cand_pairs = store.con.execute("""
        SELECT a.claim_id, b.claim_id, a.subject_id, a.proposition_id,
               a.stance, b.stance, a.is_own_assertion, b.is_own_assertion
        FROM claims a
        JOIN claims b ON a.proposition_id = b.proposition_id
                     AND a.subject_id = b.subject_id
                     AND a.claim_id < b.claim_id
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance != b.stance
    """).fetchall()

    cand_set = {(r[0], r[1]) for r in cand_pairs} | {(r[1], r[0]) for r in cand_pairs}

    target_pairs = [
        ("017b3ab8b76684d2", "af95392de868a188", "Friedberg spending"),
        ("bc553e2fecff8a27", "7f571f16d81af8c5", "Sacks AI tasks"),
        ("12ea81ee770fbd66", "4b92c00aef07ef90", "Calacanis Verizon analogy"),
        ("a9d307efd45c60ac", "d11bb9a4b8981763", "Chamath question"),
    ]

    all_eliminated = True
    for ca, cb, name in target_pairs:
        is_candidate = (ca, cb) in cand_set or (cb, ca) in cand_set
        status_str = "ELIMINATED (PASS)" if not is_candidate else "STILL CANDIDATE (FAIL)"
        print(f"  Target pair [{name}]: ({ca}, {cb}) -> {status_str}")
        if is_candidate:
            all_eliminated = False

    if all_eliminated:
        print("\nPASS: All four target false candidate pairs have stopped being candidate pairs!")
    else:
        print("\nFAIL: Some target pairs are still candidate pairs.")

    print(f"Total opposing-stance candidate pairs remaining in corpus: {len(cand_pairs)}")

    total_time = time.perf_counter() - t_start
    print(f"\nS1 Repair complete in {total_time:.2f}s.")


if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else "social_proof.duckdb"
    repair_stance_and_speech_acts(target_db)
