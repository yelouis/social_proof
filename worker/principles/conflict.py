"""Principle conflict detector — mechanical join over shared principles with opposing verdicts.

Implements design_principle_extraction.md §6 and agent_execution_guide.md §20.
Enforces:
1. DuckDB SQL self-join (same principle, same subject, different actor, opposite verdict).
2. Unresolved actors ('unknown') are excluded outright.
3. Stated distinction detection routes distinguished pairs away from hypocrisy scoring.
"""

from typing import Any

from worker.entities import Tension
from worker.principles.distinction import StatedDistinctionDetector
from worker.storage import Storage, compute_tension_id


class PrincipleConflictDetector:
    """Detects principle conflicts using DuckDB SQL self-joins and stated distinction gating."""

    def __init__(
        self,
        storage: Storage,
        enable_stated_distinction: bool = True,
        detector_version: str = "v1.0",
    ) -> None:
        self.storage = storage
        self.enable_stated_distinction = enable_stated_distinction
        self.detector_version = detector_version
        self.distinction_detector = StatedDistinctionDetector()

    def detect_conflicts_for_subject(
        self, subject_id: str
    ) -> tuple[list[Tension], list[dict[str, Any]]]:
        """Finds principle conflicts and distinguished pairs for a subject.

        Returns (published_conflicts, distinguished_pairs).
        """
        query = """
            SELECT
                a.application_id AS app_a_id,
                b.application_id AS app_b_id,
                a.principle_id,
                a.claim_id AS claim_a_id,
                b.claim_id AS claim_b_id,
                a.actor AS actor_a,
                b.actor AS actor_b,
                a.verdict AS verdict_a,
                b.verdict AS verdict_b,
                a.stated_distinction AS dist_a,
                b.stated_distinction AS dist_b,
                a.actor_affinity AS aff_a,
                b.actor_affinity AS aff_b
            FROM principle_applications a
            JOIN principle_applications b
              ON a.principle_id = b.principle_id
             AND a.subject_id   = b.subject_id
             AND a.actor       <> b.actor
             AND a.verdict     <> b.verdict
             AND a.application_id < b.application_id
            WHERE a.subject_id = ?
              AND a.actor <> 'unknown' AND b.actor <> 'unknown'
            ORDER BY a.application_id, b.application_id;
        """
        rows = self.storage.con.execute(query, [subject_id]).fetchall()

        published_conflicts: list[Tension] = []
        distinguished_pairs: list[dict[str, Any]] = []

        for r in rows:
            app_a_id = r[0]
            app_b_id = r[1]
            principle_id = r[2]
            claim_a_id = r[3]
            claim_b_id = r[4]
            actor_a = r[5]
            actor_b = r[6]
            verdict_a = r[7]
            verdict_b = r[8]
            dist_a = r[9]
            dist_b = r[10]
            _aff_a = r[11]
            _aff_b = r[12]

            # Check for stated distinction
            has_distinction = False
            distinction_reason: str | None = None

            if self.enable_stated_distinction:
                if dist_a and dist_a.strip():
                    has_distinction = True
                    distinction_reason = dist_a.strip()
                elif dist_b and dist_b.strip():
                    has_distinction = True
                    distinction_reason = dist_b.strip()

            if has_distinction:
                # Recorded as distinguished — excluded from hypocrisy scoring
                distinguished_pairs.append({
                    "app_a_id": app_a_id,
                    "app_b_id": app_b_id,
                    "claim_a_id": claim_a_id,
                    "claim_b_id": claim_b_id,
                    "principle_id": principle_id,
                    "actor_a": actor_a,
                    "actor_b": actor_b,
                    "verdict_a": verdict_a,
                    "verdict_b": verdict_b,
                    "distinction": distinction_reason,
                    "status": "distinguished",
                })
                # Optionally write dismissed tension
                tension_id = compute_tension_id(claim_a_id, claim_b_id, "principle_conflict")
                dismissed_tension = Tension(
                    tension_id=tension_id,
                    type="principle_conflict",
                    claim_a_id=claim_a_id,
                    claim_b_id=claim_b_id,
                    principle_id=principle_id,
                    severity=0.0,
                    detector_version=self.detector_version,
                    status="dismissed",
                    quarantine_reason=f"distinguished: {distinction_reason}",
                )
                self.storage.insert_tension(dismissed_tension)
            else:
                # Real principle conflict
                tension_id = compute_tension_id(claim_a_id, claim_b_id, "principle_conflict")
                conflict_tension = Tension(
                    tension_id=tension_id,
                    type="principle_conflict",
                    claim_a_id=claim_a_id,
                    claim_b_id=claim_b_id,
                    principle_id=principle_id,
                    severity=1.0,
                    detector_version=self.detector_version,
                    status="published",
                    quarantine_reason=None,
                )
                self.storage.insert_tension(conflict_tension)
                published_conflicts.append(conflict_tension)

        return published_conflicts, distinguished_pairs
