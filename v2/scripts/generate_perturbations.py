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

    # 1. Voice (5 pairs) -> reported / attributed assertion (Voice=0/1 while preserving Target=2, Prop=2)
    voice_tids = [
        (
            "00251a80c868f535_t0030",
            "Critics and commentators argue that the Chinese Communist Party is brilliant at PR.",
            "Critics and commentators argue that the Chinese Communist Party is brilliant at PR",
            "I heard some critics and commentators argue that the Chinese Communist Party is brilliant at PR, but that's just their reporting.",
            "Attributed to outside critics/commentators without personal speaker endorsement.",
        ),
        (
            "00251a80c868f535_t0053",
            "Elon Musk has claimed that Tesla's Optimus robot will be the best selling product in history.",
            "Elon Musk has claimed that Tesla's Optimus robot will be the best selling product in history",
            "Well, Elon Musk has claimed that Tesla's Optimus robot will be the best selling product in history, that's his claim.",
            "Reported claim attributed to an external subject without personal endorsement.",
        ),
        (
            "00251a80c868f535_t0084",
            "Some market analysts reported that Salesforce was meaningfully oversold in May.",
            "Some market analysts reported that Salesforce was meaningfully oversold in May",
            "I saw where some market analysts reported that Salesforce was meaningfully oversold in May, according to their notes.",
            "Reported analysis attributed to external third parties.",
        ),
        (
            "00251a80c868f535_t0101",
            "Industry observers speculate that core systems of record like CRM might eventually be replaced.",
            "Industry observers speculate that core systems of record like CRM might eventually be replaced",
            "There are industry observers who speculate that core systems of record like CRM might eventually be replaced, though that is their speculation and not my view.",
            "Reported third-party speculation without personal speaker endorsement.",
        ),
        (
            "00251a80c868f535_t0154",
            "Television pundits frequently argue that Congress is completely unable to get budget deficits under control.",
            "Television pundits frequently argue that Congress is completely unable to get budget deficits under control",
            "Television pundits frequently argue that Congress is completely unable to get budget deficits under control, as they often say on television, but that is their claim, not mine.",
            "Attributed to television pundits without personal speaker commitment.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn, desc) in enumerate(voice_tids, start=1):
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
            "perturbation_description": desc,
        })

    # 2. Target (5 pairs) -> subjective, contestable own-voice claim about the show itself (Target=0/1, Voice=2, Cont=2)
    target_tids = [
        (
            "00251a80c868f535_t0009",
            "The All-In podcast is currently the most insightful technology show in digital media.",
            "the All-In podcast is currently the most insightful technology show in digital media",
            "I really believe the All-In podcast is currently the most insightful technology show in digital media, bar none.",
            "Contestable evaluative claim about the podcast show itself rather than external world dynamics.",
        ),
        (
            "00251a80c868f535_t0015",
            "Our podcast panel has analyzed macroeconomic shifts much more accurately than the mainstream financial press.",
            "our podcast panel has analyzed macroeconomic shifts much more accurately than the mainstream financial press",
            "I think our podcast panel has analyzed macroeconomic shifts much more accurately than the mainstream financial press over the last two years.",
            "Contestable comparative claim about the show's panel rather than external entities.",
        ),
        (
            "00251a80c868f535_t0040",
            "The All-In podcast live summit in Los Angeles will be the single most successful live event in the podcast's history.",
            "the All-In podcast live summit in Los Angeles will be the single most successful live event in the podcast's history",
            "I guarantee the All-In podcast live summit in Los Angeles will be the single most successful live event in the podcast's history.",
            "Contestable predictive forecast about the podcast's own upcoming live event.",
        ),
        (
            "00251a80c868f535_t0081",
            "Our podcast discussion today will completely change how venture capitalists evaluate early-stage software startups.",
            "our podcast discussion today will completely change how venture capitalists evaluate early-stage software startups",
            "Mark my words, our podcast discussion today will completely change how venture capitalists evaluate early-stage software startups.",
            "Contestable prediction about the impact of the podcast episode itself.",
        ),
        (
            "00251a80c868f535_t0091",
            "This episode of the All-In podcast is the definitive historical breakdown of the Silicon Valley Bank collapse.",
            "this episode of the All-In podcast is the definitive historical breakdown of the Silicon Valley Bank collapse",
            "In my opinion, this episode of the All-In podcast is the definitive historical breakdown of the Silicon Valley Bank collapse.",
            "Contestable evaluative claim about the episode rather than the banking collapse itself.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn, desc) in enumerate(target_tids, start=1):
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
            "perturbation_description": desc,
        })

    # 3. Propositionality (5 pairs) -> thin assertion with minimal predicate depth (Propositionality=1, Voice=2, Cont=2)
    prop_tids = [
        (
            "00251a80c868f535_t0016",
            "Artificial intelligence is a very big deal in enterprise software.",
            "artificial intelligence is a very big deal in enterprise software",
            "In my view, artificial intelligence is a very big deal in enterprise software right now.",
            "Thin assertion carrying minimal mechanistic predicate, scoring 1 on propositionality.",
        ),
        (
            "00251a80c868f535_t0019",
            "Academic peer review practices are remarkably important in scientific research.",
            "academic peer review practices are remarkably important in scientific research",
            "I maintain that academic peer review practices are remarkably important in scientific research.",
            "Thin assertion of generic importance lacking a specific predicate mechanism.",
        ),
        (
            "00251a80c868f535_t0055",
            "Humanoid robotics development is a notable engineering pursuit.",
            "humanoid robotics development is a notable engineering pursuit",
            "We all know humanoid robotics development is a notable engineering pursuit today.",
            "Thin evaluative assertion with low propositional content.",
        ),
        (
            "00251a80c868f535_t0095",
            "Vertical software market dynamics matter a lot in modern technology.",
            "vertical software market dynamics matter a lot in modern technology",
            "I believe vertical software market dynamics matter a lot in modern technology.",
            "Thin assertion asserting relevance without a distinct causal relationship.",
        ),
        (
            "00251a80c868f535_t0105",
            "Autonomous software agents are definitely significant in computer science.",
            "autonomous software agents are definitely significant in computer science",
            "There is no doubt autonomous software agents are definitely significant in computer science.",
            "Thin assertion carrying minimal propositional depth.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn, desc) in enumerate(prop_tids, start=1):
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
            "perturbation_description": desc,
        })

    # 4. Contestability (5 pairs) -> undisputed empirical fact / date / specification (Contestability=0, Typing=2, Voice=2)
    cont_tids = [
        (
            "00251a80c868f535_t0116",
            "Nvidia announced the Blackwell GPU architecture in March 2024.",
            "Nvidia announced the Blackwell GPU architecture in March 2024",
            "Nvidia announced the Blackwell GPU architecture in March 2024 at their GTC conference.",
            "Undisputed historical announcement date and specification.",
        ),
        (
            "00251a80c868f535_t0122",
            "The United States declared independence in the year 1776.",
            "the United States declared independence in the year 1776",
            "As everyone knows, the United States declared independence in the year 1776.",
            "Undisputed historical fact and date.",
        ),
        (
            "00251a80c868f535_t0123",
            "Apple released the original iPhone in June 2007.",
            "Apple released the original iPhone in June 2007",
            "Historically, Apple released the original iPhone in June 2007 to consumers.",
            "Undisputed product release date and historical record.",
        ),
        (
            "00251a80c868f535_t0125",
            "Google was founded in Menlo Park, California in September 1998.",
            "Google was founded in Menlo Park, California in September 1998",
            "We know Google was founded in Menlo Park, California in September 1998 by Larry Page and Sergey Brin.",
            "Undisputed corporate founding date and location.",
        ),
        (
            "00251a80c868f535_t0133",
            "Microsoft acquired LinkedIn in December 2016.",
            "Microsoft acquired LinkedIn in December 2016",
            "Factually, Microsoft acquired LinkedIn in December 2016 for approximately twenty-six billion dollars.",
            "Undisputed corporate acquisition date.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn, desc) in enumerate(cont_tids, start=1):
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
            "perturbation_description": desc,
        })

    # 5. Typing (5 pairs) -> mushy modality / unclassifiable assertion (Typing=1, Voice=2, Target=2, Prop=2)
    type_tids = [
        (
            "00251a80c868f535_t0138",
            "There is an unspecified general dynamic occurring across various market entities.",
            "there is an unspecified general dynamic occurring across various market entities",
            "There is an unspecified general dynamic occurring across various market entities right now in this economy.",
            "Assertion with mushy modality that lacks a clear canonical type (position, prediction, causal, evaluative, or contested fact).",
        ),
        (
            "00251a80c868f535_t0140",
            "Tesla and robotics technology share a certain ambiguous relationship in modern manufacturing.",
            "Tesla and robotics technology share a certain ambiguous relationship in modern manufacturing",
            "Tesla and robotics technology share a certain ambiguous relationship in modern manufacturing today.",
            "Vague associative assertion devoid of a clear predictive, causal, normative, or evaluative claim.",
        ),
        (
            "00251a80c868f535_t0141",
            "Enterprise software and cloud computing could have some kind of undetermined relationship across industries.",
            "Enterprise software and cloud computing could have some kind of undetermined relationship across industries",
            "Enterprise software and cloud computing could have some kind of undetermined relationship across industries right now.",
            "Broad existential assertion lacking a distinct claim type.",
        ),
        (
            "00251a80c868f535_t0142",
            "Market valuations and interest rates could perhaps have some kind of undetermined relationship across economic cycles.",
            "Market valuations and interest rates could perhaps have some kind of undetermined relationship across economic cycles",
            "Market valuations and interest rates could perhaps have some kind of undetermined relationship across economic cycles across the world.",
            "Mushy associative observation with no clear empirical or mechanistic commitment.",
        ),
        (
            "00251a80c868f535_t0156",
            "Federal deficit spending and sovereign debt dynamics could possibly have some kind of undetermined relationship in fiscal governance.",
            "Federal deficit spending and sovereign debt dynamics could possibly have some kind of undetermined relationship in fiscal governance",
            "Federal deficit spending and sovereign debt dynamics could possibly have some kind of undetermined relationship in fiscal governance across the world.",
            "Vague consideration claim fitting none of the 5 canonical types cleanly.",
        ),
    ]
    for idx, (tid, pert_claim, pert_quote, pert_turn, desc) in enumerate(type_tids, start=1):
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
            "perturbation_description": desc,
        })

    # 6. Decontextualisation (5 pairs) -> replaced subject with unbound pronoun / placeholder
    decontext_tids = [
        ("00251a80c868f535_t0084", "The individual discussed was meaningfully oversold in May."),
        ("00251a80c868f535_t0053", "The company discussed is going to build the best selling product in history."),
        ("00251a80c868f535_t0160", "They will force this to confront its debt."),
        ("00251a80c868f535_t0176", "The unnamed organization is going to have to implement this."),
        ("00251a80c868f535_t0179", "The discussed entity will not have any money to pay by then."),
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

    # 8. Granularity (5 pairs) -> 3 real compound claims from E287 + 2 compound claims
    granularity_cases = [
        (
            "00251a80c868f535_t0016",
            "Excluding researchers outside the mainstream causes a lack of heterodox thinking in science.",
            "The lack of heterodox and outside-the-scope thinking, caused by the exclusion of those not part of the mainstream and the requirement for everyone to think in the same way, means that science is no longer pushing the envelope and discovering new things.",
            "Natural compound claim from E287 embedding multiple causal links and background constraints (42 words).",
        ),
        (
            "00251a80c868f535_t0255",
            "The heuristic used to treat AI as a standalone intelligence replacement system is inaccurate.",
            "The heuristic used to treat AI as a standalone intelligence replacement system is not accurate with respect to how humans actually use AI, which is like all other tools, a magnification of human creativity, ingenuity, and potential.",
            "Natural compound claim from E287 linking heuristic critique with alternative collaborative thesis (37 words).",
        ),
        (
            "00251a80c868f535_t0389",
            "Neoantigen immunotherapy for cancer should not be patented and charged at half a million dollars for patient treatment.",
            "The technique for neoantigen immunotherapy for cancer, which was largely developed through decades of research and funded by the NIH and other public funding, should not be patented, FDA approved, and charged at half a million dollars for patient treatment.",
            "Natural compound claim from E287 embedding decades of NIH funding history, patenting, FDA approval, and pricing (40 words).",
        ),
        (
            "00251a80c868f535_t0109",
            "Vertical SaaS does not have a system of record.",
            "Vertical SaaS does not have a proprietary system of record, and Salesforce was meaningfully oversold in May.",
            "Compound claim concatenating two distinct propositions from different domains with 'and'.",
        ),
        (
            "00251a80c868f535_t0166",
            "If the 30-year Treasury yield reaches 6%, it is the beginning of the end for sovereign debt.",
            "If the 30-year Treasury yield reaches 6%, it is the beginning of the end for sovereign debt, and Tesla's Optimus robot will be the best selling product in history.",
            "Compound claim concatenating sovereign debt mechanics with robotics prediction.",
        ),
    ]
    for idx, (tid, orig_clm, pert_clm, desc) in enumerate(granularity_cases, start=1):
        spk, q, _, txt = get_info(tid)
        perturbations.append({
            "id": f"granularity_{idx:02d}",
            "target_axis": "granularity",
            "turn_id": tid,
            "speaker": spk,
            "quote": q,
            "turn_text": txt,
            "original_claim": orig_clm,
            "perturbed_claim": pert_clm,
            "perturbed_quote": q,
            "perturbed_turn_text": txt,
            "perturbation_description": desc,
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
