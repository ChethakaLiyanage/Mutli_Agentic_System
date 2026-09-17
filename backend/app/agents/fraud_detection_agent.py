from datetime import date

from app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    FraudAssessment,
    PolicyData,
)
from app.fraud.rules import (
    flag_policy_inactive,
    flag_late_reporting,
    flag_date_conflict,
    flag_amount_conflict,
)
from app.fraud.history_checks import (
    flag_duplicate_claim,
    flag_duplicate_police_report,
)
from app.fraud.scoring import (
    calculate_rule_score,
    get_recommended_action,
    get_risk_level,
)
from app.fraud.document_checks import get_missing_documents
from app.fraud.repository import FraudRepository
from app.services.supabase_service import get_supabase_client


def fraud_detection_agent(state: dict) -> dict:
    claim = ClaimData(**state["claim_data"])
    policy = PolicyData(**state["policy_data"])

    documents = [
        DocumentFacts(**document)
        for document in state.get("document_facts", [])
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

    repository.save_fraud_assessment(
        claim_id=claim.claim_id,
        assessment=assessment
    )

    return {
        "fraud_assessment": assessment.model_dump(mode="json"),
        "next_step": "reviewer_support_agent"
    }