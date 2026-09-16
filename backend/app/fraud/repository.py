from supabase import Client

from app.fraud.schemas import FraudAssessment


class FraudRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def get_policy_claim_history(
        self,
        policy_id: str,
        exclude_claim_id: str,
    ) -> list[dict]:
        response = (
            self.supabase.table("claims")
            .select(
                "id, claim_reference, claim_type, "
                "incident_date, claimed_amount, status"
            )
            .eq("policy_id", policy_id)
            .neq("id", exclude_claim_id)
            .execute()
        )

        return response.data or []

    def get_claims_by_police_report_number(
        self,
        police_report_number: str,
        exclude_claim_id: str,
    ) -> list[dict]:
        if not police_report_number:
            return []

        response = (
            self.supabase.table("claims")
            .select(
                "id, claim_reference, policy_id, customer_id"
            )
            .eq(
                "police_report_number",
                police_report_number,
            )
            .neq("id", exclude_claim_id)
            .execute()
        )

        return response.data or []

    def save_fraud_assessment(
        self,
        claim_id: str,
        assessment: FraudAssessment,
    ) -> dict:
        payload = {
            "claim_id": claim_id,
            "risk_level": assessment.risk_level,
            "risk_score": assessment.risk_score,
            "rule_score": assessment.rule_score,
            "ml_anomaly_score": assessment.ml_anomaly_score,
            "risk_indicators": [
                item.model_dump(mode="json")
                for item in assessment.risk_indicators
            ],
            "missing_documents": assessment.missing_documents,
            "recommended_action": assessment.recommended_action,
            "automated_decision": False,
            "rules_version": assessment.rules_version,
            "model_version": assessment.model_version,
        }

        response = (
            self.supabase.table("fraud_assessments")
            .insert(payload)
            .execute()
        )

        return response.data[0] if response.data else payload