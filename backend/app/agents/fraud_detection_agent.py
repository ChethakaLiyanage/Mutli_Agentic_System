from backend.app.fraud.engine import FraudDetectionEngine
from backend.app.fraud.repository import FraudRepository
from backend.app.fraud.schemas import ClaimData
from backend.app.services.supabase_service import get_supabase_client


def fraud_detection_agent(state: dict) -> dict:
    retrieval_res = state.get("retrieval_response") or {}
    result_data = retrieval_res.get("result") or {}

    policy_raw = state.get("policy_data") or result_data.get("policy_data")
    if policy_raw is None:
        policy_raw = {
            "policy_id": state.get("policy_id", "unknown-policy"),
            "policy_number": state.get("policy_number", "UNKNOWN"),
            "customer_id": state.get("user_id", "unknown-user"),
            "status": "active",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "coverage_details": {},
        }
    claim_raw = state.get("claim_data") or result_data.get("claim_record")

    if claim_raw is None:
        claim_raw = {
            "claim_id": state.get("claim_id", "draft-claim"),
            "policy_id": (policy_raw or {}).get("policy_id", state.get("policy_id", "")),
            "customer_id": state.get("user_id", ""),
            "policy_number": (policy_raw or {}).get("policy_number", state.get("policy_number", "")),
            "claim_type": state.get("incident_type", "motor_accident"),
            "incident_date": state.get("incident_date", "2026-09-15"),
            "incident_location": state.get("incident_location"),
            "claimed_amount": state.get("claimed_amount", 0),
            "incident_description": state.get("incident_description", "Claim submission"),
            "police_report_number": state.get("police_report_number"),
        }

    claim = ClaimData(**claim_raw)
    docs_list = state.get("document_facts") or result_data.get("document_facts", [])

    repository = FraudRepository(get_supabase_client())

    historical_claims = repository.get_policy_claim_history(
        policy_id=claim.policy_id,
        exclude_claim_id=claim.claim_id
    )

    duplicate_report_claims = (
        repository.get_claims_by_police_report_number(
            police_report_number=claim.police_report_number,
            exclude_claim_id=claim.claim_id
        )
        if claim.police_report_number
        else []
    )

    assessment = FraudDetectionEngine().evaluate(
        claim_data=claim_raw,
        policy_data=policy_raw,
        document_facts=docs_list,
        historical_claims=historical_claims,
        duplicate_police_report_claims=duplicate_report_claims,
    )

    try:
        repository.save_fraud_assessment(
            claim_id=claim.claim_id,
            assessment=assessment
        )
    except Exception:
        pass

    return {
        "fraud_assessment": assessment.model_dump(mode="json"),
        "next_step": "reviewer_support_agent"
    }
