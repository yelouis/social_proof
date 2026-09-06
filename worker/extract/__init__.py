"""Claim extraction package."""

from worker.extract.extract import ClaimExtractionPipeline
from worker.extract.gate import ExtractionGate, GateDecision
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.schema import ExtractedClaim, ExtractionResult
from worker.extract.validators import (
    get_exclusion_counts,
    get_exclusion_rate,
    get_stance_correction_counts,
    has_syntactic_negation,
    reset_exclusion_counts,
    reset_stance_correction_counts,
    validate_confidence_floor,
    validate_extracted_claim,
    validate_polarity,
    validate_quote_verbatim,
    validate_schema,
    validate_speech_acts,
    validate_stance_direction,
)

__all__ = [
    "ClaimExtractionPipeline",
    "ExtractedClaim",
    "ExtractionGate",
    "ExtractionResult",
    "GateDecision",
    "LocalGemmaRuntime",
    "get_exclusion_counts",
    "get_exclusion_rate",
    "get_stance_correction_counts",
    "has_syntactic_negation",
    "reset_exclusion_counts",
    "reset_stance_correction_counts",
    "validate_confidence_floor",
    "validate_extracted_claim",
    "validate_polarity",
    "validate_quote_verbatim",
    "validate_schema",
    "validate_speech_acts",
    "validate_stance_direction",
]
