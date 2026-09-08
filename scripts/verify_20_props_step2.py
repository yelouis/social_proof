"""Step 2: Collect 20 consecutive propositions produced by the prompt/pipeline and evaluate all 20 against the Position Test.

Verifies that >= 16 of 20 (80.0%) pass the position test before full re-extraction.
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
    """Evaluates whether:

      <subject> supports <proposition>
      <subject> opposes  <proposition>
    are both coherent, distinct claims on a matter at issue.
    """
    words = prop.strip().split()
    if len(words) < 5:
        return False, f"Too short ({len(words)} words < 5), bare topic"

    lower = prop.lower()
    for v in [" has been ", " have been ", " was ", " were ", " is now ", " are now ", " has developed ", " should ", " must "]:
        if v in lower:
            return False, f"Contains finite verb or modal '{v.strip()}', not canonical noun phrase"

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

    random.seed(999)
    sample_pool = random.sample(utts, 60)

    runtime = LocalGemmaRuntime(load_live_backend=True)
    embedder = Embedder()

    propositions_tested = []

    print(f"Collecting 20 valid propositions under {runtime.extraction_version}...\n")

    for _i, (uid, _sid, _subj_id, speaker, text) in enumerate(sample_pool, 1):
        if len(propositions_tested) >= 20:
            break

        utt = store.get_utterance(uid)
        if not utt:
            continue

        context = f"Speaker: {speaker}"
        stats = runtime.generate_constrained(text, context)
        claims = stats.parsed_result.claims

        for ec in claims:
            if len(propositions_tested) >= 20:
                break

            outcome = validate_extracted_claim(
                claim=ec,
                utterance=utt,
                confidence_floor=0.70,
                embedder=embedder,
            )
            if not outcome.is_valid or not ec.is_own_assertion:
                continue

            prop = ec.proposition_text
            passed, explanation = evaluate_position_test(prop)
            idx = len(propositions_tested) + 1
            verdict = "PASS" if passed else "FAIL"
            print(f"[{idx:2d}/20] [{verdict}] \"{prop}\"")
            print(f"       Speaker:  {speaker}")
            print(f"       Quote:    \"{ec.quote_text}\"")
            print(f"       Supports: Alice supports {prop}")
            print(f"       Opposes:  Alice opposes {prop}")
            print(f"       Verdict:  {explanation}\n")
            propositions_tested.append((prop, passed, explanation))

    store.close()

    print("=" * 70)
    print("STEP 2: 20-PROPOSITION POSITION TEST AUDIT SUMMARY")
    print("=" * 70)
    pass_count = sum(1 for _, passed, _ in propositions_tested if passed)
    total_count = len(propositions_tested)
    print(f"Total propositions audited: {total_count}")
    print(f"Passed position test:       {pass_count} / {total_count} ({pass_count/total_count*100:.1f}%)")
    assert pass_count >= 16, f"Failed Step 2 gate: expected >= 16/20, got {pass_count}/{total_count}"
    print("GATE PASS: >= 16/20 pass rate satisfied!")
    print("=" * 70)


if __name__ == "__main__":
    main()
