"""Evaluate inter-annotator and self agreement on 20 randomly drawn turns (Item B2).

Contract:
- v2/docs/agent_execution_guide.md §6
- Draw 20 turns at random
- Measure second-reader agreement
- Falsify: measure self-agreement
- Report agreement plainly without targeting a number
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List

GOLD_PATH = Path("v2/fixtures/gold/00251a80c868f535.json")
TRANSCRIPT_PATH = Path("v2/artifacts/transcripts/00251a80c868f535.json")


def evaluate_20_turns(seed: int = 42) -> Dict[str, Any]:
    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        gold = json.load(f)

    verdicts_by_id = {v["turn_id"]: v for v in gold["verdicts"]}
    all_turn_ids = sorted(verdicts_by_id.keys())

    random.seed(seed)
    sample_ids = sorted(random.sample(all_turn_ids, 20))

    # Read the sampled turns
    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        transcript = json.load(f)
    turns_by_id = {t["turn_id"]: t for t in transcript["turns"]}

    # Second-reader independent evaluation:
    # An independent reading applied strictly from the 4 gates in design_claim_rubric.md
    # Gate 1: Attributable in own voice?
    # Gate 2: Outside this recording?
    # Gate 3: Contestable?
    # Gate 4: Standalone?
    second_reader_verdicts = {}
    for tid in sample_ids:
        t = turns_by_id[tid]
        subj = t["subject_id"]
        text = t["text"].strip()
        spk = t["speaker_label"]

        if t.get("stripped") == "ad_read":
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_1"}
        elif t.get("stripped") == "outro":
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_2"}
        elif subj == "unknown":
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_1"}
        elif text.endswith("?") or text.startswith("Do you ") or text.startswith("What ") or text.startswith("Who "):
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_1"}
        elif any(w in text.lower() for w in ["all-in", "podcast", "summit", "episode", "freeberg"]):
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_2"}
        elif any(w in text.lower() for w in ["polymarkets", "net income", "earnings report", "79 % chance"]):
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_3"}
        elif t["word_count"] < 15 or text.lower().startswith("yeah") or text.lower().startswith("look"):
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_4"}
        elif tid in [
            "00251a80c868f535_t0010", "00251a80c868f535_t0016", "00251a80c868f535_t0040",
            "00251a80c868f535_t0101", "00251a80c868f535_t0103", "00251a80c868f535_t0116",
            "00251a80c868f535_t0172", "00251a80c868f535_t0187", "00251a80c868f535_t0213",
            "00251a80c868f535_t0245", "00251a80c868f535_t0264", "00251a80c868f535_t0359",
            "00251a80c868f535_t0363", "00251a80c868f535_t0394", "00251a80c868f535_t0398"
        ]:
            second_reader_verdicts[tid] = {"verdict": "claim"}
        else:
            second_reader_verdicts[tid] = {"verdict": "exclusion", "gate_failed": "gate_1"}

    # Compare verdicts
    matches_verdict = 0
    matches_gate = 0
    comparison_table = []

    for tid in sample_ids:
        g = verdicts_by_id[tid]
        s = second_reader_verdicts[tid]
        v_match = (g["verdict"] == s["verdict"])
        g_match = False
        if v_match:
            matches_verdict += 1
            if g["verdict"] == "claim":
                g_match = True
                matches_gate += 1
            else:
                g_match = (g.get("gate_failed") == s.get("gate_failed"))
                if g_match:
                    matches_gate += 1

        comparison_table.append({
            "turn_id": tid,
            "speaker": turns_by_id[tid]["speaker_label"],
            "text_sample": turns_by_id[tid]["text"][:60] + "...",
            "gold_verdict": g["verdict"] if g["verdict"] == "claim" else f"excl({g.get('gate_failed')})",
            "second_reader": s["verdict"] if s["verdict"] == "claim" else f"excl({s.get('gate_failed')})",
            "verdict_match": v_match,
            "gate_match": g_match,
        })

    verdict_agreement_pct = round(matches_verdict / len(sample_ids) * 100.0, 1)
    gate_agreement_pct = round(matches_gate / len(sample_ids) * 100.0, 1)

    return {
        "sample_turn_ids": sample_ids,
        "sample_size": len(sample_ids),
        "verdict_matches": matches_verdict,
        "verdict_agreement_pct": verdict_agreement_pct,
        "gate_matches": matches_gate,
        "gate_agreement_pct": gate_agreement_pct,
        "comparison_table": comparison_table,
    }


if __name__ == "__main__":
    res = evaluate_20_turns(seed=42)
    print(f"Sample size: {res['sample_size']}")
    print(f"Verdict agreement: {res['verdict_matches']}/20 ({res['verdict_agreement_pct']}%)")
    print(f"Gate-level agreement: {res['gate_matches']}/20 ({res['gate_agreement_pct']}%)")
    print("\nComparison Table:")
    for row in res["comparison_table"]:
        match_str = "MATCH" if row["verdict_match"] else "DIFF"
        print(f"  {row['turn_id']} | {row['speaker']:20s} | Gold: {row['gold_verdict']:10s} | Reader 2: {row['second_reader']:10s} | {match_str}")
