"""Generates the Tier 2 perturbation dataset (40 items: 5 per axis * 8 axes).

Takes real, high-scoring claims from E287 and damages them in one known way each,
paired with their unperturbed originals.
For Speaker panel axes, the turn text and quote match the speaker perturbation
so that Fidelity remains high while the targeted speaker property is isolated.
For Extraction panel axes, the speaker turn and quote are unchanged, and the
extracted claim is damaged in decontextualisation, granularity, or fidelity.
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

    # 1. Voice (5 pairs) -> rewritten as interrogative question / reporting
    voice_tids = [
        (
            "00251a80c868f535_t0030",
            "Is the Chinese Communist Party brilliant at public relations?",
            "Is the Chinese Communist Party brilliant at public relations?",
            "Is the Chinese Communist Party brilliant at public relations? What do you think about that, Chamath?",
        ),
        (
            "00251a80c868f535_t0053",
            "Will Tesla's Optimus robot be the best selling product in history?",
            "Will Tesla's Optimus robot be the best selling product in history?",
            "Do you really think Optimus will be the best selling product in history, or is it just hype?",
        ),
        (
            "00251a80c868f535_t0084",
            "Was Salesforce meaningfully oversold in May?",
            "Was Salesforce meaningfully oversold in May?",
            "I wonder, was Salesforce meaningfully oversold back in May?",
        ),
        (
            "00251a80c868f535_t0101",
            "Are core systems of record like CRM not going to be replaced?",
            "Are core systems of record like CRM not going to be replaced?",
            "Are core systems of record like CRM going to get ripped out, or are they here to stay?",
        ),
        (
            "00251a80c868f535_t0154",
            "Is the United States Congress completely unable to get budget deficits under control?",
            "Is the United States Congress completely unable to get budget deficits under control?",
            "Is Congress completely unable to do anything to get these budget deficits under control?",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn) in enumerate(voice_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"voice_{idx:02d}",
            "target_axis": "voice",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert_claim,
            "perturbed_quote": pert_quote,
            "perturbed_turn_text": pert_turn,
            "perturbation_description": "Rewritten as an interrogative question rather than a speaker-committed assertion.",
        })

    # 2. Target (5 pairs) -> podcast show-mechanics statement
    target_tids = [
        (
            "00251a80c868f535_t0009",
            "The All-In podcast has a great episode lined up for all listeners today.",
            "We have a great episode lined up for all our podcast listeners today",
            "We have a great episode lined up for all our podcast listeners today. Thanks for tuning into the show.",
        ),
        (
            "00251a80c868f535_t0015",
            "David Friedberg is being welcomed back to the podcast discussion.",
            "Let's welcome David Friedberg back to the podcast discussion",
            "Let's welcome David Friedberg back to the podcast discussion after his quick break.",
        ),
        (
            "00251a80c868f535_t0040",
            "The studio audio engineer fixed the microphone audio levels.",
            "Thanks to our studio audio engineer for fixing the microphone audio levels",
            "Thanks to our studio audio engineer for fixing the microphone audio levels so we could start recording.",
        ),
        (
            "00251a80c868f535_t0081",
            "The podcast is taking a commercial break before the next segment.",
            "Before we move to our next segment, let's take a quick commercial break",
            "Before we move to our next segment, let's take a quick commercial break for our sponsors.",
        ),
        (
            "00251a80c868f535_t0091",
            "Listeners can find all show notes and links in the podcast description.",
            "You can find all of today's show notes and episode links in the podcast description",
            "You can find all of today's show notes and episode links in the podcast description below.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn) in enumerate(target_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"target_{idx:02d}",
            "target_axis": "target",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert_claim,
            "perturbed_quote": pert_quote,
            "perturbed_turn_text": pert_turn,
            "perturbation_description": "Replaced external world claim with conversational show-mechanics / podcast meta statement.",
        })

    # 3. Propositionality (5 pairs) -> bare noun phrase topic devoid of predicate
    prop_tids = [
        (
            "00251a80c868f535_t0016",
            "Enterprise AI deployment and organizational workflow integration.",
            "enterprise AI deployment and organizational workflow integration",
            "Next topic on the docket: enterprise AI deployment and organizational workflow integration in enterprises.",
        ),
        (
            "00251a80c868f535_t0019",
            "Academic peer review practices and scientific grant allocation.",
            "academic peer review practices and scientific grant allocation",
            "Moving along to academic peer review practices and scientific grant allocation in modern research.",
        ),
        (
            "00251a80c868f535_t0055",
            "Humanoid robotics development challenges in physical environments.",
            "humanoid robotics development challenges in physical environments",
            "Now concerning humanoid robotics development challenges in physical environments today.",
        ),
        (
            "00251a80c868f535_t0095",
            "Vertical software market dynamics and cloud infrastructure pricing.",
            "vertical software market dynamics and cloud infrastructure pricing",
            "Our next segment: vertical software market dynamics and cloud infrastructure pricing across vendors.",
        ),
        (
            "00251a80c868f535_t0105",
            "Autonomous software agents in workflow automation and execution.",
            "autonomous software agents in workflow automation and execution",
            "Regarding autonomous software agents in workflow automation and execution across industry domains.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn) in enumerate(prop_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"propositionality_{idx:02d}",
            "target_axis": "propositionality",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert_claim,
            "perturbed_quote": pert_quote,
            "perturbed_turn_text": pert_turn,
            "perturbation_description": "Replaced propositional clause with a bare noun phrase topic devoid of a truth-evaluable predicate.",
        })

    # 4. Contestability (5 pairs) -> undisputed tautology / definitional truism
    cont_tids = [
        (
            "00251a80c868f535_t0116",
            "Until string theory is proven true, it remains unproven.",
            "until string theory is mathematically proved, it remains unproved",
            "As everyone knows, until string theory is mathematically proved, it remains unproved. That is simply a logical fact.",
        ),
        (
            "00251a80c868f535_t0122",
            "If a commercial investment generates profits, then it is profitable.",
            "if an investment makes a profit, then it is profitable",
            "By definition, if an investment makes a profit, then it is profitable, obviously.",
        ),
        (
            "00251a80c868f535_t0123",
            "A corporation that operates in business commerce is an enterprise.",
            "a corporation operating in business is an enterprise",
            "Well of course, a corporation operating in business is an enterprise by the dictionary definition.",
        ),
        (
            "00251a80c868f535_t0125",
            "Manufactured products that are purchased by customers have buyers.",
            "products that get bought have buyers",
            "That's like saying products that get bought have buyers—it is completely obvious.",
        ),
        (
            "00251a80c868f535_t0133",
            "A competitive marketplace consists of market participants who compete.",
            "a competitive market consists of competitors",
            "Naturally, a competitive market consists of competitors competing against one another.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn) in enumerate(cont_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"contestability_{idx:02d}",
            "target_axis": "contestability",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert_claim,
            "perturbed_quote": pert_quote,
            "perturbed_turn_text": pert_turn,
            "perturbation_description": "Replaced contestable stance with an undisputed tautology / definitional truism.",
        })

    # 5. Typing (5 pairs) -> conversational filler / agreement mush
    type_tids = [
        (
            "00251a80c868f535_t0138",
            "I think that is totally right.",
            "I think that's right",
            "Yeah, absolutely. I think that's right. I agree with you completely on that.",
        ),
        (
            "00251a80c868f535_t0140",
            "Yeah, that is exactly what I was thinking too.",
            "that is exactly what I was thinking too",
            "Totally, that is exactly what I was thinking too, 100 percent.",
        ),
        (
            "00251a80c868f535_t0141",
            "A hundred percent, I definitely agree with your point.",
            "A hundred percent, I definitely agree with your point",
            "A hundred percent, I definitely agree with your point, man.",
        ),
        (
            "00251a80c868f535_t0142",
            "That makes a whole lot of sense to me.",
            "That makes a whole lot of sense to me",
            "Yeah, I hear you. That makes a whole lot of sense to me.",
        ),
        (
            "00251a80c868f535_t0156",
            "Right on, I totally see where you are coming from on that.",
            "I totally see where you are coming from on that",
            "Right on, I totally see where you are coming from on that, Jason.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn) in enumerate(type_tids, start=1):
        spk, q, orig, txt = get_info(tid)
        perturbations.append({
            "id": f"typing_{idx:02d}",
            "target_axis": "typing",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig,
            "perturbed_claim": pert_claim,
            "perturbed_quote": pert_quote,
            "perturbed_turn_text": pert_turn,
            "perturbation_description": "Replaced typed stance claim with conversational agreement filler devoid of clear claim type.",
        })

    # 6. Decontextualisation (5 pairs) -> replaced subject with unbound pronoun
    decontext_tids = [
        ("00251a80c868f535_t0084", "The individual discussed was meaningfully oversold in May."),
        ("00251a80c868f535_t0053", "They are going to build the best selling product in history."),
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
            "perturbed_quote": q,
            "perturbed_turn_text": txt,
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
            "perturbed_quote": q,
            "perturbed_turn_text": txt,
            "perturbation_description": "Replaced claim with an assertion about an entirely different topic completely unsupported by quote.",
        })

    # 8. Granularity (5 pairs) -> concatenated two unrelated claims with 'and'
    granularity_tids = [
        ("00251a80c868f535_t0104", "David Sacks is one of the most underestimated operators in Silicon Valley, and the Chinese Communist Party is brilliant at public relations."),
        ("00251a80c868f535_t0109", "Vertical SaaS does not have a proprietary system of record, and Salesforce was meaningfully oversold in May."),
        ("00251a80c868f535_t0166", "If the 30-year Treasury yield reaches 6%, it is the beginning of the end for sovereign debt, and Tesla's Optimus robot will be the best selling product in history."),
        ("00251a80c868f535_t0173", "Salesforce was meaningfully oversold in May, and the Chinese Communist Party is brilliant at public relations."),
        ("00251a80c868f535_t0195", "Tesla Optimus robot will be the best selling product in history, and academic science enforces conformity around mainstream theories."),
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
            "perturbed_quote": q,
            "perturbed_turn_text": txt,
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
