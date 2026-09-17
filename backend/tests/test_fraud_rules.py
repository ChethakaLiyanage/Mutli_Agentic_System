from datetime import date
from decimal import Decimal

from backend.app.fraud.document_checks import (
    flag_amount_conflicts,
    flag_date_conflicts,
    get_missing_documents,
)
from backend.app.fraud.rules import flag_policy_inactive
from backend.app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    PolicyData,
)


def build_claim() -> ClaimData:
    return ClaimData(
        claim_id="claim-001",
        policy_id="policy-001",
        customer_id="customer-001",
        policy_number="MTR-1001",
        claim_type="motor_accident",
        incident_date=date(2026, 9, 15),
        claimed_amount=Decimal("250000"),
        incident_description="Vehicle collision.",
    )


def test_inactive_policy_is_flagged():
    claim = build_claim()

    policy = PolicyData(
        policy_id="policy-001",
        policy_number="MTR-1001",
        customer_id="customer-001",
        status="expired",
        start_date=date(2025, 1, 1),
        end_date=date(2026, 8, 31),
    )

    result = flag_policy_inactive(claim, policy)

    assert result is not None
    assert result.rule_id == "POLICY_INACTIVE"


def test_date_conflict_is_flagged():
    claim = build_claim()

    documents = [
        DocumentFacts(
            document_id="document-001",
            document_type="police_report",
            incident_date=date(2026, 9, 12),
        )
    ]

    results = flag_date_conflicts(claim, documents)

    assert len(results) == 1
    assert results[0].rule_id == "DATE_CONFLICT"


def test_amount_conflict_is_flagged():
    claim = build_claim()

    documents = [
        DocumentFacts(
            document_id="document-002",
            document_type="repair_estimate",
            claim_amount=Decimal("100000"),
        )
    ]

    results = flag_amount_conflicts(claim, documents)

    assert len(results) == 1
    assert results[0].rule_id == "AMOUNT_CONFLICT"


def test_missing_documents_are_detected():
    claim = build_claim()

    documents = [
        DocumentFacts(
            document_id="document-001",
            document_type="police_report",
        )
    ]

    missing = get_missing_documents(
        claim.claim_type,
        documents,
    )

    assert missing == ["repair_estimate"]
