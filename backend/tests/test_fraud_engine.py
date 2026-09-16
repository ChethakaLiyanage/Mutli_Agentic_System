from datetime import date
from decimal import Decimal

from app.fraud.engine import FraudDetectionEngine


def test_engine_returns_high_risk_for_multiple_red_flags():
    claim_data = {
        "claim_id": "claim-001",
        "policy_id": "policy-001",
        "customer_id": "customer-001",
        "policy_number": "MTR-1001",
        "claim_type": "motor_accident",
        "incident_date": "2026-09-15",
        "claimed_amount": Decimal("250000"),
        "incident_description": "Vehicle collision.",
        "police_report_number": "PR-123",
    }

    policy_data = {
        "policy_id": "policy-001",
        "policy_number": "MTR-1001",
        "customer_id": "customer-001",
        "status": "expired",
        "start_date": "2025-01-01",
        "end_date": "2026-08-31",
        "coverage_details": {},
    }

    document_facts = [
        {
            "document_id": "doc-001",
            "document_type": "police_report",
            "incident_date": "2026-09-12",
            "police_report_number": "PR-123",
        },
        {
            "document_id": "doc-002",
            "document_type": "repair_estimate",
            "claimed_amount": Decimal("100000"),
        },
    ]

    historical_claims = [
        {
            "id": "old-claim-001",
            "claim_reference": "CLM-OLD-001",
            "claim_type": "motor_accident",
            "incident_date": "2026-09-14",
            "claimed_amount": "250000",
        }
    ]

    duplicate_police_report_claims = [
        {
            "id": "old-claim-002",
            "claim_reference": "CLM-OLD-002",
        }
    ]

    engine = FraudDetectionEngine()

    assessment = engine.evaluate(
        claim_data=claim_data,
        policy_data=policy_data,
        document_facts=document_facts,
        historical_claims=historical_claims,
        duplicate_police_report_claims=(
            duplicate_police_report_claims
        ),
    )

    rule_ids = {
        indicator.rule_id
        for indicator in assessment.risk_indicators
    }

    assert assessment.risk_level == "high"
    assert assessment.risk_score >= 0.70
    assert "POLICY_INACTIVE" in rule_ids
    assert "DATE_CONFLICT" in rule_ids
    assert "AMOUNT_CONFLICT" in rule_ids
    assert "DUPLICATE_CLAIM" in rule_ids
    assert "REPORT_REFERENCE_DUPLICATE" in rule_ids
    assert assessment.automated_decision is False