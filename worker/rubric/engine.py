"""Rubric engine orchestrator.

Implements design_rubric_engine.md and agent_execution_guide.md §21 (P6).
Pure arithmetic and SQL over existing rows; zero LLM calls at scoring time.
Strictly enforces:
1. No composite score anywhere.
2. Below-gate scores are not computed (null with reason).
3. Full provenance version stamping.
"""

import time
from datetime import datetime
from typing import Any

from worker.entities import Assessment, Claim, Tension
from worker.rubric.consistency import ConsistencyCalculator
from worker.rubric.even_handedness import EvenHandednessCalculator
from worker.rubric.specificity import SpecificityCalculator
from worker.rubric.update_integrity import UpdateIntegrityCalculator
from worker.storage import Storage, compute_assessment_id


class RubricEngine:
    """Orchestrates deterministic rubric evaluation for a subject across four axes."""

    def __init__(
        self,
        storage: Storage,
        rubric_version: str = "v1.0",
        detector_version: str = "v1.0",
        embedding_model: str = "nomic-embed-text-v1.5",
        nlp_version: str = "v1.0-regex-ner",
        extraction_model_set: list[str] | None = None,
    ) -> None:
        self.storage = storage
        self.rubric_version = rubric_version
        self.detector_version = detector_version
        self.embedding_model = embedding_model
        self.nlp_version = nlp_version
        self.extraction_model_set = extraction_model_set or ["google/gemma-3-27b-it"]

        self.consistency_calc = ConsistencyCalculator()
        self.specificity_calc = SpecificityCalculator()
        self.update_calc = UpdateIntegrityCalculator()
        self.even_handedness_calc = EvenHandednessCalculator()

    def assess_subject_topic(
        self,
        subject_id: str,
        topic_id: str = "global",
        claim_ids: list[str] | None = None,
        override_claims: list[Claim] | None = None,
        override_tensions: list[Tension] | None = None,
        quote_texts_by_claim_id: dict[str, str] | None = None,
        conflict_directions: list[int] | None = None,
    ) -> Assessment:
        """Computes four-axis assessment for a subject within a topic slice.

        If override_claims or override_tensions are provided, uses them directly.
        Otherwise queries storage.
        """
        # 1. Fetch claims
        if override_claims is not None:
            claims = override_claims
        else:
            all_claims = self.storage.get_claims_for_subject(subject_id)
            if claim_ids is not None:
                claim_set = set(claim_ids)
                claims = [c for c in all_claims if c.claim_id in claim_set]
            else:
                claims = all_claims

        # 2. Fetch tensions
        if override_tensions is not None:
            tensions = override_tensions
        else:
            tensions = self.storage.get_tensions_for_subject(subject_id)

        # 3. Compute sufficiency summary
        claim_count = len(claims)
        sources: set[str] = set()
        dates: list[datetime] = []
        for c in claims:
            if hasattr(c, "source_id") and c.source_id:
                sources.add(c.source_id)
            if c.recorded_at:
                try:
                    dt = datetime.fromisoformat(c.recorded_at.replace("Z", "+00:00"))
                    dates.append(dt)
                except ValueError:
                    pass

        span_days = 0
        if len(dates) >= 2:
            span_days = max(0, (max(dates) - min(dates)).days)

        sufficiency: dict[str, Any] = {
            "claim_count": claim_count,
            "source_count": max(len(sources), 1 if claim_count > 0 else 0),
            "span_days": span_days,
        }

        # 4. Compute axes independently (per-axis sufficiency gating)
        res_consistency = self.consistency_calc.calculate(claims, tensions)
        res_specificity = self.specificity_calc.calculate(claims, quote_texts_by_claim_id)
        res_update = self.update_calc.calculate(tensions)
        res_even = self.even_handedness_calc.calculate(tensions, conflict_directions)

        axes: dict[str, Any] = {
            "consistency": {
                "score": res_consistency["score"],
                "n": res_consistency["n"],
                **({"reason": res_consistency["reason"]} if res_consistency.get("reason") else {}),
            },
            "specificity": {
                "score": res_specificity["score"],
                "n": res_specificity["n"],
                "checkable": res_specificity.get("checkable", 0),
                **({"reason": res_specificity["reason"]} if res_specificity.get("reason") else {}),
            },
            "update_integrity": {
                "score": res_update["score"],
                "n": res_update["n"],
                **({"reason": res_update["reason"]} if res_update.get("reason") else {}),
            },
            "even_handedness": {
                "score": res_even["score"],
                "n": res_even["n"],
                **({"reason": res_even["reason"]} if res_even.get("reason") else {}),
                **({"p_value": res_even["p_value"]} if "p_value" in res_even else {}),
            },
        }

        axis_evidence: dict[str, list[str]] = {
            "consistency": res_consistency.get("evidence", []),
            "specificity": res_specificity.get("evidence", []),
            "update_integrity": res_update.get("evidence", []),
            "even_handedness": res_even.get("evidence", []),
        }

        assessment_id = compute_assessment_id(subject_id, topic_id, self.rubric_version)
        computed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        assessment = Assessment(
            assessment_id=assessment_id,
            subject_id=subject_id,
            topic_id=topic_id,
            rubric_version=self.rubric_version,
            extraction_model_set=self.extraction_model_set,
            detector_version=self.detector_version,
            embedding_model=self.embedding_model,
            nlp_version=self.nlp_version,
            sufficiency=sufficiency,
            axes=axes,
            axis_evidence=axis_evidence,
            computed_at=computed_at,
        )

        self.storage.insert_assessment(assessment)
        return assessment
