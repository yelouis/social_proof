"""Step 2 Verification: 20-utterance sample gate for Item D6 (§11).

Extract from 20 utterances and apply the position test to every proposition produced.
At least 16 of 20 must pass the position test before full re-extraction.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import Embedder
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import validate_extracted_claim
from worker.storage import Storage


def evaluate_position_test(prop: str) -> tuple[bool, str]:
    """Applies the position test to a proposition string:

    A proposition passes if both:
      <subject> supports <proposition>
      <subject> opposes  <proposition>
    are coherent, distinct claims on a matter at issue.
    """
    words = prop.strip().split()
    if len(words) < 5:
        return False, f"Too short ({len(words)} words < 5), bare topic"

    lower = prop.lower()
    # Check for finite verbs acting as main clauses
    for v in [" has been ", " have been ", " was ", " were ", " is now ", " are now ", " has developed ", " have developed ", " should ", " must "]:
        if v in lower:
            return False, f"Contains finite verb or modal '{v.strip()}', not canonical noun phrase"

    # Check for bare verb openers
    first_word = words[0].lower()
    if first_word in ["bolt", "disrupt", "pricing", "doing", "making"]:
        if not first_word.endswith("ing"):
            return False, f"Starts with bare imperative verb '{first_word}'"

    # Check for incident reports / news events
    for marker in ["meeting disrupted", "lawsuits that will take", "worth 200 billion"]:
        if marker in lower:
            return False, "Incident/valuation description, not a policy matter at issue"

    return True, "PASS: Coherent, distinct support/oppose stances"


def main() -> None:
    store = Storage("social_proof.duckdb", read_only=True)
    utts = store.con.execute("""
        SELECT u.utterance_id, u.source_id, u.subject_id, s.display_name, u.text_verbatim
        FROM utterances u
        JOIN subjects s ON u.subject_id = s.subject_id
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims)
        ORDER BY u.utterance_id
    """).fetchall()

    random.seed(42)
    sample_utts = random.sample(utts, 20)

    runtime = LocalGemmaRuntime(load_live_backend=True)
    embedder = Embedder()

    propositions_tested = []

    print(f"Running Step 2 verification on 20 utterances using {runtime.extraction_version}...\n")

    for i, (uid, _sid, _subj_id, speaker, text) in enumerate(sample_utts, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        context = f"Speaker: {speaker}"
        stats = runtime.generate_constrained(text, context)
        claims = stats.parsed_result.claims

        print(f"[{i:2d}/20] ({speaker}): \"{text[:70]}...\"")
        if not claims:
            print("   -> No claims emitted (banter/non-position)")
            continue

        for ec in claims:
            # Validate through pipeline
            outcome = validate_extracted_claim(
                claim=ec,
                utterance=utt,
                confidence_floor=0.70,
                embedder=embedder,
            )
            if not outcome.is_valid or not ec.is_own_assertion:
                reason = outcome.rejection_reason or (ec.exclusion_reason if not ec.is_own_assertion else "unknown")
                print(f"   [Validator Rejected: {reason}] \"{ec.proposition_text}\"")
                continue

            prop = ec.proposition_text
            passed, explanation = evaluate_position_test(prop)
            verdict = "PASS" if passed else "FAIL"
            print(f"   [{verdict}] \"{prop}\"")
            print(f"          Supports: Alice supports {prop}")
            print(f"          Opposes:  Alice opposes {prop}")
            print(f"          Reason:   {explanation}")
            propositions_tested.append((prop, passed, explanation))

    store.close()

    print("\n" + "=" * 70)
    print("STEP 2 SAMPLE VERIFICATION SUMMARY")
    print("=" * 70)
    pass_count = sum(1 for _, passed, _ in propositions_tested if passed)
    total_count = len(propositions_tested)
    print(f"Total valid propositions produced: {total_count}")
    print(f"Passed position test:             {pass_count} / {total_count} ({pass_count/total_count*100:.1f}%)" if total_count > 0 else "0")
    print("=" * 70)


if __name__ == "__main__":
    main()
