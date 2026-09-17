"""Generates the Tier 2 perturbation dataset (40 items: 5 per axis * 8 axes).

Takes real, high-scoring claims from E287 and damages them in one known way each,
paired with their unperturbed originals.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRANSCRIPT_FILE = REPO_ROOT / "v2" / "artifacts" / "transcripts" / "00251a80c868f535.json"
SCORED_AXES_FILE = REPO_ROOT / "v2" / "artifacts" / "extraction" / "c4_scored_axes_00251a80c868f535.json"
OUTPUT_FILE = REPO_ROOT / "v2" / "fixtures" / "axes" / "perturbations.json"


def build_perturbations() -> list[dict[str, str]]:
    with open(SCORED_AXES_FILE, "r", encoding="utf-8") as f:
        c4_data = json.load(f)
    scored_claims = {c["turn_id"]: c for c in c4_data["scored_claims"]}

    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        t_data = json.load(f)
    turns = {t["turn_id"]: t for t in t_data.get("turns", [])}

    def get_info(tid: str) -> tuple[str, str, str, str]:
        c = scored_claims[tid]
        t = turns[tid]
        return c["speaker"], c["quote"], c["claim"], t["text"]

    perturbations: list[dict[str, str]] = []

    # 1. Voice (5 pairs) -> rewritten as question / unattributed hearsay
    voice_tids = [
        ("00251a80c868f535_t0030", "Is the Chinese Communist Party brilliant at public relations?"),
        ("00251a80c868f535_t0053", "Will Tesla's Optimus robot be the best selling product in history?"),
        ("00251a80c868f535_t0084", "Was Salesforce meaningfully oversold in May?"),
        ("00251a80c868f535_t0101", "Are core systems of record like CRM not going to be replaced?"),
        ("00251a80c868f535_t0154", "Is the United States Congress completely unable to do anything about fiscal deficits?"),
    ]
    for idx, (tid, pert) in enumerate(voice_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"voice_{idx:02d}",
            "target_axis": "voice",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Rewritten as an interrogative question rather than a speaker-committed assertion.",
        })

    # 2. Target (5 pairs) -> replaced with podcast show-mechanics statement
    target_tids = [
        ("00251a80c868f535_t0009", "We have a great episode lined up for all our podcast listeners today."),
        ("00251a80c868f535_t0015", "Let's welcome David Friedberg back to the podcast discussion."),
        ("00251a80c868f535_t0040", "Thanks to our studio audio engineer for fixing the microphone audio levels."),
        ("00251a80c868f535_t0081", "Before we move to our next segment, let's take a quick commercial break."),
        ("00251a80c868f535_t0091", "You can find all of today's show notes and episode links in the podcast description."),
    ]
    for idx, (tid, pert) in enumerate(target_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"target_{idx:02d}",
            "target_axis": "target",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced external world claim with conversational show-mechanics / podcast meta statement.",
        })

    # 3. Propositionality (5 pairs) -> replaced with bare noun phrase / unasserted topic
    prop_tids = [
        ("00251a80c868f535_t0016", "Enterprise AI deployment and organizational workflow integration."),
        ("00251a80c868f535_t0019", "Academic peer review practices and scientific grant allocation."),
        ("00251a80c868f535_t0055", "Humanoid robotics development challenges in unprogrammed physical environments."),
        ("00251a80c868f535_t0095", "Vertical software market dynamics and cloud infrastructure pricing."),
        ("00251a80c868f535_t0105", "Autonomous software agents in workflow automation and execution."),
    ]
    for idx, (tid, pert) in enumerate(prop_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"propositionality_{idx:02d}",
            "target_axis": "propositionality",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced propositional clause with a bare noun phrase topic devoid of a truth-evaluable predicate.",
        })

    # 4. Contestability (5 pairs) -> replaced with tautology or undisputed definitional fact
    cont_tids = [
        ("00251a80c868f535_t0116", "Until string theory is proven true, it remains unproven."),
        ("00251a80c868f535_t0122", "If a commercial investment generates profits, then it is profitable."),
        ("00251a80c868f535_t0123", "A corporation that operates in business commerce is an enterprise."),
        ("00251a80c868f535_t0125", "Manufactured products that are purchased by customers have buyers."),
        ("00251a80c868f535_t0133", "A competitive marketplace consists of market participants who compete."),
    ]
    for idx, (tid, pert) in enumerate(cont_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"contestability_{idx:02d}",
            "target_axis": "contestability",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced contestable stance with an undisputed tautology / definitional truism.",
        })

    # 5. Typing (5 pairs) -> replaced with conversational filler / mush
    type_tids = [
        ("00251a80c868f535_t0138", "I think that is totally right."),
        ("00251a80c868f535_t0140", "Yeah, that is exactly what I was thinking too."),
        ("00251a80c868f535_t0141", "A hundred percent, I definitely agree with your point."),
        ("00251a80c868f535_t0142", "That makes a whole lot of sense to me."),
        ("00251a80c868f535_t0156", "Right on, I totally see where you are coming from on that."),
    ]
    for idx, (tid, pert) in enumerate(type_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"typing_{idx:02d}",
            "target_axis": "typing",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced typed stance claim with conversational agreement filler devoid of clear claim type.",
        })

    # 6. Decontextualisation (5 pairs) -> replaced subject with unbound pronoun
    decontext_tids = [
        ("00251a80c868f535_t0084", "It was meaningfully oversold in May."),
        ("00251a80c868f535_t0053", "It will be the best selling product in history."),
        ("00251a80c868f535_t0160", "They will force this to confront its debt."),
        ("00251a80c868f535_t0176", "They are going to have to implement this."),
        ("00251a80c868f535_t0179", "It will not have any money to pay by then."),
    ]
    for idx, (tid, pert) in enumerate(decontext_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"decontextualisation_{idx:02d}",
            "target_axis": "decontextualisation",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced resolved named entities with unbound pronouns / indexicals.",
        })

    # 7. Fidelity (5 pairs) -> swapped claim for assertion quote does not support
    fidelity_tids = [
        ("00251a80c868f535_t0181", "Tesla's Optimus robot will be the best selling product in history."),
        ("00251a80c868f535_t0183", "The Chinese Communist Party is brilliant at public relations."),
        ("00251a80c868f535_t0185", "Persistent inflation is caused by excess government money printing."),
        ("00251a80c868f535_t0187", "Salesforce was meaningfully oversold in May."),
        ("00251a80c868f535_t0192", "Much of academic science enforces conformity around mainstream theories."),
    ]
    for idx, (tid, pert) in enumerate(fidelity_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"fidelity_{idx:02d}",
            "target_axis": "fidelity",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Replaced claim with an assertion about an entirely different topic completely unsupported by quote.",
        })

    # 8. Granularity (5 pairs) -> concatenated two unrelated claims with 'and'
    granularity_tids = [
        ("00251a80c868f535_t0104", "David Sacks is one of the most underestimated operators in Silicon Valley, and the Chinese Communist Party is brilliant at public relations."),
        ("00251a80c868f535_t0109", "Vertical SaaS does not have a proprietary system of record, and Salesforce was meaningfully oversold in May."),
        ("00251a80c868f535_t0166", "If the 30-year Treasury yield reaches 6%, it is the beginning of the end for sovereign debt, and Tesla's Optimus robot will be the best selling product in history."),
        ("00251a80c868f535_t0173", "If Republicans lose control of Congress, government spending will accelerate, and persistent inflation is caused by excess government deficits."),
        ("00251a80c868f535_t0195", "Socialism was much more likely 100 years ago when wealth was visible, and there is a level of corruption in scientific grant funding apparatus."),
    ]
    for idx, (tid, pert) in enumerate(granularity_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"granularity_{idx:02d}",
            "target_axis": "granularity",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert,
            "perturbation_description": "Compound claim concatenating two distinct independent claims from different turns with 'and'.",
        })

    return perturbations


def main() -> None:
    perts = build_perturbations()
    assert len(perts) == 40, f"Expected 40 perturbations, got {len(perts)}"
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(perts, f, indent=2)
    print(f"Saved {len(perts)} perturbations to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
