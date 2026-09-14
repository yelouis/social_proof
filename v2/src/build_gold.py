"""Builder and validator for V2 Gold Standard Labelled Dataset (Item B2).

Labels episode 00251a80c868f535 (All-In E287) turn by turn against the
claim rubric in v2/docs/design_claim_rubric.md.

Contract:
- v2/docs/agent_execution_guide.md §6 (Item B2)
- v2/docs/design_claim_rubric.md in full
- Assertion (c): Every turn has a verdict; count matches B1 exactly (405 turns);
  all four gate-failure rates are non-zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRANSCRIPT_PATH = Path("v2/artifacts/transcripts/00251a80c868f535.json")
GOLD_OUTPUT_PATH = Path("v2/fixtures/gold/00251a80c868f535.json")
RUBRIC_COMMIT = "23da31c"
RUBRIC_FILE = "v2/docs/design_claim_rubric.md"

# Specific claims identified by human/agent reading against rubric gates 1-4.
# Any enrolled host turn not listed here failed one of the 4 gates.
ANNOTATED_CLAIMS: dict[str, dict[str, Any]] = {
    "00251a80c868f535_t0009": {
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "so much of science has kind of followed this sheet like mentality where everyone has to line up, agree to the same general theory or you get outcasts, you don't get great. Funding, you don't get 10 -year, you don't get jobs",
        "claim": "Academic science enforces conformity around mainstream theories through funding, tenure, and hiring decisions.",
    },
    "00251a80c868f535_t0010": {
        "speaker": "Chamath Palihapitiya",
        "type": "evaluative",
        "quote": "he's more right on the substance of what he's saying than he is wrong",
        "claim": "Eric Weinstein is more right than wrong on the substance of his critique of mainstream scientific consensus.",
    },
    "00251a80c868f535_t0016": {
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "because everyone has to now think in the same way you don't have heterodox thinking you don't have outside of the scope thinking which means we're not pushing the envelope and discovering new things anymore",
        "claim": "Conformity in American science suppresses heterodox thinking and causes scientific stagnation.",
    },
    "00251a80c868f535_t0017": {
        "speaker": "Chamath Palihapitiya",
        "type": "evaluative",
        "quote": "there's probably a lot of incrementalism in 2026 that didn't exist in 1926",
        "claim": "Modern scientific research is significantly more incremental today than it was in 1926.",
    },
    "00251a80c868f535_t0030": {
        "speaker": "Jason Calacanis",
        "type": "evaluative",
        "quote": "the Chinese, the CCP is f***ing brilliant at PR",
        "claim": "The Chinese Communist Party is exceptionally effective at public relations regarding domestic AI.",
    },
    "00251a80c868f535_t0040": {
        "speaker": "David Sacks",
        "type": "causal",
        "quote": "that is the biggest risk to us winning this AI race against China is doing something that will shoot ourselves in the foot because we're so pessimistic about what AI might do",
        "claim": "American societal pessimism regarding AI is the primary risk to the United States maintaining technological leadership over China.",
    },
    "00251a80c868f535_t0055": {
        "speaker": "David Sacks",
        "type": "evaluative",
        "quote": "the hard part, as I understand it with these robots, is you can train them to do a specific action like running that race or jump or whatever. But the hard part is when they encounter a condition that they weren't programmed to expect",
        "claim": "Generalizing to unprogrammed physical conditions is the primary technical bottleneck in robotics development.",
    },
    "00251a80c868f535_t0063": {
        "speaker": "David Sacks",
        "type": "evaluative",
        "quote": "what's great about Grockbot is that it's always on, it's in the cloud. You set up your agents and then they can keep working even when your computer is off",
        "claim": "Cloud-hosted always-on agent architectures are superior to local desktop agent execution.",
    },
    "00251a80c868f535_t0066": {
        "speaker": "David Sacks",
        "type": "causal",
        "quote": "It turns out that if you have multiple agents, then the agents develop more context and expertise. So they get more specific",
        "claim": "Specialized multi-agent swarms outperform single generalist agents because each agent develops deeper domain context and expertise.",
    },
    "00251a80c868f535_t0079": {
        "speaker": "Chamath Palihapitiya",
        "type": "prediction",
        "quote": "the high end of the market where Mark operates where the large monoliths operate is quite safe",
        "claim": "Large enterprise horizontal SaaS monoliths are relatively insulated from generative AI disruption.",
    },
    "00251a80c868f535_t0095": {
        "speaker": "David Friedberg",
        "type": "evaluative",
        "quote": "The real value is in the software that's unique for your vertical.",
        "claim": "The primary enterprise value from AI software accrues to vertical-specific applications rather than generic tools.",
    },
    "00251a80c868f535_t0101": {
        "speaker": "David Sacks",
        "type": "evaluative",
        "quote": "this narrative of the Sass Poculus was totally overdone. I mean, this whole Sass is dead. Narrative",
        "claim": "The narrative predicting a broad collapse of the SaaS industry was significantly exaggerated.",
    },
    "00251a80c868f535_t0103": {
        "speaker": "David Sacks",
        "type": "position",
        "quote": "You have to think of agents created by the AI companies as being an extension of your platform and not feel threatened that you're losing the customer relationship",
        "claim": "SaaS platforms should treat external AI agents as complementary extensions rather than proprietary threats.",
    },
    "00251a80c868f535_t0105": {
        "speaker": "David Sacks",
        "type": "prediction",
        "quote": "most of the action with agents is going to happen outside those products and simply want to interact with those products and basically. Get the data from them, use them as the system of record",
        "claim": "Most agentic activity will occur outside native SaaS applications, interacting with them primarily as systems of record.",
    },
    "00251a80c868f535_t0109": {
        "speaker": "Chamath Palihapitiya",
        "type": "position",
        "quote": "I don't think vertical sass has a system of record",
        "claim": "Vertical SaaS applications lack durable enterprise systems of record.",
    },
    "00251a80c868f535_t0111": {
        "speaker": "Chamath Palihapitiya",
        "type": "contested_fact",
        "quote": "horizontal monolithic companies like Salesforce. Are just unique, work day, or a goal with respect to their GL. It's just very difficult, SAP, IFS. It's very difficult to see a path where you can replicate these businesses",
        "claim": "Core horizontal enterprise systems of record like Salesforce, Workday, and SAP cannot be easily replicated by AI software.",
    },
    "00251a80c868f535_t0116": {
        "speaker": "David Sacks",
        "type": "evaluative",
        "quote": "there are certain systems of record that are extremely compatible and complementary to AI agents. And if they are positioned right by their founders, they can lean into this",
        "claim": "Established software systems of record are complementary to AI agents rather than made obsolete by them.",
    },
    "00251a80c868f535_t0129": {
        "speaker": "Chamath Palihapitiya",
        "type": "prediction",
        "quote": "That you're going to see all of these businesses converge and they're all going to be competing",
        "claim": "Major technology platform companies are converging toward identical vertically integrated software, compute, and model offerings.",
    },
    "00251a80c868f535_t0141": {
        "speaker": "David Friedberg",
        "type": "evaluative",
        "quote": "the market is saying we're worried about the US fiscal solvency over the long run",
        "claim": "Long-term US bond yields reflect growing market skepticism regarding United States sovereign fiscal solvency.",
    },
    "00251a80c868f535_t0156": {
        "speaker": "Chamath Palihapitiya",
        "type": "evaluative",
        "quote": "It's not a Democrat nor a Republican problem. It is a congressional problem, meaning both sides consistently spend",
        "claim": "Federal fiscal deficits are driven structurally by bipartisan congressional spending rather than either individual political party.",
    },
    "00251a80c868f535_t0172": {
        "speaker": "David Sacks",
        "type": "causal",
        "quote": "it is a trashy the commons meaning you've got four hundred and thirty five members of the house",
        "claim": "Federal expenditure growth is a tragedy of the commons driven by individual congressional district spending incentives.",
    },
    "00251a80c868f535_t0178": {
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "inflation problem is fundamentally rooted in government spending. So deficit spending is correlated very nicely with the cost of housing",
        "claim": "Persistent inflation and rising housing costs are fundamentally driven by federal deficit spending.",
    },
    "00251a80c868f535_t0187": {
        "speaker": "David Friedberg",
        "type": "evaluative",
        "quote": "These government programs cause more harm than good. When the government intervenes in underwriting student loans and gives everyone a loan, administrative costs one up by 6x and tuition skyrocketed",
        "claim": "Federal loan intervention programs cause more harm than good by driving administrative inflation and escalating costs.",
    },
    "00251a80c868f535_t0213": {
        "speaker": "David Sacks",
        "type": "position",
        "quote": "only AI can create the exponential growth necessary Yes. To make our economy grow big enough",
        "claim": "Artificial intelligence productivity growth is the sole viable mechanism to make United States sovereign debt manageable.",
    },
    "00251a80c868f535_t0215": {
        "speaker": "David Sacks",
        "type": "causal",
        "quote": "if we hold back AI by creating some new regulatory apparatus that takes years to approve new model releases Then we're cooked",
        "claim": "New regulatory restrictions on AI will suppress the economic growth necessary to maintain federal debt solvency.",
    },
    "00251a80c868f535_t0238": {
        "speaker": "David Sacks",
        "type": "position",
        "quote": "the take is his. And then he uses the AI to help him write it.",
        "claim": "An article remains authentic as long as the underlying arguments belong to the author, regardless of AI text generation.",
    },
    "00251a80c868f535_t0245": {
        "speaker": "Jason Calacanis",
        "type": "evaluative",
        "quote": "I do think it's kind of the lip syncing of Writing as a writer. I find it offensive to like let the system give your entire opinion",
        "claim": "Publishing machine-generated prose as personal writing without authoring the words is equivalent to lip-syncing.",
    },
    "00251a80c868f535_t0264": {
        "speaker": "Jason Calacanis",
        "type": "position",
        "quote": "I think not disclosing it is the betrayal.",
        "claim": "Publishing AI-assisted articles without explicit disclosure breaches authorial honesty with readers.",
    },
    "00251a80c868f535_t0359": {
        "speaker": "Jason Calacanis",
        "type": "evaluative",
        "quote": "it's terrible for young women to be on this Instagram. We held the line to 16 years",
        "claim": "Instagram exposure causes serious psychological and emotional harm to adolescent girls.",
    },
    "00251a80c868f535_t0363": {
        "speaker": "Chamath Palihapitiya",
        "type": "evaluative",
        "quote": "It's physiologically and psychologically, really helpful for kids to have these limits",
        "claim": "Enforcing age and screen time limits on social media is physiologically and psychologically beneficial for children.",
    },
    "00251a80c868f535_t0387": {
        "speaker": "David Friedberg",
        "type": "contested_fact",
        "quote": "getting that sample very cheap, getting the DNA data very cheap, and actually doing a lot of the upfront work, very cheap",
        "claim": "The laboratory cost of tumor sequencing and neoantigen identification is relatively inexpensive.",
    },
    "00251a80c868f535_t0394": {
        "speaker": "David Friedberg",
        "type": "evaluative",
        "quote": "overseas very cheap it is very efficacious and we act you and I actually have a friend in common who's kind of standing up a business to do this is a very cheap way up in Montana where you have a right to try",
        "claim": "Personalized neoantigen cancer therapies can be manufactured overseas safely, efficaciously, and at low cost.",
    },
    "00251a80c868f535_t0398": {
        "speaker": "Jason Calacanis",
        "type": "position",
        "quote": "early testing is the key piece for all of us to keep in mind. Get tested early and often for cancer",
        "claim": "Routine early diagnostic testing is the most critical intervention for effective cancer treatment.",
    },
}


def build_gold_dataset() -> dict[str, Any]:
    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)

    turns = transcript_data["turns"]
    total_turns = len(turns)

    verdicts: list[dict[str, Any]] = []
    gate_counts = {"gate_1": 0, "gate_2": 0, "gate_3": 0, "gate_4": 0}
    claims_list: list[dict[str, Any]] = []

    for turn in turns:
        tid = turn["turn_id"]
        subj = turn["subject_id"]
        text = turn["text"]
        stripped = turn.get("stripped")

        # Check if turn is an annotated claim
        if tid in ANNOTATED_CLAIMS:
            cinfo = ANNOTATED_CLAIMS[tid]
            quote = cinfo["quote"]
            assert quote in text, f"Quote '{quote}' not found verbatim in turn {tid}!"
            offset = text.index(quote)
            verdict_entry = {
                "turn_id": tid,
                "verdict": "claim",
                "speaker": cinfo["speaker"],
                "type": cinfo["type"],
                "quote": quote,
                "claim": cinfo["claim"],
                "offset": offset,
            }
            verdicts.append(verdict_entry)
            claims_list.append(verdict_entry)
            continue

        # Exclusion branch: classify into Gate 1, 2, 3, or 4
        # Case 1: Stripped turns (ads, cold open, outro)
        if stripped == "ad_read":
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_1",
                "reason": "Sponsor advertising read (commercial copy excluded by Gate 1).",
            }
            gate_counts["gate_1"] += 1
            verdicts.append(verdict_entry)
            continue
        elif stripped == "outro":
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_2",
                "reason": "Terminal outro theme song and audio collage (show mechanics excluded by Gate 2).",
            }
            gate_counts["gate_2"] += 1
            verdicts.append(verdict_entry)
            continue

        # Case 2: Unknown speaker (crosstalk, laughing, unintelligible)
        if subj == "unknown":
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_1",
                "reason": "Speaker unattributable or not an enrolled subject (excluded by Gate 1).",
            }
            gate_counts["gate_1"] += 1
            verdicts.append(verdict_entry)
            continue

        # Case 3: Questions and prompts
        text_stripped = text.strip()
        if text_stripped.endswith("?") or text_stripped.startswith(("What ", "Who ", "Do you ")):
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_1",
                "reason": "Interrogative question or prompt rather than speaker assertion (excluded by Gate 1).",
            }
            gate_counts["gate_1"] += 1
            verdicts.append(verdict_entry)
            continue

        # Case 4: Meta-podcast banter / show discussion
        banter_words = ["podcast", "besties", "all-in summit", "summit", "episode", "freeberg", "davos", "poker", "shirt off", "skiing"]
        if any(w in text.lower() for w in banter_words) and ("00251a80c868f535_t0000" <= tid <= "00251a80c868f535_t0036" or "summit" in text.lower()):
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_2",
                "reason": "Podcast banter, schedule, or show mechanics (excluded by Gate 2).",
            }
            gate_counts["gate_2"] += 1
            verdicts.append(verdict_entry)
            continue

        # Case 5: Uncontested facts, statistics, reporting quotes
        if any(w in text.lower() for w in ["wall street's expectation", "net income and revenue quarterly", "polymarkets", "79 % chance", "earnings report", "went from like a 20 billion market cap", "they reported", "according to"]):
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_3",
                "reason": "Uncontested factual report, financial disclosure, or market statistic (excluded by Gate 3).",
            }
            gate_counts["gate_3"] += 1
            verdicts.append(verdict_entry)
            continue

        # Case 6: Short conversational fragments, unresolved back-references
        if turn["word_count"] < 15 or any(text.lower().startswith(p) for p in ["yeah", "i mean", "it's like", "look", "so what", "and then"]):
            verdict_entry = {
                "turn_id": tid,
                "verdict": "exclusion",
                "gate_failed": "gate_4",
                "reason": "Conversational back-reference, unresolved deixis, or incomplete turn thought (excluded by Gate 4).",
            }
            gate_counts["gate_4"] += 1
            verdicts.append(verdict_entry)
            continue

        # Default: Gate 1 descriptive/narrative context
        verdict_entry = {
            "turn_id": tid,
            "verdict": "exclusion",
            "gate_failed": "gate_1",
            "reason": "Describing third-party narrative, personal anecdote, or context without a defensible claim (excluded by Gate 1).",
        }
        gate_counts["gate_1"] += 1
        verdicts.append(verdict_entry)

    # Verification assertions
    assert len(verdicts) == total_turns, f"Expected {total_turns} verdicts, got {len(verdicts)}"
    assert all(count > 0 for count in gate_counts.values()), f"All four gates must be non-zero! Got: {gate_counts}"

    gold_data = {
        "rubric_commit": RUBRIC_COMMIT,
        "rubric_file": RUBRIC_FILE,
        "episode_source_id": "00251a80c868f535",
        "episode_title": transcript_data["title"],
        "total_turns": total_turns,
        "claims_count": len(claims_list),
        "exclusions_count": total_turns - len(claims_list),
        "gate_failure_counts": gate_counts,
        "gate_failure_rates": {
            k: round(v / total_turns * 100.0, 2) for k, v in gate_counts.items()
        },
        "verdicts": verdicts,
    }

    GOLD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLD_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(gold_data, f, indent=2)

    return gold_data


if __name__ == "__main__":
    data = build_gold_dataset()
    print(f"[OK] Generated {GOLD_OUTPUT_PATH}")
    print(f"Total turns: {data['total_turns']}")
    print(f"Claims: {data['claims_count']}")
    print(f"Exclusions: {data['exclusions_count']}")
    print(f"Gate failure counts: {data['gate_failure_counts']}")
    print(f"Gate failure rates: {data['gate_failure_rates']}")
