from copy import deepcopy
from typing import Optional, Protocol, runtime_checkable
from supabase import Client

from backend.app.fraud.schemas import FraudAssessment
from backend.app.schemas.domain import FraudAssessmentContext
from backend.app.services.supabase_service import get_supabase_client


@runtime_checkable
class FraudAssessmentRepository(Protocol):
    def save_canonical_assessment(
        self, assessment: FraudAssessmentContext
    ) -> dict: ...


class InMemoryFraudRepository:
    def __init__(self) -> None:
        self.assessments: dict[str, dict] = {}

    def save_canonical_assessment(
        self, assessment: FraudAssessmentContext
    ) -> dict:
        if not assessment.assessment_id or not assessment.claim_id:
            raise ValueError("Assessment and claim identifiers are required")
        if assessment.automated_decision is not False:
            raise ValueError("Fraud triage cannot make an automated decision")
        row = {
            "assessment_id": assessment.assessment_id,
            "claim_id": assessment.claim_id,
            "risk_level": assessment.risk_level.value,
            "risk_score": assessment.risk_score,
            "rule_score": assessment.rule_score,
            "anomaly_score": assessment.anomaly_score,
            "indicators": [item.model_dump(mode="json") for item in assessment.indicators],
            "missing_documents": [item.value for item in assessment.missing_documents],
            "recommended_action": assessment.recommended_action.value,
            "automated_decision": False,
            "rules_version": assessment.rules_version,
            "model_version": assessment.model_version,
        }
        self.assessments[assessment.assessment_id] = deepcopy(row)
        return deepcopy(row)


class FraudRepository:
    def __init__(self, supabase: Optional[Client] = None):
        self.supabase = supabase or get_supabase_client()

    def get_policy_claim_history(
        self,
        policy_id: str,
        exclude_claim_id: str,
    ) -> list[dict]:
        query = (
            self.supabase.table("claims")
            .select(
                "claim_id, claim_reference, incident_type, "
                "incident_date, claimed_amount, claim_status"
            )
            .eq("policy_id", policy_id)
        )
        if exclude_claim_id:
            query = query.neq("claim_id", exclude_claim_id)

        response = query.execute()
        return [self._claim_history_from_row(row) for row in (response.data or [])]

    def get_claims_by_police_report_number(
        self,
        police_report_number: str,
        exclude_claim_id: str,
    ) -> list[dict]:
        if not police_report_number:
            return []

        query = (
            self.supabase.table("claims")
            .select(
                "claim_id, claim_reference, policy_id, customer_id"
            )
            .eq(
                "police_report_number",
                police_report_number,
            )
        )
        if exclude_claim_id:
            query = query.neq("claim_id", exclude_claim_id)

        response = query.execute()
        return [self._claim_identity_from_row(row) for row in (response.data or [])]

    def save_fraud_assessment(
        self,
        claim_id: str,
        assessment: FraudAssessment,
    ) -> dict:
        payload = self.assessment_to_row(claim_id, assessment)

        response = (
            self.supabase.table("fraud_assessments")
            .insert(payload)
            .execute()
        )

        # The caller receives the stable canonical payload rather than a
        # provider-specific response row (which may contain extra columns).
        return payload

    def save_canonical_assessment(
        self,
        assessment: FraudAssessmentContext,
    ) -> dict:
        """Idempotently persist the current assessment by stable identifier."""
        if not assessment.assessment_id or not assessment.claim_id:
            raise ValueError("Assessment and claim identifiers are required")
        if assessment.automated_decision is not False:
            raise ValueError("Fraud triage cannot make an automated decision")
        payload = {
            "assessment_id": assessment.assessment_id,
            "claim_id": assessment.claim_id,
            "risk_level": assessment.risk_level.value,
            "risk_score": assessment.risk_score,
            "rule_score": assessment.rule_score,
            "anomaly_score": assessment.anomaly_score,
            "indicators": [item.model_dump(mode="json") for item in assessment.indicators],
            "missing_documents": [item.value for item in assessment.missing_documents],
            "recommended_action": assessment.recommended_action.value,
            "automated_decision": False,
            "rules_version": assessment.rules_version,
            "model_version": assessment.model_version,
        }
        response = (
            self.supabase.table("fraud_assessments")
            .upsert(payload, on_conflict="assessment_id")
            .execute()
        )
        return dict(response.data[0]) if response.data else payload

    @staticmethod
    def assessment_to_row(
        claim_id: str,
        assessment: FraudAssessment,
    ) -> dict:
        """Serialize the legacy fraud model into canonical storage columns."""
        return {
            "claim_id": claim_id,
            "risk_level": assessment.risk_level,
            "risk_score": assessment.risk_score,
            "rule_score": assessment.rule_score,
            "anomaly_score": assessment.ml_anomaly_score,
            "indicators": [
                item.model_dump(mode="json")
                for item in assessment.risk_indicators
            ],
            "missing_documents": assessment.missing_documents,
            "recommended_action": assessment.recommended_action,
            "automated_decision": False,
            "rules_version": assessment.rules_version,
            "model_version": assessment.model_version,
        }

    @staticmethod
    def _claim_history_from_row(row: dict) -> dict:
        """Translate storage names for the existing fraud engine interface."""
        return {
            "id": row["claim_id"],
            "claim_reference": row["claim_reference"],
            "claim_type": row["incident_type"],
            "incident_date": row["incident_date"],
            "claimed_amount": row.get("claimed_amount"),
            "status": row.get("claim_status"),
        }

    @staticmethod
    def _claim_identity_from_row(row: dict) -> dict:
        return {
            "id": row["claim_id"],
            "claim_reference": row["claim_reference"],
            "policy_id": row["policy_id"],
            "customer_id": row["customer_id"],
        }
