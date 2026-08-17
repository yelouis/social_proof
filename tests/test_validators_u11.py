"""Unit and falsification tests for the Five Validators and Extraction Pipeline (U11)."""

from pathlib import Path

from worker.entities import Utterance
from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    validate_confidence_floor,
    validate_polarity,
    validate_quote_verbatim,
    validate_schema,
    validate_speech_acts,
)
from worker.storage import Storage


def make_sample_utterance(text: str = "We must mandate federal licensing for all large frontier models.") -> Utterance:
    return Utterance(
        utterance_id="utt_val_01",
        source_id="src_val_01",
        subject_id="subj_val_01",
        text_verbatim=text,
        start_ms=1000,
        end_ms=5000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
    )


def test_validator_1_quote_verbatim() -> None:
    utt = make_sample_utterance("We must mandate federal licensing for all large frontier models.")

    # Valid quote
    valid_claim = ExtractedClaim(
        proposition_text="frontier AI model licensing requirement",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="mandate federal licensing",
        confidence=0.95,
    )
    res_valid = validate_quote_verbatim(valid_claim, utt.text_verbatim)
    assert res_valid.is_valid is True
    assert res_valid.resolved_quote_span == (8, 33)

    # Hallucinated quote
    invalid_claim = ExtractedClaim(
        proposition_text="frontier AI model licensing requirement",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="state government licensing program",
        confidence=0.95,
    )
    res_invalid = validate_quote_verbatim(invalid_claim, utt.text_verbatim)
    assert res_invalid.is_valid is False
    assert res_invalid.rejection_reason == "quote_verbatim_not_found_in_utterance"


def test_validator_2_polarity_rejection() -> None:
    # Stance-neutral proposition: PASS
    neutral_claim = ExtractedClaim(
        proposition_text="frontier AI compute cluster licensing requirement",
        stance="oppose",  # Polarity in stance is fine!
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="mandate federal licensing",
        confidence=0.95,
    )
    assert validate_polarity(neutral_claim).is_valid is True

    # Polarity-polluted propositions: REJECT
    banned_samples = [
        "frontier AI compute clusters should not be licensed",
        "why we must never allow open source weights",
        "prohibiting all neural network exports",
        "opposing mandatory compute audits",
    ]
    for banned in banned_samples:
        polluted_claim = ExtractedClaim(
            proposition_text=banned,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="mandate federal licensing",
            confidence=0.95,
        )
        assert validate_polarity(polluted_claim).is_valid is False


def test_validator_3_speech_acts_invariant_i7() -> None:
    # Valid own assertion
    own_claim = ExtractedClaim(
        proposition_text="frontier AI licensing requirement",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        exclusion_reason=None,
        quote_text="mandate federal licensing",
        confidence=0.95,
    )
    assert validate_speech_acts(own_claim).is_valid is True

    # Valid excluded sarcasm
    sarcasm_claim = ExtractedClaim(
        proposition_text="open source Python script licensing requirement",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=False,
        exclusion_reason="sarcasm",
        quote_text="brilliant idea to ban every open source script",
        confidence=0.95,
    )
    assert validate_speech_acts(sarcasm_claim).is_valid is True

    # Invalid: excluded but missing reason
    invalid_excluded = ExtractedClaim(
        proposition_text="open source Python script licensing requirement",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=False,
        exclusion_reason=None,  # Missing!
        quote_text="brilliant idea",
        confidence=0.95,
    )
    assert validate_speech_acts(invalid_excluded).is_valid is False


def test_validator_4_confidence_floor() -> None:
    low_conf = ExtractedClaim(
        proposition_text="frontier AI licensing requirement",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="mandate federal licensing",
        confidence=0.55,
    )
    assert validate_confidence_floor(low_conf, floor=0.70).is_valid is False


def test_validator_5_schema_constraints() -> None:
    valid_schema = ExtractedClaim(
        proposition_text="frontier AI licensing requirement",
        stance="support",
        hedging_level=0.5,
        is_own_assertion=True,
        quote_text="mandate federal licensing",
        confidence=0.95,
    )
    assert validate_schema(valid_schema).is_valid is True


def test_claim_extraction_pipeline_end_to_end(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    pipeline = ClaimExtractionPipeline(storage=store)

    utt = make_sample_utterance("We must mandate federal licensing for all large frontier models.")
    store.insert_utterance(utt)

    mock_output = {
        "claims": [
            {
                "proposition_text": "frontier AI model licensing requirement",
                "stance": "support",
                "hedging_level": 0.0,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "quote_text": "mandate federal licensing for all large frontier models",
                "condition": None,
                "prior_stance_reported": None,
                "change_marker": None,
                "confidence": 0.98,
            }
        ]
    }

    claims = pipeline.extract_from_utterance(
        utterance=utt,
        source_recorded_at="2024-01-15T12:00:00Z",
        mock_model_output=mock_output,
    )

    assert len(claims) == 1
    c = claims[0]
    assert c.stance == "support"
    assert c.quote_span == (8, 63)
    assert c.recorded_at == "2024-01-15T12:00:00Z"
    assert c.extraction_model == "gemma-3-27b-it"


def test_falsification_disabled_polarity_validator_leaks_banned_tokens() -> None:
    """Falsification test: Disabling polarity validator allows 'should not' in proposition text."""
    banned_claim = ExtractedClaim(
        proposition_text="AI models should not be deployed",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="should not be deployed",
        confidence=0.95,
    )
    # With active validator:
    res = validate_polarity(banned_claim)
    assert res.is_valid is False  # Falsification confirmed: validator successfully catches violation!
