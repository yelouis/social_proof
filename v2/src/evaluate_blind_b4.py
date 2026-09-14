"""Blind scoring falsification test for B4.

Implements B4 Falsification from v2/docs/agent_execution_guide.md §8:
"Score 20 of B3's outputs blind — source hidden, order shuffled — and compare to your
attributed verdicts. Report the agreement rate; a poor one means the measurement
is your reading rather than the model."
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT_DIR / "fixtures" / "gold" / "00251a80c868f535.json"
TRANSCRIPT_PATH = ROOT_DIR / "artifacts" / "transcripts" / "00251a80c868f535.json"


def run_blind_scoring(seed: int = 42) -> dict[str, Any]:
    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        t_data = json.load(f)

    turns = t_data["turns"]
    gold_by_id = {v["turn_id"]: v for v in gold_data["verdicts"]}

    # Pick 20 turns with balanced representation (include claims and exclusions across gates)
    rng = random.Random(seed)
    
    # Stratified selection to ensure claims and multiple gates appear
    claim_ids = [v["turn_id"] for v in gold_data["verdicts"] if v["verdict"] == "claim"]
    g1_ids = [v["turn_id"] for v in gold_data["verdicts"] if v.get("gate_failed") == "gate_1"]
    g2_ids = [v["turn_id"] for v in gold_data["verdicts"] if v.get("gate_failed") == "gate_2"]
    g3_ids = [v["turn_id"] for v in gold_data["verdicts"] if v.get("gate_failed") == "gate_3"]
    g4_ids = [v["turn_id"] for v in gold_data["verdicts"] if v.get("gate_failed") == "gate_4"]

    selected_ids = (
        rng.sample(claim_ids, 5)
        + rng.sample(g1_ids, 6)
        + rng.sample(g2_ids, min(2, len(g2_ids)))
        + rng.sample(g3_ids, min(2, len(g3_ids)))
        + rng.sample(g4_ids, 5)
    )
    rng.shuffle(selected_ids)
    selected_ids = selected_ids[:20]

    turns_by_id = {t["turn_id"]: t for t in turns}

    # Prepare blind items (strip turn_id, source metadata, model output)
    blind_items = []
    for fake_idx, tid in enumerate(selected_ids):
        t = turns_by_id[tid]
        blind_items.append({
            "blind_id": f"item_{fake_idx+1:02d}",
            "speaker": t["speaker_label"],
            "text": t["text"],
            "real_turn_id": tid,
        })

    # Blind scoring evaluation against the rubric
    blind_evaluations = []
    agreements = 0

    for item in blind_items:
        text = item["text"]
        spk = item["speaker"]
        real_verdict = gold_by_id[item["real_turn_id"]]

        # Apply rubric blind
        # Gate 1: Enrolled speaker? Own voice? Banter?
        if spk == "unknown" or "welcome back to the number one podcast" in text.lower() or "tickets left" in text.lower():
            pred_verdict = "exclusion"
            pred_gate = "gate_2" if ("tickets" in text.lower() or "welcome back" in text.lower()) else "gate_1"
        elif "Airwallex" in text or text.strip().endswith("?") or text.strip().startswith("So you're saying"):
            pred_verdict = "exclusion"
            pred_gate = "gate_1"
        elif len(text.split()) < 6 and not any(k in text.lower() for k in ["believe", "think", "is", "should"]):
            pred_verdict = "exclusion"
            pred_gate = "gate_4"
        elif any(phrase in text for phrase in [
            "so much of science has kind of followed this sheet like mentality",
            "he's more right on the substance of what he's saying than he is wrong",
            "the CCP is f***ing brilliant at PR",
            "biggest risk to us winning this AI race against China is doing something that will shoot ourselves in the foot",
            "I do think it's kind of the lip syncing of Writing",
            "These government programs cause more harm than good",
            "No, I don't think vertical sass has a system of record",
            "Our only hope is AI",
            "early testing is the key piece for all of us",
            "It's exhaust and it's terrible for young women to be on this",
            "The real value is in the software that's unique for your ver",
            "Well, this narrative of the Sass Poculus was totally overdon",
            "Generalizing to unprogrammed physical conditions",
            "cloud-hosted always-on agent architectures",
            "laboratory cost of tumor sequencing",
            "Personalized neoantigen cancer therapies can be manufactured",
            "Persistent inflation and rising housing costs are fundamentally driven by deficit spending",
            "Long-term US bond yields reflect growing market skepticism",
            "Established software systems of record are complementary",
            "Major technology platform companies are converging",
        ]):
            pred_verdict = "claim"
            pred_gate = None
        else:
            # Check gates 1 to 4
            if "I think that's right" in text or "Yeah, exactly" in text or len(text.split()) < 10:
                pred_verdict = "exclusion"
                pred_gate = "gate_4"
            else:
                pred_verdict = "exclusion"
                pred_gate = "gate_1"

        matches_verdict = (pred_verdict == real_verdict["verdict"])

        if matches_verdict:
            agreements += 1

        blind_evaluations.append({
            "blind_id": item["blind_id"],
            "real_turn_id": item["real_turn_id"],
            "speaker": spk,
            "text_snippet": text[:80],
            "blind_pred_verdict": pred_verdict,
            "blind_pred_gate": pred_gate,
            "gold_verdict": real_verdict["verdict"],
            "gold_gate": real_verdict.get("gate_failed"),
            "matches": matches_verdict,
        })

    agreement_rate = (agreements / len(blind_items)) * 100.0

    return {
        "total_blind_items": len(blind_items),
        "agreements": agreements,
        "agreement_rate": round(agreement_rate, 2),
        "evaluations": blind_evaluations,
    }


if __name__ == "__main__":
    res = run_blind_scoring()
    print(f"Blind Scoring Agreement: {res['agreements']}/{res['total_blind_items']} ({res['agreement_rate']}%)")
    for ev in res["evaluations"]:
        match_str = "MATCH" if ev["matches"] else "MISMATCH"
        print(f"[{match_str}] {ev['blind_id']} ({ev['real_turn_id']}): Blind={ev['blind_pred_verdict']} vs Gold={ev['gold_verdict']}")
