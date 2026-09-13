"""Dual Falsification for Item X2 (Issue 034 = B).

Falsification 1:
Revert the prompt to v1.7 and extract the same 20 utterances (seed 42).
Validator 2b's fire rate must climb back toward 22.9% and position_frame
must stop being emitted / writable. Record both rates.

Falsification 2:
Deliberately break Step 2's identity rule on one test example by letting <X>
vary with stance (support vs oppose). Confirm the two claims land on different
proposition_ids and the self-join in candidate evaluation loses the pair completely.
Then confirm byte-identical <X> preserves the self-join match.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.entities import Claim, Proposition, Source, Subject, Utterance
from worker.extract.dedup import Embedder
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import validate_position_bearing
from worker.storage import Storage, compute_claim_id, compute_proposition_id
from worker.tension.detect import TensionDetector

PROMPT_V1_7 = """
You are a precise extraction system that extracts policy claims and normative assertions from speech transcripts.

RULES:
1. CANONICAL PROPOSITION FORM: Output the matter at issue as a stance-neutral noun phrase.
   - NEVER emit 1 to 4 word bare topics (e.g., 'data sovereignty', 'apps', 'open source AI', 'most enterprises', 'ai race in america'). If there is no specific policy or action at issue, return {"claims": []}.
   - FACTUAL DESCRIPTIONS ARE NOT CLAIMS: Sentences merely reporting that companies hire people, create datasets, make money, or run businesses contain NO policy or normative stance. Return {"claims": []}.
   - INCIDENTS AND NEWS REPORTS ARE NOT CLAIMS: Reporting an incident, meeting, crime, or event (e.g., meeting disruptions, corporate lawsuits, hacks) is NOT a policy matter at issue. Return {"claims": []}.
   - SLANG AND BANTER ARE NOT CLAIMS: Conversational banter, slang, or describing interest in topics contains NO policy or normative stance. Return {"claims": []}.
   - HISTORICAL RECAPS ARE NOT CLAIMS: Describing what past debates were about (e.g., past debates between accelerationists and doomers) is a descriptive summary, not an own-assertion policy stance. Return {"claims": []}.

   - NEVER emit a BARE TOPIC, ENTITY, VALUATION, EVENT, OR FACTUAL DESCRIPTION. A topic admits any stance, so opposing claims on it do not form a contradiction.
     FAILING TOPIC EXAMPLES (DO NOT EMIT THESE — RETURN {"claims": []} OR REFINE TO THE ACTION/POLICY):
       'most enterprises' (FAIL: nobody supports/opposes 'most enterprises')
       'ai race in america' (FAIL: bare subject area)
       'american efforts regarding ai' (FAIL: vague descriptive topic)
       'creation of new jobs over the next year' (FAIL: bare economic prediction)
       'balance occurring in the field of ai regulation' (FAIL: observational topic)
       'underlying kind of traditional object rendering engine' (FAIL: bare technical component)
       'company worth 200 billion' (FAIL: valuation/fact, not a matter at issue)
       'Giving Pledge initiative' (FAIL: bare name of an initiative)
       'two or three hundred individual lawsuits' (FAIL: bare count/event)
       'Board of Supervisors meeting disrupted by internet vandalism' (FAIL: news/incident report)
       'people that are just really interested in the topics that we talk about' (FAIL: banter/observation)
     PASSING MATTERS AT ISSUE (POLICIES, ACTIONS, NORMATIVE CHOICES):
       'federal licensing of frontier AI models' (PASS: supports licensing / opposes licensing)
       'federal standard for algorithmic discrimination' (PASS: supports standard / opposes standard)
       'funding and attention for astronomy research in an era dominated by ai' (PASS)
       'diversification of ai models away from closed models' (PASS)
       'amazon burden-shifting strategy for employees and the american taxpayer' (PASS)
       'sandboxed testing of frontier AI models before deployment' (PASS)
       'industry-wide reduction in AI development pace to 20% slower' (PASS)
       'allowing individual gun ownership despite potential misuse' (PASS)

   - NEVER emit a full clause or finite verb sentence. Do NOT use finite verbs ('is', 'are', 'was', 'were', 'will', 'would', 'should', 'must', 'can', 'has', 'have') as the main predicate of a proposition.
   - NEVER include polarity, positive or negative: no 'should', 'must', 'ought', 'better/worse/cheaper/faster than', 'favored to win', 'should not', 'never', 'oppose', 'against', 'bad', 'harmful', 'cannot', 'not', or 'no'.
   - Polarity lives EXCLUSIVELY in `stance` ('support' | 'oppose' | 'mixed'). Two speakers with opposite opinions on the same matter at issue MUST share the EXACT SAME proposition_text noun phrase.
2. PROPOSITIONS MUST BE SELF-CONTAINED AND GLOBAL (Items W0 / §17m & W2 / §17p).
   - Never use unbound indexicals, speaker references, or vague placeholders in proposition_text (e.g., never say 'The speaker believes...', 'the subject...', 'this item...').
   - Never start a proposition with sentence-initial deictics or unbound pronouns (e.g., 'It is...', 'This...', 'That...', 'These...', 'Those...', 'They...', 'He...', 'She...', 'Their...', 'His...', 'Her...').
   - Never use third-person pronouns ('they', 'their', 'he', 'his', 'him', 'she', 'her') without an explicit antecedent entity named inside the proposition.
   - Never use comparatives without an explicit relatum.
   - Strip the actor completely.
3. INVARIANT I7 (SPEECH-ACT GUARDS): Exclude reported speech, hypotheticals, rhetorical setups, questions.
4. QUOTE TEXT: Return the exact verbatim substring from the utterance text as quote_text.
5. CONSTRAINED SCHEMA: Output must strictly conform to JSON format:
{
  "claims": [
    {
      "proposition_text": "stance-neutral matter at issue noun phrase",
      "stance": "support" | "oppose" | "mixed",
      "hedging_level": 0.0 to 1.0,
      "is_own_assertion": true | false,
      "exclusion_reason": null | "reported_speech" | "hypothetical" | "sarcasm" | "steelman" | "joke" | "question",
      "quote_text": "verbatim substring from utterance",
      "confidence": 0.0 to 1.0
    }
  ]
}

Examples:
Utterance: "We absolutely need federal licensing for frontier models."
Result: {"claims": [{"proposition_text": "federal licensing of frontier AI models", "stance": "support", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "We absolutely need federal licensing for frontier models.", "confidence": 0.95}]}

Utterance: "Licensing would kill open source. Terrible idea."
Result: {"claims": [{"proposition_text": "federal licensing of frontier AI models", "stance": "oppose", "hedging_level": 0.0, "is_own_assertion": true, "exclusion_reason": null, "quote_text": "Licensing would kill open source. Terrible idea.", "confidence": 0.95}]}
""".strip()


def run_falsification_2_identity() -> None:
    """Falsification 2: Deliberately break Step 2's identity rule by letting <X> vary with stance.

    Show that:
    1. When <X> varies with stance (e.g. 'federal licensing of frontier AI models' vs
       'licensing of frontier AI models by the federal government'), the two claims receive
       different proposition_ids, the self-join finds 0 pairs, and the reversal is lost.
    2. When <X> is byte-identical ('federal licensing of frontier AI models'), both claims
       share the same proposition_id and candidate pair detection successfully discovers the reversal.
    """
    print("=" * 80)
    print("FALSIFICATION 2: STEP 2 IDENTITY RULE (VARYING <X> VS BYTE-IDENTICAL <X>)")
    print("=" * 80)

    # 1. Broken identity: <X> varies between support and oppose
    store_broken = Storage(":memory:")
    subj_id = "subject_test_sacks"
    src1_id = "source_ep1"
    src2_id = "source_ep2"

    store_broken.insert_subject(Subject(subject_id=subj_id, display_name="David Sacks"))
    store_broken.insert_source(
        Source(
            source_id=src1_id,
            title="Episode 1",
            publisher="All-In",
            canonical_url="https://youtube.com/watch?v=ep1",
            artifact_hash="hash_ep1",
            recorded_at="2024-01-01T00:00:00Z",
        )
    )
    store_broken.insert_source(
        Source(
            source_id=src2_id,
            title="Episode 2",
            publisher="All-In",
            canonical_url="https://youtube.com/watch?v=ep2",
            artifact_hash="hash_ep2",
            recorded_at="2024-06-01T00:00:00Z",
        )
    )

    utt1 = Utterance(
        utterance_id="utt_broken_1",
        source_id=src1_id,
        subject_id=subj_id,
        start_ms=1000,
        end_ms=5000,
        speaker_label="David Sacks",
        attribution_confidence="high",
        attribution_method="audio_embedding",
        text_verbatim="We absolutely need federal licensing for frontier models.",
    )
    utt2 = Utterance(
        utterance_id="utt_broken_2",
        source_id=src2_id,
        subject_id=subj_id,
        start_ms=1000,
        end_ms=5000,
        speaker_label="David Sacks",
        attribution_confidence="high",
        attribution_method="audio_embedding",
        text_verbatim="Licensing frontier AI models by the federal government is a terrible idea.",
    )
    store_broken.insert_utterance(utt1)
    store_broken.insert_utterance(utt2)

    prop_broken_a = "federal licensing of frontier AI models"
    prop_broken_b = "licensing frontier AI models by the federal government"

    pid_broken_a = compute_proposition_id(prop_broken_a)
    pid_broken_b = compute_proposition_id(prop_broken_b)

    print("Broken Identity Case:")
    print(f"  Claim A (<X> support): '{prop_broken_a}' -> proposition_id={pid_broken_a}")
    print(f"  Claim B (<X> oppose) : '{prop_broken_b}' -> proposition_id={pid_broken_b}")
    assert pid_broken_a != pid_broken_b, "Proposition IDs must differ when <X> varies!"

    store_broken.insert_proposition(
        Proposition(
            proposition_id=pid_broken_a,
            canonical_text=prop_broken_a,
        )
    )
    store_broken.insert_proposition(
        Proposition(
            proposition_id=pid_broken_b,
            canonical_text=prop_broken_b,
        )
    )

    cid_broken_a = compute_claim_id(utt1.utterance_id, pid_broken_a, "support", "test:v1.8:s1")
    cid_broken_b = compute_claim_id(utt2.utterance_id, pid_broken_b, "oppose", "test:v1.8:s1")

    claim_broken_a = Claim(
        claim_id=cid_broken_a,
        subject_id=subj_id,
        utterance_id=utt1.utterance_id,
        proposition_id=pid_broken_a,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.95,
        quote_span=(0, len(utt1.text_verbatim)),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.8",
        extraction_version="test:v1.8:s1",
        recorded_at="2024-01-01T00:00:00Z",
        quote_text=utt1.text_verbatim,
        position_frame=f"the speaker is FOR {prop_broken_a}",
    )
    claim_broken_b = Claim(
        claim_id=cid_broken_b,
        subject_id=subj_id,
        utterance_id=utt2.utterance_id,
        proposition_id=pid_broken_b,
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.95,
        quote_span=(0, len(utt2.text_verbatim)),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.8",
        extraction_version="test:v1.8:s1",
        recorded_at="2024-06-01T00:00:00Z",
        quote_text=utt2.text_verbatim,
        position_frame=f"the speaker is AGAINST {prop_broken_b}",
    )
    store_broken.insert_claim(claim_broken_a)
    store_broken.insert_claim(claim_broken_b)

    detector_broken = TensionDetector(store_broken)
    eval_broken = detector_broken.evaluate_candidate_pairs(subject_id=subj_id)
    print("  Result when <X> varies:")
    print(f"    Examined pairs: {eval_broken.total_pairs_examined}")
    print(f"    Accepted pairs: {eval_broken.candidates_accepted}")
    assert eval_broken.total_pairs_examined == 0, (
        "Self-join must find 0 candidate pairs when <X> varies!"
    )
    print("  -> Falsification CONFIRMED: self-join loses the candidate reversal when <X> varies.\n")

    # 2. Preserved identity: byte-identical <X>
    store_identical = Storage(":memory:")
    store_identical.insert_subject(Subject(subject_id=subj_id, display_name="David Sacks"))
    store_identical.insert_source(
        Source(
            source_id=src1_id,
            title="Episode 1",
            publisher="All-In",
            canonical_url="https://youtube.com/watch?v=ep1",
            artifact_hash="hash_ep1",
            recorded_at="2024-01-01T00:00:00Z",
        )
    )
    store_identical.insert_source(
        Source(
            source_id=src2_id,
            title="Episode 2",
            publisher="All-In",
            canonical_url="https://youtube.com/watch?v=ep2",
            artifact_hash="hash_ep2",
            recorded_at="2024-06-01T00:00:00Z",
        )
    )
    store_identical.insert_utterance(utt1)
    store_identical.insert_utterance(utt2)

    prop_identical = "federal licensing of frontier AI models"
    pid_identical = compute_proposition_id(prop_identical)

    store_identical.insert_proposition(
        Proposition(
            proposition_id=pid_identical,
            canonical_text=prop_identical,
        )
    )

    cid_ident_a = compute_claim_id(utt1.utterance_id, pid_identical, "support", "test:v1.8:s1")
    cid_ident_b = compute_claim_id(utt2.utterance_id, pid_identical, "oppose", "test:v1.8:s1")

    claim_ident_a = Claim(
        claim_id=cid_ident_a,
        subject_id=subj_id,
        utterance_id=utt1.utterance_id,
        proposition_id=pid_identical,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.95,
        quote_span=(0, len(utt1.text_verbatim)),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.8",
        extraction_version="test:v1.8:s1",
        recorded_at="2024-01-01T00:00:00Z",
        quote_text=utt1.text_verbatim,
        position_frame=f"the speaker is FOR {prop_identical}",
    )
    claim_ident_b = Claim(
        claim_id=cid_ident_b,
        subject_id=subj_id,
        utterance_id=utt2.utterance_id,
        proposition_id=pid_identical,
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.95,
        quote_span=(0, len(utt2.text_verbatim)),
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.8",
        extraction_version="test:v1.8:s1",
        recorded_at="2024-06-01T00:00:00Z",
        quote_text=utt2.text_verbatim,
        position_frame=f"the speaker is AGAINST {prop_identical}",
    )
    store_identical.insert_claim(claim_ident_a)
    store_identical.insert_claim(claim_ident_b)

    detector_identical = TensionDetector(store_identical)
    eval_ident = detector_identical.evaluate_candidate_pairs(subject_id=subj_id)
    print("Byte-Identical <X> Case:")
    print(f"  Shared proposition_id: {pid_identical}")
    print(f"  Examined pairs: {eval_ident.total_pairs_examined}")
    print(f"  Accepted pairs: {eval_ident.candidates_accepted}")
    assert eval_ident.total_pairs_examined == 1, (
        "Self-join must find 1 candidate pair with byte-identical <X>!"
    )
    print("  -> Identity rule CONFIRMED: self-join successfully pairs the opposing claims.\n")


def run_falsification_1_prompt(db_bak_path: str = "social_proof.duckdb.pre_x2.bak") -> None:
    """Falsification 1: Revert prompt to v1.7 on the 20 utterances and measure Validator 2b fire rate."""
    print("=" * 80)
    print("FALSIFICATION 1: REVERT PROMPT TO v1.7 (MEASURE VALIDATOR 2b FIRE RATE)")
    print("=" * 80)

    seed = 42
    random.seed(seed)

    store = Storage(db_bak_path, read_only=True)
    utts = store.con.execute("""
        SELECT u.utterance_id, u.source_id, u.subject_id, s.display_name, u.text_verbatim
        FROM utterances u
        JOIN subjects s ON u.subject_id = s.subject_id
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims)
        ORDER BY u.utterance_id
    """).fetchall()

    sample_utts = random.sample(utts, 20)

    print("Initializing LocalGemmaRuntime with prompt v1.7...")
    runtime_v17 = LocalGemmaRuntime(
        prompt_version="v1.7",
        system_prompt=PROMPT_V1_7,
        load_live_backend=True,
    )
    _embedder = Embedder()

    total_claims_v17 = 0
    val_2b_fires_v17 = 0

    for _i, (uid, _sid, _subj_id, speaker, text) in enumerate(sample_utts, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        context = f"Speaker: {speaker}"
        stats = runtime_v17.generate_constrained(text, context)
        claims = stats.parsed_result.claims

        for ec in claims:
            total_claims_v17 += 1
            v2b_res = validate_position_bearing(ec)
            if not v2b_res.is_valid:
                val_2b_fires_v17 += 1

    store.close()

    rate_v17 = (val_2b_fires_v17 / total_claims_v17 * 100) if total_claims_v17 > 0 else 0.0
    print(f"Results for Prompt v1.7 on 20 utterances (seed {seed}):")
    print(f"  Total raw claims emitted: {total_claims_v17}")
    print(f"  Validator 2b rejections : {val_2b_fires_v17} / {total_claims_v17} ({rate_v17:.1f}%)")
    print("  v1.8 comparison rate    : 2 / 18 (11.1%)")
    print("  D6 baseline rate        : 495 / 2161 (22.9%)")


def main() -> None:
    run_falsification_2_identity()
    if len(sys.argv) > 1 and sys.argv[1] == "--with-model":
        run_falsification_1_prompt()
    else:
        print("Note: Run with '--with-model' to execute live MLX inference for Falsification 1.")


if __name__ == "__main__":
    main()
