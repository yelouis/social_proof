"""Tension Detection Engine — design_rubric_engine.md §1, design_data_layer.md §4.

Implements all four tension types:
1. unacknowledged_reversal: same proposition, opposing stance, no acknowledgement in interval
2. acknowledged_update: same proposition, opposing stance, with acknowledgement in interval (Trap 2)
3. principle_conflict: stubbed until P5
4. audience_divergence: same proposition, opposing stance in short window across diverging venues

Enforces the six preconditions (own assertion, attribution confidence, stance in {support, oppose},
condition matching, quote span resolution, negation certainty). Precondition failures write status: quarantined.
"""

from typing import Any

from worker.entities import Tension
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import validate_self_contained
from worker.storage import Storage, compute_tension_id


class TensionDetector:
    """Detects tensions between claims using DuckDB SQL self-joins and precondition gating."""

    def __init__(
        self,
        storage: Storage,
        detector_version: str = "v1.0",
        full_interval_search: bool = True,
    ) -> None:
        self.storage = storage
        self.detector_version = detector_version
        self.full_interval_search = full_interval_search

    def detect_tensions_for_subject(
        self,
        subject_id: str,
        topic_proposition_ids: list[str] | None = None,
    ) -> list[Tension]:
        """Runs the reversal self-join in DuckDB SQL and gates candidates through the six preconditions.

        Writes detected tensions (both published and quarantined) to storage.
        """
        # 1. SQL Self-Join Query in DuckDB (design_data_layer.md §4)
        query = """
            SELECT
                a.claim_id AS claim_a_id,
                b.claim_id AS claim_b_id,
                a.proposition_id,
                a.stance AS stance_a,
                b.stance AS stance_b,
                a.hedging_level AS hedging_a,
                b.hedging_level AS hedging_b,
                a.condition AS condition_a,
                b.condition AS condition_b,
                a.recorded_at AS rec_a,
                b.recorded_at AS rec_b,
                a.utterance_id AS utt_a_id,
                b.utterance_id AS utt_b_id,
                a.quote_span_start AS q_start_a,
                a.quote_span_end AS q_end_a,
                b.quote_span_start AS q_start_b,
                b.quote_span_end AS q_end_b,
                a.quote_text AS quote_text_a,
                b.quote_text AS quote_text_b,
                ua.attribution_confidence AS attr_conf_a,
                ub.attribution_confidence AS attr_conf_b,
                ua.negation_uncertain AS neg_unc_a,
                ub.negation_uncertain AS neg_unc_b,
                ua.transcription_pass_count AS pass_count_a,
                ub.transcription_pass_count AS pass_count_b,
                ua.text_verbatim AS text_a,
                ub.text_verbatim AS text_b
            FROM claims a
            JOIN claims b
              ON a.proposition_id = b.proposition_id
             AND a.subject_id = b.subject_id
             AND TRY_CAST(a.recorded_at AS TIMESTAMPTZ) < TRY_CAST(b.recorded_at AS TIMESTAMPTZ)
             AND a.stance <> b.stance
            JOIN utterances ua ON a.utterance_id = ua.utterance_id
            JOIN utterances ub ON b.utterance_id = ub.utterance_id
            WHERE a.subject_id = ?
              AND a.is_own_assertion AND b.is_own_assertion
              AND a.stance IN ('support', 'oppose')
              AND b.stance IN ('support', 'oppose')
        """
        params: list[Any] = [subject_id]
        if topic_proposition_ids is not None:
            placeholders = ", ".join("?" for _ in topic_proposition_ids)
            query += f" AND a.proposition_id IN ({placeholders})"
            params.extend(topic_proposition_ids)

        query += " ORDER BY a.recorded_at, b.recorded_at;"

        rows = self.storage.con.execute(query, params).fetchall()

        tensions: list[Tension] = []
        for r in rows:
            claim_a_id = r[0]
            claim_b_id = r[1]
            prop_id = r[2]
            _stance_a = r[3]
            _stance_b = r[4]
            hedging_a = float(r[5]) if r[5] is not None else 0.0
            hedging_b = float(r[6]) if r[6] is not None else 0.0
            condition_a = r[7]
            condition_b = r[8]
            rec_a = r[9]
            rec_b = r[10]
            _utt_a_id = r[11]
            _utt_b_id = r[12]
            q_start_a = r[13]
            q_end_a = r[14]
            q_start_b = r[15]
            q_end_b = r[16]
            _q_text_a = r[17]
            _q_text_b = r[18]
            attr_conf_a = str(r[19]).lower() if r[19] is not None else ""
            attr_conf_b = str(r[20]).lower() if r[20] is not None else ""
            neg_unc_a = bool(r[21])
            neg_unc_b = bool(r[22])
            pass_count_a = int(r[23]) if r[23] is not None else 2
            pass_count_b = int(r[24]) if r[24] is not None else 2
            text_a = r[25] or ""
            text_b = r[26] or ""

            # 2. Six Precondition Checks (design_rubric_engine.md §1)
            quarantine_reason: str | None = None

            # Precondition 1: Negation certainty
            if neg_unc_a or neg_unc_b:
                quarantine_reason = "negation_uncertain"
            # Precondition 2: Attribution confidence high
            elif attr_conf_a != "high" or attr_conf_b != "high":
                quarantine_reason = "low_attribution_confidence"
            # Precondition 3: Transcription pass count >= 2
            elif pass_count_a < 2 or pass_count_b < 2:
                quarantine_reason = "insufficient_transcription_passes"
            # Precondition 4: Matching condition
            elif (condition_a or "").strip() != (condition_b or "").strip():
                quarantine_reason = "condition_mismatch"
            # Precondition 5: Quote span resolution against stored text
            elif (
                q_start_a < 0
                or q_end_a > len(text_a)
                or q_start_a >= q_end_a
                or q_start_b < 0
                or q_end_b > len(text_b)
                or q_start_b >= q_end_b
            ):
                quarantine_reason = "quote_span_unresolved"
            # Precondition 6: Proposition must be active and self-contained (non-indexical)
            elif prop_id:
                prop_obj = self.storage.get_proposition(prop_id)
                if prop_obj and prop_obj.status == "quarantined":
                    quarantine_reason = prop_obj.quarantine_reason or "fabricated_proposition"
                elif prop_obj:
                    dummy_claim = ExtractedClaim(
                        proposition_text=prop_obj.canonical_text,
                        stance="support",
                        hedging_level=0.0,
                        is_own_assertion=True,
                        quote_text="dummy quote",
                        confidence=0.9,
                    )
                    outcome_sc = validate_self_contained(dummy_claim)
                    if not outcome_sc.is_valid:
                        quarantine_reason = outcome_sc.rejection_reason or "proposition_not_self_contained"

            # 3. Acknowledgement Window Search (Trap 2)
            # Check if any claim in the interval carries a change marker
            is_acknowledged = False
            if self.full_interval_search:
                ack_query = """
                    SELECT count(*)
                    FROM claims
                    WHERE subject_id = ?
                      AND proposition_id = ?
                      AND TRY_CAST(recorded_at AS TIMESTAMPTZ) >= TRY_CAST(? AS TIMESTAMPTZ)
                      AND TRY_CAST(recorded_at AS TIMESTAMPTZ) <= TRY_CAST(? AS TIMESTAMPTZ)
                      AND (
                          (change_marker IS NOT NULL AND change_marker <> '' AND change_marker <> 'false' AND change_marker <> 'null')
                          OR prior_stance_reported IS NOT NULL
                      );
                """
                ack_count = self.storage.con.execute(ack_query, [subject_id, prop_id, rec_a, rec_b]).fetchone()
                if ack_count and ack_count[0] > 0:
                    is_acknowledged = True
            else:
                # Falsification mode: check only the second utterance
                ack_query = """
                    SELECT count(*)
                    FROM claims
                    WHERE claim_id = ?
                      AND (
                          (change_marker IS NOT NULL AND change_marker <> '' AND change_marker <> 'false' AND change_marker <> 'null')
                          OR prior_stance_reported IS NOT NULL
                      );
                """
                ack_count = self.storage.con.execute(ack_query, [claim_b_id]).fetchone()
                if ack_count and ack_count[0] > 0:
                    is_acknowledged = True

            # 4. Determine Tension Type and Severity
            tension_type = "acknowledged_update" if is_acknowledged else "unacknowledged_reversal"
            severity = float(max(0.0, min(1.0, (1.0 - hedging_a) * (1.0 - hedging_b))))
            status = "quarantined" if quarantine_reason is not None else "published"
            tension_id = compute_tension_id(claim_a_id, claim_b_id, tension_type)

            existing_t = self.storage.get_tension(tension_id)
            if existing_t and existing_t.status == "quarantined":
                status = "quarantined"
                quarantine_reason = existing_t.quarantine_reason

            tension = Tension(
                tension_id=tension_id,
                type=tension_type,  # type: ignore[arg-type]
                claim_a_id=claim_a_id,
                claim_b_id=claim_b_id,
                proposition_id=prop_id,
                principle_id=None,
                severity=severity,
                detector_version=self.detector_version,
                status=status,  # type: ignore[arg-type]
                quarantine_reason=quarantine_reason,
            )
            self.storage.insert_tension(tension)
            tensions.append(tension)

        return tensions

    def detect_audience_divergence_for_subject(
        self,
        subject_id: str,
        window_days: int = 30,
    ) -> list[Tension]:
        """Detects audience divergence: opposing stance within a short window across venues of differing audience_stance."""
        query = """
            SELECT
                a.claim_id AS claim_a_id,
                b.claim_id AS claim_b_id,
                a.proposition_id,
                a.hedging_level AS hedging_a,
                b.hedging_level AS hedging_b,
                ra.audience_stance AS stance_role_a,
                rb.audience_stance AS stance_role_b,
                ua.attribution_confidence AS attr_conf_a,
                ub.attribution_confidence AS attr_conf_b,
                ua.negation_uncertain AS neg_unc_a,
                ub.negation_uncertain AS neg_unc_b,
                ua.text_verbatim AS text_a,
                ub.text_verbatim AS text_b,
                a.quote_span_start AS q_start_a,
                a.quote_span_end AS q_end_a,
                b.quote_span_start AS q_start_b,
                b.quote_span_end AS q_end_b
            FROM claims a
            JOIN claims b
              ON a.proposition_id = b.proposition_id
             AND a.subject_id = b.subject_id
             AND TRY_CAST(a.recorded_at AS TIMESTAMPTZ) < TRY_CAST(b.recorded_at AS TIMESTAMPTZ)
             AND a.stance <> b.stance
            JOIN utterances ua ON a.utterance_id = ua.utterance_id
            JOIN utterances ub ON b.utterance_id = ub.utterance_id
            JOIN source_roles ra ON ra.source_id = ua.source_id AND ra.subject_id = a.subject_id
            JOIN source_roles rb ON rb.source_id = ub.source_id AND rb.subject_id = b.subject_id
            WHERE a.subject_id = ?
              AND a.is_own_assertion AND b.is_own_assertion
              AND a.stance IN ('support', 'oppose')
              AND b.stance IN ('support', 'oppose')
              AND ra.audience_stance IS NOT NULL
              AND rb.audience_stance IS NOT NULL
              AND ra.audience_stance <> rb.audience_stance
              AND abs(epoch(TRY_CAST(b.recorded_at AS TIMESTAMPTZ)) - epoch(TRY_CAST(a.recorded_at AS TIMESTAMPTZ))) <= ? * 86400
            ORDER BY a.recorded_at, b.recorded_at;
        """
        rows = self.storage.con.execute(query, [subject_id, window_days]).fetchall()
        tensions: list[Tension] = []
        for r in rows:
            claim_a_id = r[0]
            claim_b_id = r[1]
            prop_id = r[2]
            hedging_a = float(r[3]) if r[3] is not None else 0.0
            hedging_b = float(r[4]) if r[4] is not None else 0.0
            attr_conf_a = str(r[7]).lower() if r[7] is not None else ""
            attr_conf_b = str(r[8]).lower() if r[8] is not None else ""
            neg_unc_a = bool(r[9])
            neg_unc_b = bool(r[10])
            text_a = r[11] or ""
            text_b = r[12] or ""
            q_start_a = r[13]
            q_end_a = r[14]
            q_start_b = r[15]
            q_end_b = r[16]

            quarantine_reason: str | None = None
            if neg_unc_a or neg_unc_b:
                quarantine_reason = "negation_uncertain"
            elif attr_conf_a != "high" or attr_conf_b != "high":
                quarantine_reason = "low_attribution_confidence"
            elif (
                q_start_a < 0
                or q_end_a > len(text_a)
                or q_start_a >= q_end_a
                or q_start_b < 0
                or q_end_b > len(text_b)
                or q_start_b >= q_end_b
            ):
                quarantine_reason = "quote_span_unresolved"
            elif prop_id:
                prop_obj = self.storage.get_proposition(prop_id)
                if prop_obj and prop_obj.status == "quarantined":
                    quarantine_reason = prop_obj.quarantine_reason or "fabricated_proposition"
                elif prop_obj:
                    dummy_claim = ExtractedClaim(
                        proposition_text=prop_obj.canonical_text,
                        stance="support",
                        hedging_level=0.0,
                        is_own_assertion=True,
                        quote_text="dummy quote",
                        confidence=0.9,
                    )
                    outcome_sc = validate_self_contained(dummy_claim)
                    if not outcome_sc.is_valid:
                        quarantine_reason = outcome_sc.rejection_reason or "proposition_not_self_contained"

            tension_type = "audience_divergence"
            severity = float(max(0.0, min(1.0, (1.0 - hedging_a) * (1.0 - hedging_b))))
            status = "quarantined" if quarantine_reason is not None else "published"
            tension_id = compute_tension_id(claim_a_id, claim_b_id, tension_type)

            tension = Tension(
                tension_id=tension_id,
                type=tension_type,  # type: ignore[arg-type]
                claim_a_id=claim_a_id,
                claim_b_id=claim_b_id,
                proposition_id=prop_id,
                principle_id=None,
                severity=severity,
                detector_version=self.detector_version,
                status=status,  # type: ignore[arg-type]
                quarantine_reason=quarantine_reason,
            )
            self.storage.insert_tension(tension)
            tensions.append(tension)

        return tensions

    def detect_principle_conflicts_for_subject(self, subject_id: str) -> list[Tension]:
        """Detects principle conflicts using PrincipleConflictDetector."""
        from worker.principles.conflict import PrincipleConflictDetector

        detector = PrincipleConflictDetector(
            storage=self.storage,
            detector_version=self.detector_version,
        )
        conflicts, _ = detector.detect_conflicts_for_subject(subject_id)
        return conflicts

    def detect_all_tensions_for_subject(self, subject_id: str) -> list[Tension]:
        """Runs reversal, update, audience divergence, and principle conflict detection for a subject."""
        reversals_and_updates = self.detect_tensions_for_subject(subject_id)
        audience_divs = self.detect_audience_divergence_for_subject(subject_id)
        principle_conflicts = self.detect_principle_conflicts_for_subject(subject_id)
        return reversals_and_updates + audience_divs + principle_conflicts

    def detect_all_tensions(self) -> list[Tension]:
        """Sweeps all subjects in storage and returns all detected tensions."""
        subjects = self.storage.con.execute("SELECT DISTINCT subject_id FROM subjects").fetchall()
        all_tensions: list[Tension] = []
        for row in subjects:
            all_tensions.extend(self.detect_all_tensions_for_subject(row[0]))
        return all_tensions
