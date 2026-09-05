"""Re-resolves proposition deduplication across the corpus at Parameter 008 (T_dedup = 0.86).

Implements agent_execution_guide.md §17j (P0) and §17l (W1).
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import DEFAULT_T_DEDUP
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def run_remerge(
    db_path: str = "social_proof.duckdb",
    threshold: float = DEFAULT_T_DEDUP,
    from_pre_merge: bool = False,
) -> dict[str, object]:
    print(f"=== Proposition Deduplication Re-resolution (T_dedup={threshold:.3f}) ===")
    store = Storage(db_path=db_path)

    # 1. Execute proposition re-resolution
    stats = store.reresolve_propositions(t_dedup=threshold, from_pre_merge=from_pre_merge)
    print(f"Surviving propositions: {stats['surviving_propositions']}")
    print(f"Merged-away propositions: {stats['merged_away_propositions']}")
    print(f"Re-pointed claims: {stats['repointed_propositions_count']}")
    print(f"Multi-source diff-date propositions: {stats['multi_source_diff_date_propositions']}")
    print("Merge histogram (claim_count: proposition_count):")
    hist = stats["merge_histogram"]
    if isinstance(hist, dict):
        for count_val, p_count in sorted(hist.items()):
            print(f"  {count_val} claim(s): {p_count} proposition(s)")

    # 2. Re-run P4 Tension Detection
    print("\n--- P4 Tension Detection ---")
    store.con.execute("DELETE FROM tensions WHERE status != 'quarantined';")
    subjects = [
        r[0]
        for r in store.con.execute("SELECT subject_id FROM subjects ORDER BY subject_id").fetchall()
    ]
    td = TensionDetector(store)
    all_tensions = []
    candidates_considered = []

    for subj_id in subjects:
        tensions = td.detect_tensions_for_subject(subj_id)
        all_tensions.extend(tensions)

        # Inspect candidate pairs for this subject
        candidates = store.con.execute(
            """
            SELECT
                a.claim_id AS claim_a_id,
                b.claim_id AS claim_b_id,
                a.proposition_id,
                a.stance AS stance_a,
                b.stance AS stance_b,
                a.recorded_at AS rec_a,
                b.recorded_at AS rec_b,
                ua.attribution_confidence AS attr_a,
                ub.attribution_confidence AS attr_b
            FROM claims a
            JOIN claims b
              ON a.proposition_id = b.proposition_id
             AND a.subject_id = b.subject_id
             AND a.claim_id < b.claim_id
            JOIN utterances ua ON a.utterance_id = ua.utterance_id
            JOIN utterances ub ON b.utterance_id = ub.utterance_id
            WHERE a.subject_id = ?
            """,
            [subj_id],
        ).fetchall()

        for c_row in candidates:
            c_a, c_b, p_id, st_a, st_b, rec_a, rec_b, attr_a, attr_b = c_row
            if st_a == st_b:
                reason = "concordant_stances (no tension)"
            elif rec_a[:10] == rec_b[:10]:
                reason = "same_recorded_date (no temporal delta)"
            elif attr_a != "high" or attr_b != "high":
                reason = "low_attribution_confidence"
            else:
                reason = "evaluated_by_detector"
            candidates_considered.append({
                "subject_id": subj_id,
                "claim_a": c_a,
                "claim_b": c_b,
                "proposition_id": p_id,
                "reason": reason,
            })

    print(f"Candidate pairs considered across all subjects: {len(candidates_considered)}")
    rejection_counter = Counter(c["reason"] for c in candidates_considered)
    for reason, count in sorted(rejection_counter.items()):
        print(f"  Outcome '{reason}': {count}")

    print(f"Published/Quarantined tensions detected: {len(all_tensions)}")
    for t in all_tensions:
        print(f"  Tension {t.tension_id[:8]}: type={t.type}, status={t.status}, severity={t.severity:.2f}")

    # 3. Re-run P5 Principle Conflict Detection
    print("\n--- P5 Principle Conflict Detection ---")
    pd = PrincipleConflictDetector(store)
    all_conflicts = []
    for subj_id in subjects:
        conflicts, _ = pd.detect_conflicts_for_subject(subj_id)
        all_conflicts.extend(conflicts)
    print(f"Principle conflicts detected: {len(all_conflicts)}")

    # 4. Re-run P6 Rubric Engine Assessments
    print("\n--- P6 Rubric Engine Assessments ---")
    re = RubricEngine(store)
    assessments = []
    for subj_id in subjects:
        for top_id in ["global", "top_ai_reg"]:
            a = re.assess_subject_topic(subj_id, top_id, persist=True)
            assessments.append(a)
            scores = {k: v.get("score") for k, v in a.axes.items()}
            print(f"  Assessment {subj_id[:20]} ({top_id}): passed={a.sufficiency.get('passed')}, scores={scores}")

    store.close()
    return {
        "stats": stats,
        "tensions": len(all_tensions),
        "candidate_pairs_total": len(candidates_considered),
        "candidates_by_reason": dict(rejection_counter),
        "conflicts": len(all_conflicts),
        "assessments": len(assessments),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-resolve proposition deduplication at threshold T_dedup.")
    parser.add_argument("--db", type=str, default="social_proof.duckdb", help="Path to DuckDB database")
    parser.add_argument("--threshold", type=float, default=DEFAULT_T_DEDUP, help="Deduplication threshold (Parameter 008)")
    parser.add_argument("--from-pre-merge", action="store_true", help="Restore from pre-merge tables first")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database {args.db} does not exist.", file=sys.stderr)
        sys.exit(1)

    run_remerge(db_path=args.db, threshold=args.threshold, from_pre_merge=args.from_pre_merge)


if __name__ == "__main__":
    main()
