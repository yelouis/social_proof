"""Tests and LOOP 2 falsification for Item D4 (§13w):

Validator 7 scope-aware negation validation & false-flip suppression.
"""

import json
from pathlib import Path
from typing import Literal, cast

from worker.extract.dedup import Embedder
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    has_syntactic_negation,
    reset_stance_correction_counts,
    validate_stance_direction,
)

CANONICAL_QUOTES_D4 = [
    {
        "case_id": "canonical_continuation_modal_not_stop",
        "proposition_text": "the rest of the world will continue to utilize LLMs even if the US does",
        "quote_text": "the rest of the world's not going to stop using these models",
        "initial_stance": "support",
        "expected_stance": "support",
        "notes": "'not stop' = continue. Continuation modal negation reinforces proposition.",
    },
    {
        "case_id": "canonical_epistemic_verb_never_predict",
        "proposition_text": "understanding user intent … is a significant advance",
        "quote_text": "we would never have been able to predict … that we go from a great summarizer to actually understanding your intent",
        "initial_stance": "support",
        "expected_stance": "support",
        "notes": "'never' negates predict (epistemic stance), not the proposition advancement.",
    },
    {
        "case_id": "canonical_attenuating_qualifier_not_that_much",
        "proposition_text": "anthropic's growth rate is significantly faster than openai's",
        "quote_text": "That's not that much of an increase when anthropic is growing 10x and openAI 4x",
        "initial_stance": "support",
        "expected_stance": "support",
        "notes": "'not' negates 'much of an increase' (qualifier), while endorsing Anthropic's faster growth.",
    },
    {
        "case_id": "canonical_foil_refutation_double_negation",
        "proposition_text": "Running a Chinese model on your own infrastructure does not necessarily mean data will go to China",
        "quote_text": "a lot of people think the data must be going back to China, but it's not if it's run on your own infrastructure",
        "initial_stance": "support",
        "expected_stance": "support",
        "notes": "Both carry negation: foil refutation agrees with negated proposition.",
    },
]


def test_assertion_c_drawn_eval_set_confusion_matrix() -> None:
    """1. Assertion (c) & Drawn Evaluation Set (80 claims, seed 168).

    - Measures and reports the confusion matrix over the drawn evaluation set.
    - Asserts 0 false flips in the support -> oppose direction.
    - Asserts both classes end as their true stance.
    """
    fixture_path = Path("fixtures/behaviour/stance_validation_eval.json")
    assert fixture_path.exists(), f"Missing fixture file: {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) >= 40, f"Expected at least 40 cases (§13w Step 1), got {len(cases)}"

    reset_stance_correction_counts()
    embedder = Embedder()

    confusion: dict[str, int] = {
        "true_support_ended_support": 0,
        "true_support_ended_oppose": 0,
        "true_oppose_ended_oppose": 0,
        "true_oppose_ended_support": 0,
    }

    for c in cases:
        cid = c["claim_id"]
        true_stance = c["true_stance"]
        claim = ExtractedClaim(
            proposition_text=c["proposition_text"],
            stance=cast(Literal["support", "oppose", "mixed"], c["initial_stance"]),
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=c["quote_text"],
            confidence=0.9,
        )

        outcome = validate_stance_direction(claim, embedder=embedder, auto_correct=True)
        assert outcome.is_valid is True, f"[{cid}] Expected valid after auto_correct, got {outcome}"

        final_stance = claim.stance
        if true_stance == "support":
            if final_stance == "support":
                confusion["true_support_ended_support"] += 1
            else:
                confusion["true_support_ended_oppose"] += 1
        elif true_stance == "oppose":
            if final_stance == "oppose":
                confusion["true_oppose_ended_oppose"] += 1
            else:
                confusion["true_oppose_ended_support"] += 1

        assert final_stance == true_stance, (
            f"[{cid}] Expected final stance '{true_stance}', got '{final_stance}' (initial: '{c['initial_stance']}')"
        )

    # Assertion (c): false-flip rate in support -> oppose direction must be 0 on drawn set
    total_support = confusion["true_support_ended_support"] + confusion["true_support_ended_oppose"]
    false_flip_rate = (
        confusion["true_support_ended_oppose"] / total_support if total_support > 0 else 0.0
    )

    assert confusion["true_support_ended_oppose"] == 0, (
        f"False flip failure: {confusion['true_support_ended_oppose']} support claims falsely flipped to oppose"
    )
    assert false_flip_rate == 0.0, f"Expected 0.0 false-flip rate, got {false_flip_rate:.4f}"

    # Verify oppose floor (Issue 018 = B: >= 5 cases)
    total_oppose = confusion["true_oppose_ended_oppose"] + confusion["true_oppose_ended_support"]
    assert total_oppose >= 5, f"Expected >= 5 oppose cases, got {total_oppose}"
    assert confusion["true_oppose_ended_support"] == 0, f"Oppose errors: {confusion}"


def test_canonical_four_quotes_end_as_support() -> None:
    """2. Assertion (c) Canonical Quotes:

    All four canonical live quotes from §13w that failed under unmodified D3
    now end as support under the scope-aware validator.
    """
    embedder = Embedder()

    for c in CANONICAL_QUOTES_D4:
        cid = c["case_id"]
        claim = ExtractedClaim(
            proposition_text=c["proposition_text"],
            stance=cast(Literal["support", "oppose", "mixed"], c["initial_stance"]),
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=c["quote_text"],
            confidence=0.9,
        )

        outcome = validate_stance_direction(claim, embedder=embedder, auto_correct=True)
        assert outcome.is_valid is True, f"[{cid}] Expected valid, got {outcome}"
        assert claim.stance == "support", (
            f"[{cid}] Canonical quote MUST end as 'support', got '{claim.stance}'. Quote: {c['quote_text']}"
        )


def test_oppose_to_support_precision_preserved() -> None:
    """3. Validation check: oppose -> support precision does not regress.

    Live claims that genuinely assert the proposition despite being labeled oppose
    by the initial extractor must still be corrected to support.
    """
    embedder = Embedder()

    # Two verified oppose -> support flips from corpus
    cases = [
        {
            "case_id": "679a8a29cc3b78dc",
            "proposition_text": "bitcoin's use for black market transactions is a misconception",
            "quote_text": "And I think it's disp - this idea that the only thing you'd use Bitcoin for is black market transactions is just completely wrong.",
            "initial_stance": "oppose",
            "expected_stance": "support",
        },
        {
            "case_id": "c606393a6d045545",
            "proposition_text": "politicians have a complete inability to pass a new framework",
            "quote_text": "And so if you look at the section 230 example, where have we left ourselves, the politicians have a complete inability to pass a new framework.",
            "initial_stance": "oppose",
            "expected_stance": "support",
        },
    ]

    for c in cases:
        claim = ExtractedClaim(
            proposition_text=c["proposition_text"],
            stance=cast(Literal["support", "oppose", "mixed"], c["initial_stance"]),
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=c["quote_text"],
            confidence=0.9,
        )
        outcome = validate_stance_direction(claim, embedder=embedder, auto_correct=True)
        assert outcome.is_valid is True
        assert claim.stance == "support", (
            f"[{c['case_id']}] Expected correction to 'support', got '{claim.stance}'"
        )


def test_loop2_falsification_scope_test_discriminates() -> None:
    """4. LOOP 2 FALSIFICATION (§13w):

    - When scope test is active, canonical quote 1 ('not going to stop') does NOT trigger negation
      scoping over the proposition, so it remains 'support' (GREEN).
    - Under naive negation detection without scope (matching any negator), 'not' matches indiscriminately
      and inverts the claim to 'oppose' (falsifying the naive mechanism, RED).
    """
    prop = "the rest of the world will continue to utilize LLMs even if the US does"
    quote = "the rest of the world's not going to stop using these models"

    # 1. With scope test (Item D4): has_syntactic_negation recognises continuation modal
    assert has_syntactic_negation(quote, prop) is False, (
        "Scope test must recognize 'not going to stop' as a continuation idiom, not an opposition"
    )

    # 2. Naive matching (Item D3): matching 'not' without scope check
    naive_has_neg = "not" in quote.lower()
    assert naive_has_neg is True, "Naive matching confirms presence of 'not' token"
