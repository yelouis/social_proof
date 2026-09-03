from fixtures.behaviour.loader import load_behaviour_cases
from worker.extract.gate import ExtractionGate


def test_gate_zero_false_negatives_on_golden_positives() -> None:
    """All golden positive cases (P1-P4) MUST pass through the gate (zero false rejections)."""
    gate = ExtractionGate(claim_threshold=0.20)
    cases = load_behaviour_cases()
    positive_cases = [c for c in cases if c.type in ["P1", "P2", "P3", "P4"]]

    for case in positive_cases:
        for utt in case.utterances:
            decision = gate.evaluate_text(utt.text)
            assert decision.should_extract is True, (
                f"Gate falsely rejected positive case {case.case_id} utterance: '{utt.text}'"
            )


def test_gate_filters_conversational_filler_n13() -> None:
    """Conversational filler cases (N13) should be filtered out by the gate."""
    gate = ExtractionGate(claim_threshold=0.20)
    filler_phrases = [
        "Yeah, absolutely, thanks so much for having me on the show today.",
        "Let me check my calendar for next Tuesday afternoon, I think that works.",
        "Right, exactly, mm-hmm, totally agree with that logistical point.",
        "Yeah exactly.",
        "Thanks for having me.",
        "Sound check one two three.",
    ]
    rejected_count = sum(1 for phrase in filler_phrases if not gate.evaluate_text(phrase).should_extract)
    assert rejected_count >= len(filler_phrases) - 1


def test_falsification_overly_strict_threshold_rejects_positive_case() -> None:
    """Falsification test: Raising threshold to 0.95 causes false negative on positive cases."""
    strict_gate = ExtractionGate(claim_threshold=0.95)
    cases = load_behaviour_cases()
    p1 = next(c for c in cases if c.type == "P1")

    decision = strict_gate.evaluate_text(p1.text_snippet)
    # Decision becomes False because score < 0.95
    assert decision.should_extract is False  # Falsification confirmed!
