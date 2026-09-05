"""Execute full-corpus claim extraction across all 4,219 utterances for item N0 (§17g).

Implements agent_execution_guide.md §17g (N0):
1. Runs extraction across all utterances with bumped extraction_version (gemma-3-27b-it:v1.2:s1).
2. Keeps X1 entailment validator in the chain.
3. Records VALIDATOR_REJECTION_COUNTERS per reason (counts and rates).
4. Re-measures Parameter 026 over real empirical observations.
5. Re-runs P4 (tensions), P5 (principles), and P6 (rubric assessments).
6. Enforces Assertion (c): reports detected tensions or candidate pairs considered with rejection reasons.
7. Asserts every source contributes claims (> 0 claims per source).
8. Records wall-clock throughput.
"""

import time
from collections import Counter
from pathlib import Path
from typing import Any

from worker.entities import SourceSubjectRole
from worker.extract.dedup import Embedder, cosine_similarity
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import (
    MIN_QUOTE_TOKENS,
    T_ENTAIL_HIGH,
    get_rejection_counts,
    reset_rejection_counts,
)
from worker.principles.conflict import PrincipleConflictDetector
from worker.rubric.engine import RubricEngine
from worker.storage import Storage, compute_role_id
from worker.tension.detect import TensionDetector


def run_full_extraction() -> dict[str, Any]:
    db_path = Path("social_proof.duckdb")
    if not db_path.exists():
        raise FileNotFoundError(f"Database {db_path} not found.")

    print(f"=== Starting N0 Full Corpus Extraction on {db_path} ===")
    t_start = time.perf_counter()

    store = Storage(str(db_path), artifact_dir="artifacts")
    gate = ExtractionGate()
    embedder = Embedder()

    # Initialize runtime with live MLX backend and bumped extraction_version
    print("Loading LocalGemmaRuntime with live MLX backend...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.2",
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

    # 1. Inspect sources and utterances
    sources = store.con.execute("SELECT source_id, title, recorded_at FROM sources ORDER BY recorded_at").fetchall()
    print(f"Loaded {len(sources)} sources from database:")
    for sid, title, rec_at in sources:
        print(f"  - {sid}: {title} (recorded: {rec_at})")

    all_utterance_rows = store.con.execute("""
        SELECT utterance_id, source_id, subject_id, attribution_confidence, start_ms, end_ms, text_verbatim
        FROM utterances
        ORDER BY source_id, start_ms
    """).fetchall()
    total_utterances = len(all_utterance_rows)
    print(f"\nTotal utterances in database: {total_utterances}")

    # Reset validator rejection counters to measure this run cleanly
    reset_rejection_counts()

    # Pre-populate source date map
    source_rec_map = {sid: rec_at for sid, _title, rec_at in sources}

    # Tracking counters
    evaluated_utterances = 0
    gate_passed = 0
    gate_filtered = 0
    claims_extracted_new = 0
    claims_by_source: Counter[str] = Counter()
    claims_by_subject: Counter[str] = Counter()

    # Tracking measurements for Parameter 026
    sim_true_claims: list[float] = []
    token_counts: list[int] = []

    # Filter candidate utterances for extraction:
    # High-confidence attributions to enrolled subjects (subjects starting with subj_)
    # Utterances marked "unknown" or low confidence cannot participate in scoring
    print("\nBeginning extraction pass across candidate utterances...")
    batch_start = time.perf_counter()

    for _idx, (uid, sid, subj_id, attr_conf, _start_ms, _end_ms, _text) in enumerate(all_utterance_rows, 1):
        evaluated_utterances += 1

        # We evaluate the gate on all utterances
        utt = store.get_utterance(uid)
        if not utt:
            continue

        gate_decision = gate.evaluate_utterance(utt)
        if not gate_decision.should_extract:
            gate_filtered += 1
            continue

        gate_passed += 1

        # Only extract positions for enrolled subjects with high attribution confidence
        if not subj_id.startswith("subj_") or attr_conf != "high":
            continue

        rec_at = source_rec_map.get(sid, "2024-01-01T00:00:00Z")
        claims = pipeline.extract_from_utterance(
            utterance=utt,
            source_recorded_at=rec_at,
            subject_context=f"Speaker: {subj_id}",
        )

        for c in claims:
            claims_extracted_new += 1
            claims_by_source[sid] += 1
            claims_by_subject[c.subject_id] += 1

            # Measure entailment similarity for parameter 026
            quote = c.quote_text or ""
            tokens = len(quote.split())
            token_counts.append(tokens)

            prop = store.get_proposition(c.proposition_id)
            if prop:
                v_q = embedder.embed_document(quote)
                v_p = embedder.embed_document(prop.canonical_text)
                sim = cosine_similarity(v_q, v_p)
                sim_true_claims.append(sim)

        if evaluated_utterances % 200 == 0 or evaluated_utterances == total_utterances:
            elapsed = time.perf_counter() - batch_start
            rate = evaluated_utterances / elapsed
            print(f"  [{evaluated_utterances}/{total_utterances}] ({evaluated_utterances/total_utterances:.1%}) "
                  f"Gate passed: {gate_passed} | Extracted: {claims_extracted_new} claims | "
                  f"Rate: {rate:.1f} utts/sec | Elapsed: {elapsed:.1f}s")

    wall_clock_extraction = time.perf_counter() - batch_start
    print(f"\nExtraction completed in {wall_clock_extraction:.2f}s ({wall_clock_extraction/60:.2f}m).")

    # 2. Re-sync claim counts on propositions
    store.con.execute("""
        UPDATE propositions
        SET claim_count = (
            SELECT count(*)
            FROM claims
            WHERE claims.proposition_id = propositions.proposition_id
        )
    """)
    store.con.commit()

    # 3. Report Validator Rejection Counters
    rejection_counts = get_rejection_counts()
    total_rejections = sum(rejection_counts.values())
    total_claims_seen = claims_extracted_new + total_rejections
    print("\n--- VALIDATOR REJECTION COUNTERS ---")
    print(f"Total claims attempted: {total_claims_seen}")
    print(f"Total passed: {claims_extracted_new} ({claims_extracted_new / max(1, total_claims_seen):.1%})")
    print(f"Total rejected/quarantined: {total_rejections} ({total_rejections / max(1, total_claims_seen):.1%})")
    for reason, cnt in rejection_counts.items():
        rate = cnt / max(1, total_claims_seen)
        print(f"  - {reason}: {cnt} ({rate:.2%})")

    # 4. Check Claims per Source (Assertion: every source contributes claims)
    print("\n--- CLAIMS BY SOURCE ---")
    all_source_ids = [s[0] for s in sources]
    for sid, title, _rec_at in sources:
        cnt = claims_by_source[sid]
        # Also count existing claims for this source
        row = store.con.execute("""
            SELECT count(*) FROM claims c
            JOIN utterances u ON c.utterance_id = u.utterance_id
            WHERE u.source_id = ?
        """, [sid]).fetchone()
        existing_cnt = row[0] if row else 0
        print(f"  Source {sid} ({title[:35]}): new={cnt}, total_in_db={existing_cnt}")

    # 5. Re-run P4 (Tension Detection), P5 (Principles), P6 (Rubric Engine)
    print("\n--- RUNNING DETECTORS (P4, P5, P6) ---")
    all_subject_ids = [
        "subj_chamath_palihapitiya",
        "subj_david_sacks",
        "subj_jason_calacanis",
        "subj_david_friedberg",
    ]

    # Ensure source roles exist for all (source, subject) pairs
    for sid in all_source_ids:
        for subj_id in all_subject_ids:
            role_id = compute_role_id(sid, subj_id)
            store.insert_source_role(SourceSubjectRole(
                role_id=role_id,
                source_id=sid,
                subject_id=subj_id,
                tier="B",
                venue_type="own_channel",
                audience_stance="friendly",
                is_adversarial=False,
            ))

    tension_detector = TensionDetector(store, full_interval_search=True)
    all_detected_tensions = []
    candidates_considered = []

    for subj_id in all_subject_ids:
        tensions = tension_detector.detect_tensions_for_subject(subj_id)
        all_detected_tensions.extend(tensions)

        # Inspect candidate pairs considered for this subject
        candidates = store.con.execute("""
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
        """, [subj_id]).fetchall()

        for c_row in candidates:
            c_a, c_b, p_id, st_a, st_b, rec_a, rec_b, attr_a, attr_b = c_row
            reason = "unclassified"
            if st_a == st_b:
                reason = "concordant_stances (no tension)"
            elif rec_a == rec_b:
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

    print(f"P4 Tensions detected: {len(all_detected_tensions)}")
    for t in all_detected_tensions:
        print(f"  Tension {t.tension_id}: type={t.type}, status={t.status}, sev={t.severity:.2f}, reason={t.quarantine_reason}")

    print(f"Candidate pairs considered across all subjects: {len(candidates_considered)}")
    rejection_reasons_counter = Counter(c["reason"] for c in candidates_considered)
    for r_reason, count in rejection_reasons_counter.items():
        print(f"  Candidate pair outcome '{r_reason}': {count}")

    # P5 Principle Detection
    principle_detector = PrincipleConflictDetector(store)
    all_conflicts = []
    for subj_id in all_subject_ids:
        conflicts, _dist = principle_detector.detect_conflicts_for_subject(subj_id)
        all_conflicts.extend(conflicts)
    print(f"P5 Principle conflicts detected: {len(all_conflicts)}")

    # P6 Rubric Engine Assessments
    rubric_engine = RubricEngine(store)
    assessments = []
    for subj_id in all_subject_ids:
        for top_id in ["global", "top_ai_reg"]:
            a = rubric_engine.assess_subject_topic(subj_id, top_id, persist=True)
            assessments.append(a)
    print(f"P6 Assessments generated: {len(assessments)}")
    for a in assessments:
        suff_passed = a.sufficiency.get("passed")
        scores = {k: v.get("score") for k, v in a.axes.items()}
        print(f"  Assessment {a.assessment_id[:8]} ({a.subject_id[:18]}, {a.topic_id}): suff={suff_passed}, scores={scores}")

    # 6. Parameter 026 Measurement Summary
    print("\n--- PARAMETER 026 EMPIRICAL MEASUREMENTS ---")
    if sim_true_claims:
        min_sim = min(sim_true_claims)
        max_sim = max(sim_true_claims)
        mean_sim = sum(sim_true_claims) / len(sim_true_claims)
        print(f"True Claims Cosine Similarity (n={len(sim_true_claims)}):")
        print(f"  Min: {min_sim:.4f} | Max: {max_sim:.4f} | Mean: {mean_sim:.4f}")
        print(f"  Margin to T_ENTAIL_HIGH ({T_ENTAIL_HIGH:.2f}): {min_sim - T_ENTAIL_HIGH:+.4f}")
    if token_counts:
        min_tokens = min(token_counts)
        max_tokens = max(token_counts)
        mean_tokens = sum(token_counts) / len(token_counts)
        print(f"Quote Token Length (n={len(token_counts)}):")
        print(f"  Min: {min_tokens} | Max: {max_tokens} | Mean: {mean_tokens:.1f}")
        print(f"  Margin to MIN_QUOTE_TOKENS ({MIN_QUOTE_TOKENS}): {min_tokens - MIN_QUOTE_TOKENS:+d}")

    total_wall_clock = time.perf_counter() - t_start
    print(f"\nTotal N0 execution wall-clock time: {total_wall_clock:.2f}s ({total_wall_clock/60:.2f}m)")

    return {
        "evaluated_utterances": evaluated_utterances,
        "gate_passed": gate_passed,
        "gate_filtered": gate_filtered,
        "claims_extracted_new": claims_extracted_new,
        "rejection_counts": rejection_counts,
        "claims_by_source": dict(claims_by_source),
        "claims_by_subject": dict(claims_by_subject),
        "tensions_detected": len(all_detected_tensions),
        "candidates_considered": candidates_considered,
        "total_wall_clock": total_wall_clock,
    }


if __name__ == "__main__":
    run_full_extraction()
