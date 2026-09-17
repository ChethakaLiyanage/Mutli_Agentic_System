from datetime import date

from backend.app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    FraudAssessment,
    PolicyData,
)
from backend.app.fraud.rules import (
    flag_policy_inactive,
    flag_late_reporting,
    flag_date_conflict,
    flag_amount_conflict,
)
from backend.app.fraud.history_checks import (
    flag_duplicate_claim,
    flag_duplicate_police_report,
)
from backend.app.fraud.scoring import (
    calculate_rule_score,
    get_recommended_action,
    get_risk_level,
)
from backend.app.fraud.document_checks import get_missing_documents
from backend.app.fraud.repository import FraudRepository
from backend.app.services.supabase_service import get_supabase_client


def fraud_detection_agent(state: dict) -> dict:
    retrieval_res = state.get("retrieval_response") or {}
    result_data = retrieval_res.get("result") or {}

    policy_raw = state.get("policy_data") or result_data.get("policy_data")
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

    docs_list = state.get("document_facts") or result_data.get("document_facts", [])

    claim = ClaimData(**claim_raw)
    policy = PolicyData(**policy_raw)

    documents = [
        DocumentFacts(**document)
        for document in docs_list
    ]

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

    indicators = []

    checks = [
        flag_policy_inactive(
            claim=claim,
            policy=policy
        ),
        flag_late_reporting(
            claim=claim,
            submitted_date=date.today()
        ),
        flag_duplicate_claim(
            claim=claim,
            historical_claims=historical_claims
        ),
        flag_duplicate_police_report(
            claim=claim,
            matching_claims=duplicate_report_claims
        ),
    ]

    indicators.extend(
        item for item in checks
        if item is not None
    )

    indicators.extend(
        flag_date_conflict(
            claim=claim,
            documents=documents
        )
    )

    indicators.extend(
        flag_amount_conflict(
            claim=claim,
            documents=documents
        )
    )

    missing_documents = get_missing_documents(
        claim_type=claim.claim_type,
        documents=documents
    )

    rule_score = calculate_rule_score(indicators)
    risk_level = get_risk_level(rule_score)

    action = get_recommended_action(
        risk_level=risk_level,
        missing_documents=missing_documents
    )

    assessment = FraudAssessment(
        risk_level=risk_level,
        risk_score=rule_score,
        rule_score=rule_score,
        ml_anomaly_score=None,
        risk_indicators=indicators,
        missing_documents=missing_documents,
        recommended_action=action,
        automated_decision=False,
        rules_version="1.0.0",
        model_version=None
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
