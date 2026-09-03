"""Fixture datasets: hand-written valid and deliberately broken fixtures."""

from worker.entities import Assessment, Claim, Source, SourceSubjectRole, Tension, Utterance
from worker.storage import compute_role_id


def load_valid_fixtures() -> tuple[list[Source], list[Utterance], list[Claim], list[Tension], list[Assessment], list[SourceSubjectRole]]:
    """Loads a fully valid entity graph that satisfies all 9 integrity checks."""
    source_1 = Source(
        source_id="src_valid_01",
        title="Episode 101: AI Regulation and the Future",
        publisher="The Tech Pod",
        canonical_url="https://youtube.com/watch?v=valid01",
        artifact_hash="hash_src_valid_01",
        citation_url_template="https://youtu.be/valid01?t={seconds}",
        interlocutor=None,
        recorded_at="2024-01-15T10:00:00Z",
        published_at="2024-01-16T08:00:00Z",
        transcription_model="whisper-large-v3",
        ingested_at="2024-01-16T12:00:00Z",
        audio_deleted_at="2024-01-16T12:05:00Z",
    )

    source_2 = Source(
        source_id="src_valid_02",
        title="Senate Judiciary Hearing on Frontier AI",
        publisher="U.S. Senate",
        canonical_url="https://judiciary.senate.gov/hearings/frontier-ai",
        artifact_hash="hash_src_valid_02",
        citation_url_template="https://judiciary.senate.gov/hearings/frontier-ai#p{seconds}",
        interlocutor="Committee Chair",
        recorded_at="2024-05-10T14:00:00Z",
        published_at="2024-05-10T18:00:00Z",
        transcription_model="official_transcript",
        ingested_at="2024-05-11T09:00:00Z",
        audio_deleted_at="2024-05-11T09:01:00Z",
    )

    role_1 = SourceSubjectRole(
        role_id=compute_role_id("src_valid_01", "subj_valid_01"),
        source_id="src_valid_01",
        subject_id="subj_valid_01",
        tier="B",
        venue_type="own_channel",
        audience_stance="friendly",
        is_adversarial=False,
    )

    role_2 = SourceSubjectRole(
        role_id=compute_role_id("src_valid_02", "subj_valid_01"),
        source_id="src_valid_02",
        subject_id="subj_valid_01",
        tier="D",
        venue_type="institutional",
        audience_stance="adversarial",
        is_adversarial=True,
    )

    utt_1 = Utterance(
        utterance_id="utt_valid_01",
        source_id="src_valid_01",
        subject_id="subj_valid_01",
        text_verbatim="We absolutely need federal licensing for frontier models before deployment.",
        start_ms=10000,
        end_ms=15000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_embedding_match",
        word_timestamps_ref="parquet_hash_utt_01",
        language="en",
        transcription_pass_count=2,
        dual_pass_agreement=True,
        negation_uncertain=False,
    )

    utt_2 = Utterance(
        utterance_id="utt_valid_02",
        source_id="src_valid_02",
        subject_id="subj_valid_01",
        text_verbatim="Mandatory licensing would destroy open source software innovation in this country.",
        start_ms=45000,
        end_ms=52000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="official_transcript",
        word_timestamps_ref="parquet_hash_utt_02",
        language="en",
        transcription_pass_count=2,
        dual_pass_agreement=True,
        negation_uncertain=False,
    )

    # In utt_1: "federal licensing for frontier models" is at index 19..56
    text_1 = utt_1.text_verbatim
    q1 = "federal licensing for frontier models"
    idx1 = text_1.find(q1)
    span1 = (idx1, idx1 + len(q1))

    # In utt_2: "Mandatory licensing would destroy open source software" is at index 0..54
    text_2 = utt_2.text_verbatim
    q2 = "Mandatory licensing would destroy open source software"
    idx2 = text_2.find(q2)
    span2 = (idx2, idx2 + len(q2))

    claim_1 = Claim(
        claim_id="clm_valid_01",
        subject_id="subj_valid_01",
        utterance_id="utt_valid_01",
        proposition_id="prop_licensing_01",
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.98,
        quote_span=span1,
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
        recorded_at="2024-01-15T10:00:00Z",
    )

    claim_2 = Claim(
        claim_id="clm_valid_02",
        subject_id="subj_valid_01",
        utterance_id="utt_valid_02",
        proposition_id="prop_licensing_01",
        stance="oppose",
        hedging_level=0.05,
        is_own_assertion=True,
        exclusion_reason=None,
        confidence=0.99,
        quote_span=span2,
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
        recorded_at="2024-05-10T14:00:00Z",
    )

    tension_1 = Tension(
        tension_id="tns_valid_01",
        type="unacknowledged_reversal",
        claim_a_id="clm_valid_01",
        claim_b_id="clm_valid_02",
        proposition_id="prop_licensing_01",
        severity=0.85,
        detector_version="v1.0",
        status="published",
    )

    assessment_1 = Assessment(
        assessment_id="asm_valid_01",
        subject_id="subj_valid_01",
        topic_id="top_ai_reg_01",
        rubric_version="v1.2",
        extraction_model_set=["gemma-3-27b-it"],
        detector_version="v1.0",
        embedding_model="nomic-embed-text-v1.5",
        nlp_version="spacy-en-core-web-sm-3.7",
        sufficiency={"passed": True, "claim_count": 2, "source_count": 2, "span_days": 116},
        axes={
            "consistency": {"score": 0.15, "n": 2},
            "specificity": {"score": 0.95, "n": 2, "checkable": 2},
            "update_integrity": {"score": None, "reason": "no_updates_detected", "n": 0},
            "even_handedness": {"score": None, "reason": "pattern_not_significant", "n": 0},
        },
        axis_evidence={"consistency": ["tns_valid_01"]},
        computed_at="2024-05-11T10:00:00Z",
    )

    return (
        [source_1, source_2],
        [utt_1, utt_2],
        [claim_1, claim_2],
        [tension_1],
        [assessment_1],
        [role_1, role_2],
    )


def load_broken_quote_fixture() -> tuple[list[Source], list[Utterance], list[Claim]]:
    """Loads a fixture where a Claim's quote_span points at text that is NOT in text_verbatim."""
    sources, utterances, claims, _, _, _ = load_valid_fixtures()
    # Deliberately corrupt the quote_span to point outside the utterance
    broken_claim = Claim(
        claim_id="clm_broken_01",
        subject_id="subj_valid_01",
        utterance_id="utt_valid_01",
        proposition_id="prop_licensing_01",
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
        confidence=0.95,
        quote_span=(100, 150),  # utt_1 length is only 71 chars!
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
    )
    return sources, utterances, [broken_claim]


def load_broken_anchor_fixture() -> tuple[list[Source], list[Utterance], list[Claim]]:
    """Loads a fixture with an orphan utterance pointing at a non-existent source_id."""
    _, utterances, claims, _, _, _ = load_valid_fixtures()
    broken_utt = Utterance(
        utterance_id="utt_orphan_01",
        source_id="src_non_existent_999",
        subject_id="subj_valid_01",
        text_verbatim="Some text from a deleted source.",
        start_ms=0,
        end_ms=5000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
    )
    return [], [broken_utt], []
