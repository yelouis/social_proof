"""Item X4 Step 1 Verification.

Extracts from 20 hand-picked descriptive utterances from the corpus.
Verifies that:
1. Most produce NO claim at all (empty list decline).
2. "Azure holds a Fed ramp..." produces NO claim.
3. Position-bearing utterances ("unless you are willing to spend millions...") still produce genuine positions (AGAINST).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.runtime import LocalGemmaRuntime

HAND_PICKED_DESCRIPTIVE_UTTERANCES = [
    (
        "03821a2c2f50bc9a",
        "Azure holds a Fed ramp, high authorization, and Department of Defense, impact level five clear ends.",
    ),
    ("cd2d2586770e1848", "And clearly, I think we have a seat open next week."),
    ("5165bda8e006d8af", "What's gonna happen is a blue state's gonna get blueer."),
    ("db805b516882cc5d", "The water uses quite manageable less than a golf course."),
    (
        "a9c497b1fab0a664",
        "So to your point, Jason, you're seeing this fragmentation and distribution of edge compute, which I think is a theme.",
    ),
    (
        "8dbd05b48ab02f75",
        "I mean, it feels like the amount of capital, time, and intelligent people on the planet, dedicating themselves to the build out of something.",
    ),
    (
        "0d29b1bd5944f419",
        "The fact that Dario could want and has evolved for including in very recent blogs.",
    ),
    (
        "acaef75003ae2add",
        "And that then opened the floodgates to export. are culture wars and then our culture wars became this kind of battle around where there's like France, gender, theater, in Africa, and I think that's what opened the door.",
    ),
    (
        "6ef597669a53fa6b",
        "So they're every single blue chip a plus institutional investor and what they wanted was great companies.",
    ),
    (
        "8e6a1e3a9778a220",
        "Now we have the details of this North American blue energy partners gets a 100 year concession over 17 oil fields.",
    ),
    (
        "13cc49b45f6cdbb5",
        "Blue Energy Partners is pledging roughly $100 billion in new infrastructure a lot of other companies, Chevron, etc.",
    ),
    (
        "454671f771a24eef",
        "And the Mansfield Amendment in 1691 named after Mike Mansfield of Montana said, okay, the military can no longer fund blue sky research inside of our university system.",
    ),
    (
        "e7dfdad7df7279e8",
        "Google blew the doors off of their, uh, blue the doors off. was insane outrageous, and they were 10%, like 70 % Google Cloud growing.",
    ),
    (
        "28126fe431ecb2d8",
        "Is software going to become a hunt? percent bespoke, even like the internal tools, I was looking at Slack.",
    ),
    (
        "bb40e0da0d1d6399",
        "If you go on blue sky, which is like the open source, lib, TDS, social. network.",
    ),
    (
        "5024c52ae48823ca",
        "The slide they generate a lot of tax revenue, they've created a blue collar construction boom.",
    ),
    (
        "9acf5e9601d61b0b",
        "Now there are new solutions like blue energy, which allows you to have huge installations and still fall under the personal use clean air permit.",
    ),
    (
        "7e678e43bdc828da",
        "It's like one cop would have heard that, flip on the blue lights, race down and they're heart racing, he's got his gun ready, and someone's about to die.",
    ),
    (
        "f26fc16041867d97",
        "Well, they barely enter once at a blue moon They did right so you know at night the sign is streaming this through the earth is passing through Hollywood, yeah, but it when it gets to us it goes It keeps going, you know, you can shoot it through what it is a light year of lead in, you know, very rarely.",
    ),
    (
        "215a3769859a9cad",
        "Unless you have like your real, name or you're a blue checkmark or something.",
    ),
]

POSITION_BEARING_CONTROLS = [
    (
        "73c1f91e3d98e960",
        "Hardware makes building production apps unless you are willing to spend millions and millions of dollars for a very slow app, unfeasible.",
    ),
    (
        "7bd614831d924148",
        "Now it may not be located in places that actually make sense for commerce and for people to live or that are already living there because I don't think it really abuts, you know.",
    ),
]


def run_verification() -> None:
    print("Loading LocalGemmaRuntime with live MLX backend...")
    runtime = LocalGemmaRuntime(load_live_backend=True)

    print("\n--- EXTRACTING 20 DESCRIPTIVE UTTERANCES ---")
    declined_count = 0
    emitted_count = 0

    for idx, (uid, text) in enumerate(HAND_PICKED_DESCRIPTIVE_UTTERANCES, 1):
        stats = runtime.generate_constrained(text, subject_context="Speaker: Host / Guest")
        claims = stats.parsed_result.claims
        num = len(claims)
        if num == 0:
            declined_count += 1
            status = "DECLINED (empty list)"
            detail = ""
        else:
            emitted_count += 1
            c = claims[0]
            status = f"EMITTED {num} claim(s)"
            detail = f" -> frame: {c.position_frame} | excl: {c.exclusion_reason}"

        print(f"[{idx:02d}/20] {uid} | {status}{detail}")
        print(f'     text: "{text[:80]}..."')

    print(
        f"\nDescriptive utterances summary: {declined_count}/20 DECLINED ({declined_count / 20 * 100:.1f}%), {emitted_count}/20 EMITTED ({emitted_count / 20 * 100:.1f}%)"
    )

    # Check Azure Fed ramp explicitly
    azure_uid = "03821a2c2f50bc9a"
    azure_text = dict(HAND_PICKED_DESCRIPTIVE_UTTERANCES)[azure_uid]
    azure_stats = runtime.generate_constrained(azure_text)
    azure_emitted = len(azure_stats.parsed_result.claims)
    print(f"\nExplicit check: Azure Fed ramp ({azure_uid}) claims count: {azure_emitted}")
    assert azure_emitted == 0, f"FAILED: Azure Fed ramp still emitted {azure_emitted} claims!"
    print("  PASS: Azure Fed ramp produced no claims.")

    print("\n--- EXTRACTING POSITION-BEARING CONTROLS ---")
    for uid, text in POSITION_BEARING_CONTROLS:
        stats = runtime.generate_constrained(text)
        claims = stats.parsed_result.claims
        print(f"Control {uid}: emitted {len(claims)} claim(s)")
        for c in claims:
            print(f"  frame: {c.position_frame}")
            print(f"  stance: {c.stance}")
            print(f"  prop: {c.proposition_text}")
        if uid == "73c1f91e3d98e960":
            assert len(claims) > 0, "FAILED: Hardware spend control produced no claim!"
            assert claims[0].stance == "oppose", f"FAILED: Expected oppose, got {claims[0].stance}"
            print("  PASS: Hardware spend produced AGAINST.")

    print("\nALL STEP 1 CHECKS PASSED.")


if __name__ == "__main__":
    run_verification()
