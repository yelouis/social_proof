"""Step 0 baseline measurement for Item X4.

Draws 40 own-assertion claims with fixed seed 20260910 from social_proof.duckdb
and outputs the exact claims, quotes, position frames, and human verdicts.
"""

import random

import duckdb

VERDICTS = {
    "1e0bcbbf400545b7": (
        "fabricated",
        "factual descriptive comparison about water consumption, not a policy/normative stance",
    ),
    "98aad7b0aae681dc": ("fabricated", "scheduling/logistical fact, not a position"),
    "9149be049710f3a4": ("marginal", "observing willingness of third parties to engage"),
    "43545af2bb2c36e7": ("incoherent", "fragmentary, ungrammatical, not a stance"),
    "2d67a498dc8a5112": ("genuine", "critiquing suboptimal datacenter placement"),
    "69d3e1f8e94c9788": ("fabricated", "description of market outcome"),
    "e91125b82147009c": (
        "marginal",
        "speculative questioning about whether bespoke tools will happen",
    ),
    "d06cb582baad70cb": (
        "fabricated",
        "factual descriptive comparison about water consumption, not a policy/normative stance",
    ),
    "0df366479f64bf75": ("fabricated", "scheduling/logistical fact, not a position"),
    "281aa00a12e23da6": ("marginal", "observing willingness of third parties to engage"),
    "dfecb59cf9bc4a89": ("incoherent", "fragmentary, ungrammatical, not a stance"),
    "b62f741584ea6eb9": ("genuine", "critiquing suboptimal datacenter placement"),
    "6c469f417f7d45e4": ("fabricated", "description of market outcome"),
    "77fb1ce13f3807d9": (
        "marginal",
        "speculative questioning about whether bespoke tools will happen",
    ),
    "6a1293e7b421d546": ("fabricated", "product certification fact"),
    "083382e1827702ad": (
        "genuine",
        "asserting unfeasibility and rejecting excessive cost for slow apps",
    ),
    "23151b7fc72d3818": ("fabricated", "observational sentiment, not a normative stance"),
    "46a19a2f1e822ccc": ("fabricated", "electoral prediction, not a policy stance"),
    "4b7a5d29c43b326b": (
        "fabricated",
        "industry observation/theme, not advocating for edge compute",
    ),
    "32ef602757c3a5cd": (
        "genuine",
        "normative advice on executive responsibility in viral media environment",
    ),
    "a789a3537d1431c7": (
        "fabricated",
        "factual count of passed legislation, speaker is not advocating for them",
    ),
    "de764fd76e8352b9": ("genuine", "direct prescriptive recommendation: you should get out now"),
    "9886cb63d9324564": ("fabricated", "reporting factual status of ongoing R&D"),
    "d7cbf58895239426": ("genuine", "critique/condemnation of employer labor practice"),
    "234b6239e8f3cbae": ("marginal", "observing pension fund risk that will need resolution"),
    "cc1d5bf50fb03589": ("fabricated", "describing software tool prerequisite"),
    "68efe94877b150c9": (
        "fabricated",
        "observing statistical correlation, speaker actually opposes deficit spending",
    ),
    "ef7e454e5f87c477": ("fabricated", "commercial analysis of Nvidia vs OpenAI/Anthropic"),
    "393502f5a656a35b": ("genuine", "strategic business recommendation for game developers"),
    "71ced601064df744": ("fabricated", "descriptive statement about media assets"),
    "2be2bbae7f13a2df": ("fabricated", "technical compounding speed comparison"),
    "5d0dcf8d596f5e3a": ("fabricated", "financial valuation multiple report"),
    "940e9885b2af2f8c": ("marginal", "reporting developer sentiment/friction"),
    "b6ba459fdda702c3": (
        "fabricated",
        "historical/sociological cycle prediction, speaker not endorsing scapegoating",
    ),
    "58645b9f4b056734": ("fabricated", "prompt instruction / software workflow example"),
    "cdff389f0fe395e4": ("genuine", "ethical pushback against suppressing inquiry"),
    "e3a9240411a1fd00": ("marginal", "technical utility observation"),
    "ca5ab685c809c16f": ("incoherent", "fragmentary speech, not a stance"),
    "fbf73a5af6bc94a6": ("fabricated", "financial revenue metric report"),
    "d395d616816db0ee": ("genuine", "explicit career advice/recommendation"),
    "e8f0334afe7f9c48": ("fabricated", "legislative introduction statistic"),
    "44bbf5fc8927ae89": ("fabricated", "describing NYC budget line and political dynamic"),
    "b9d50d30a2cd1753": ("genuine", "journalistic standard prescription"),
    "f3e1d6116671cbfb": ("fabricated", "speculating on someone else's ideological motivation"),
    "72f8fab8cdc10fd3": ("fabricated", "personal coding musing"),
    "8760e1e1650cd2c9": ("fabricated", "factual fiscal budget statistic"),
    "0452b3b59297aa03": ("fabricated", "product feature demonstration observation"),
}


def main() -> None:
    con = duckdb.connect("social_proof.duckdb", read_only=True)
    claims = con.execute("""
        SELECT c.claim_id, c.utterance_id, c.position_frame, c.quote_text, c.stance, p.canonical_text
        FROM claims c
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE c.is_own_assertion = true
        ORDER BY c.claim_id
    """).fetchall()

    random.seed(20260910)
    sample = random.sample(claims, 40)

    genuine_count = 0
    marginal_count = 0
    fabricated_count = 0
    incoherent_count = 0

    print("=" * 80)
    print("STEP 0 BASELINE MEASUREMENT — 40 OWN-ASSERTION CLAIMS (seed=20260910)")
    print("=" * 80)

    for idx, c in enumerate(sample, 1):
        cid = c[0]
        verdict, rationale = VERDICTS.get(cid, ("unknown", ""))
        if verdict == "genuine":
            genuine_count += 1
        elif verdict == "marginal":
            marginal_count += 1
        elif verdict == "fabricated":
            fabricated_count += 1
        elif verdict == "incoherent":
            incoherent_count += 1

        print(f"{idx}. [{cid}] {verdict.upper()}: {rationale}")
        print(f"   Frame: {c[2]}")
        print(f'   Quote: "{c[3]}"')
        print()

    total = len(sample)
    print("=" * 80)
    print(f"BASELINE SUMMARY (n={total}):")
    print(f"  Genuine positions : {genuine_count} ({genuine_count / total * 100:.1f}%)")
    print(f"  Marginal positions: {marginal_count} ({marginal_count / total * 100:.1f}%)")
    print(f"  Fabricated frames : {fabricated_count} ({fabricated_count / total * 100:.1f}%)")
    print(f"  Incoherent frames : {incoherent_count} ({incoherent_count / total * 100:.1f}%)")
    bad_count = fabricated_count + incoherent_count
    print(f"  Total Non-Positions: {bad_count} / {total} ({bad_count / total * 100:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
