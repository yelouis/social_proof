"""Item D5 (§13x) Step 1: Fixed 300-utterance sample re-extraction and rejection counter audit."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import Embedder
from worker.extract.gate import ExtractionGate
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import (
    MIN_QUOTE_TOKENS,
    T_ENTAIL_HIGH,
    T_ENTAIL_LOW,
    reset_rejection_counts,
    validate_confidence_floor,
    validate_entailment,
    validate_polarity,
    validate_quote_verbatim,
    validate_schema,
    validate_self_contained,
    validate_speech_acts,
    validate_stance_direction,
)
from worker.storage import Storage


@dataclass
class RejectedCandidateRecord:
    utterance_id: str
    source_id: str
    speaker_name: str
    utterance_text: str
    proposition_text: str
    quote_text: str
    stance: str
    hedging_level: float
    is_own_assertion: bool
    exclusion_reason: str | None
    confidence: float
    rejection_reason: str
    validator_stage: str


def run_sample_audit(
    db_path: str = "social_proof.duckdb",
    sample_size: int = 300,
    output_json: str = "fixtures/behaviour/d5_sample_audit_results.json",
) -> dict[str, Any]:
    store = Storage(db_path, artifact_dir="artifacts")

    print(f"Loading candidate utterances for D5 sample audit (sample_size={sample_size})...")
    target_utts_rows = store.con.execute(f"""
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
        LIMIT {sample_size}
    """).fetchall()

    sample_uids = [r[0] for r in target_utts_rows]

    # Pre-D1 and current Post-D1 claims in these 300 utterances
    pre_claims_rows = store.con.execute(
        """
        SELECT claim_id, utterance_id, proposition_id, stance, quote_text, is_own_assertion
        FROM claims_pre_d1
        WHERE utterance_id IN (SELECT unnest(?))
    """,
        [sample_uids],
    ).fetchall()
    pre_claims_count = len(pre_claims_rows)

    post_claims_rows = store.con.execute(
        """
        SELECT claim_id, utterance_id, proposition_id, stance, quote_text, is_own_assertion
        FROM claims
        WHERE utterance_id IN (SELECT unnest(?))
    """,
        [sample_uids],
    ).fetchall()
    post_claims_count = len(post_claims_rows)

    shortfall = pre_claims_count - post_claims_count
    print(f"Sample contains {len(target_utts_rows)} utterances.")
    print(f"  Pre-D1 claims: {pre_claims_count}")
    print(f"  Post-D1 claims in live table: {post_claims_count}")
    print(f"  Shortfall: {shortfall} ({(shortfall / pre_claims_count * 100):.1f}%)")

    # Initialize components
    print("\nInitializing MLX Gemma runtime (v1.6 prompt)...")
    runtime = LocalGemmaRuntime(
        model_id="gemma-3-27b-it",
        prompt_version="v1.6",
        schema_version="s1",
        load_live_backend=True,
    )
    gate = ExtractionGate()
    embedder = Embedder()

    reset_rejection_counts()

    # Trackers
    gate_rejections: Counter[str] = Counter()
    gate_passed = 0
    prompt_empty_count = 0
    total_candidates_emitted = 0
    passed_claims_count = 0

    rejections_by_reason: Counter[str] = Counter()
    all_rejected_records: list[RejectedCandidateRecord] = []
    all_passed_records: list[dict[str, Any]] = []

    # Per-utterance tracking for exact pre vs post comparison
    per_utt_audit: list[dict[str, Any]] = []

    t0 = time.perf_counter()
    print(f"\nProcessing {len(target_utts_rows)} utterances...")

    for idx, (uid, sid, _subj_id, name, _rec_at, _start_ms, _text) in enumerate(
        target_utts_rows, 1
    ):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        utt_pre_claims = [r for r in pre_claims_rows if r[1] == uid]
        utt_pre_count = len(utt_pre_claims)

        # 1. Gate stage
        gate_dec = gate.evaluate_text(utt.text_verbatim)
        if not gate_dec.should_extract:
            gate_rejections[gate_dec.reason] += 1
            per_utt_audit.append(
                {
                    "utterance_id": uid,
                    "pre_claims_count": utt_pre_count,
                    "gate_passed": False,
                    "gate_reason": gate_dec.reason,
                    "candidates_emitted": 0,
                    "passed_claims": 0,
                }
            )
            continue

        gate_passed += 1

        # 2. Model Prompt generation
        gen_stats = runtime.generate_constrained(
            utterance_text=utt.text_verbatim,
            subject_context=f"Speaker: {name}",
            enforce_grammar=True,
        )

        extracted_claims = gen_stats.parsed_result.claims
        candidates_in_utt = len(extracted_claims)
        total_candidates_emitted += candidates_in_utt

        if candidates_in_utt == 0:
            prompt_empty_count += 1

        utt_passed = 0

        # 3. Apply Validators sequentially and capture every rejection reason
        for ec in extracted_claims:
            rejection_reason = None
            validator_stage = None

            # 3.1 Quote Verbatim
            res_quote = validate_quote_verbatim(ec, utt.text_verbatim)
            if not res_quote.is_valid:
                rejection_reason = res_quote.rejection_reason or "quote_verbatim_failed"
                validator_stage = "1_quote_verbatim"
            else:
                # 3.2 Self-Contained (Item W0)
                res_self = validate_self_contained(ec)
                if not res_self.is_valid:
                    rejection_reason = res_self.rejection_reason or "proposition_not_self_contained"
                    validator_stage = "2_self_contained"
                else:
                    # 3.3 Entailment (Validator 6 / Item X1)
                    res_entail = validate_entailment(
                        claim=ec,
                        embedder=embedder,
                        min_quote_tokens=MIN_QUOTE_TOKENS,
                        t_low=T_ENTAIL_LOW,
                        t_high=T_ENTAIL_HIGH,
                    )
                    if not res_entail.is_valid:
                        rejection_reason = (
                            res_entail.rejection_reason or "quote_does_not_support_proposition"
                        )
                        validator_stage = "3_entailment"
                    elif res_entail.status == "quarantined":
                        # Mark as quarantined
                        ec.is_own_assertion = False
                        ec.exclusion_reason = "entailment_ambiguous"
                    else:
                        # 3.4 Stance Direction (Validator 7 / Items S1, D3, D4)
                        res_stance = validate_stance_direction(
                            claim=ec,
                            embedder=embedder,
                            prop_embedding=res_entail.prop_embedding,
                            quote_embedding=res_entail.quote_embedding,
                        )
                        if not res_stance.is_valid:
                            rejection_reason = (
                                res_stance.rejection_reason or "stance_direction_mismatch"
                            )
                            validator_stage = "4_stance_direction"
                        else:
                            # 3.5 Polarity (Item D1)
                            res_pol = validate_polarity(ec)
                            if not res_pol.is_valid:
                                rejection_reason = (
                                    res_pol.rejection_reason or "proposition_carries_polarity"
                                )
                                validator_stage = "5_polarity"
                            else:
                                # 3.6 Speech Acts (Invariant I7)
                                res_sa = validate_speech_acts(ec, utt)
                                if not res_sa.is_valid:
                                    rejection_reason = (
                                        res_sa.rejection_reason or "speech_acts_failed"
                                    )
                                    validator_stage = "6_speech_acts"
                                else:
                                    # 3.7 Confidence Floor
                                    res_conf = validate_confidence_floor(ec, 0.70)
                                    if not res_conf.is_valid:
                                        rejection_reason = (
                                            res_conf.rejection_reason or "confidence_floor_failed"
                                        )
                                        validator_stage = "7_confidence_floor"
                                    else:
                                        # 3.8 Schema
                                        res_schema = validate_schema(ec)
                                        if not res_schema.is_valid:
                                            rejection_reason = (
                                                res_schema.rejection_reason or "schema_failed"
                                            )
                                            validator_stage = "8_schema"

            if rejection_reason is not None:
                rejections_by_reason[rejection_reason] += 1
                all_rejected_records.append(
                    RejectedCandidateRecord(
                        utterance_id=uid,
                        source_id=sid,
                        speaker_name=name,
                        utterance_text=utt.text_verbatim,
                        proposition_text=ec.proposition_text,
                        quote_text=ec.quote_text,
                        stance=ec.stance,
                        hedging_level=ec.hedging_level,
                        is_own_assertion=ec.is_own_assertion,
                        exclusion_reason=ec.exclusion_reason,
                        confidence=ec.confidence,
                        rejection_reason=rejection_reason,
                        validator_stage=validator_stage or "unknown",
                    )
                )
            else:
                passed_claims_count += 1
                utt_passed += 1
                all_passed_records.append(
                    {
                        "utterance_id": uid,
                        "proposition_text": ec.proposition_text,
                        "quote_text": ec.quote_text,
                        "stance": ec.stance,
                        "status": res_entail.status,
                    }
                )

        per_utt_audit.append(
            {
                "utterance_id": uid,
                "pre_claims_count": utt_pre_count,
                "gate_passed": True,
                "candidates_emitted": candidates_in_utt,
                "passed_claims": utt_passed,
            }
        )

        if idx % 25 == 0 or idx == len(target_utts_rows):
            el = time.perf_counter() - t0
            rate = idx / el if el > 0 else 0
            eta_m = (len(target_utts_rows) - idx) / rate / 60 if rate > 0 else 0
            print(
                f"  [{idx:3d}/{len(target_utts_rows)}] candidates: {total_candidates_emitted} | passed: {passed_claims_count} | rejected: {len(all_rejected_records)} | {rate:.2f} utts/s | ETA: {eta_m:.1f}m",
                flush=True,
            )

    elapsed = time.perf_counter() - t0
    print(f"\nCompleted 300 utterances in {elapsed:.1f}s ({elapsed / 60:.2f}m).")

    # Summary of Rejection Counters
    print("\n=== VALIDATOR REJECTION COUNTERS ===")
    total_rejections = sum(rejections_by_reason.values())
    for reason, count in rejections_by_reason.most_common():
        print(f"  {reason}: {count}")
    print(f"  Total Candidate Rejections: {total_rejections}")

    print("\n=== GATE REJECTIONS ===")
    total_gate_rejections = sum(gate_rejections.values())
    for reason, count in gate_rejections.most_common():
        print(f"  {reason}: {count}")
    print(f"  Total Gate Rejections: {total_gate_rejections}")

    print("\n=== ARITHMETIC RECONCILIATION ===")
    print("1. Candidate Level:")
    print(f"   Total candidates emitted: {total_candidates_emitted}")
    print(f"   Passed claims:            {passed_claims_count}")
    print(f"   Rejected candidates:      {total_rejections}")
    candidate_check = passed_claims_count + total_rejections
    print(
        f"   Sum (passed + rejected):  {candidate_check} (Difference: {total_candidates_emitted - candidate_check})"
    )

    # Pre-D1 vs Post-D1 claim reconciliation
    lost_to_gate_claims = sum(u["pre_claims_count"] for u in per_utt_audit if not u["gate_passed"])
    lost_to_empty_prompt_claims = sum(
        u["pre_claims_count"]
        for u in per_utt_audit
        if u["gate_passed"] and u["candidates_emitted"] == 0
    )
    prompt_candidate_shortfall = sum(
        max(0, u["pre_claims_count"] - u["candidates_emitted"])
        for u in per_utt_audit
        if u["gate_passed"] and u["candidates_emitted"] > 0
    )
    measured_shortfall = pre_claims_count - passed_claims_count

    print("\n2. Pre-D1 Claim Shortfall Analysis:")
    print(f"   Pre-D1 claims:                       {pre_claims_count}")
    print(f"   Post-D1 passed claims:               {passed_claims_count}")
    print(f"   Net Shortfall:                       {measured_shortfall}")
    print(f"   - Claims lost to gate:               {lost_to_gate_claims}")
    print(f"   - Claims lost to empty prompt:       {lost_to_empty_prompt_claims}")
    print(f"   - Prompt candidate shortfall:        {prompt_candidate_shortfall}")
    print(f"   - Candidates rejected by validators: {total_rejections}")

    audit_data = {
        "metadata": {
            "sample_size": len(target_utts_rows),
            "pre_claims_count": pre_claims_count,
            "post_claims_live_count": post_claims_count,
            "passed_claims_reextracted": passed_claims_count,
            "shortfall": measured_shortfall,
            "total_candidates_emitted": total_candidates_emitted,
            "total_rejections": total_rejections,
            "gate_rejections": dict(gate_rejections),
            "prompt_empty_count": prompt_empty_count,
            "rejections_by_reason": dict(rejections_by_reason),
            "elapsed_seconds": elapsed,
        },
        "rejected_records": [asdict(r) for r in all_rejected_records],
        "passed_records": all_passed_records,
        "per_utt_audit": per_utt_audit,
    }

    out_p = Path(output_json)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)
    print(f"\nSaved audit details and rejected records to {out_p}")

    return audit_data


if __name__ == "__main__":
    run_sample_audit()
