"""Pydantic schemas for structured claim extraction and grammar generation.

Implements design_claim_extraction.md §1 & §8 and agent_execution_guide.md §11 (U9).
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChangeMarker(BaseModel):
    acknowledged: bool = True
    reason_given: bool = True
    reason_text: str | None = None


class ExtractedClaim(BaseModel):
    proposition_text: str = Field(
        ...,
        description="Canonical, stance-neutral description of the matter at issue (no polarity).",
    )
    stance: Literal["support", "oppose", "mixed", "hedge"] = Field(
        ...,
        description="The speaker's stance toward the proposition.",
    )
    hedging_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0.0 flat assertion to 1.0 pure hedge.",
    )
    is_own_assertion: bool = Field(
        ...,
        description="True if the speaker asserts this as their own view; False if excluded.",
    )
    exclusion_reason: (
        Literal[
            "reported_speech",
            "hypothetical",
            "sarcasm",
            "steelman",
            "joke",
            "question",
            "quote_agreement_unclear",
            "entailment_ambiguous",
        ]
        | None
    ) = Field(
        default=None,
        description="Reason for exclusion under Invariant I7 if is_own_assertion is False.",
    )
    quote_text: str = Field(
        ...,
        description="Exact verbatim substring from the utterance acting as evidence.",
    )
    condition: str | None = Field(
        default=None,
        description="Text of the antecedent 'if...' clause if conditional.",
    )
    prior_stance_reported: Literal["support", "oppose"] | None = Field(
        default=None,
        description="Self-reported prior stance for Update Integrity.",
    )
    change_marker: ChangeMarker | None = Field(
        default=None,
        description="Change marker detailing acknowledged change of mind.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model extraction confidence score.",
    )


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim] = Field(
        default_factory=list,
        description="Extracted claims list. Empty list is the expected, correct answer for non-claim speech.",
    )
