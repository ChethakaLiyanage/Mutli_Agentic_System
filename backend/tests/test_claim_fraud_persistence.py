from __future__ import annotations

from backend.app.fraud.repository import InMemoryFraudRepository
from backend.app.orchestrator.claim_repository import (
    InMemoryClaimRepository,
    SupabaseClaimRepository,
)
from backend.app.schemas.domain import ClaimContext, FraudAssessmentContext
from backend.tests._supabase_fake import FakeSupabaseClient


POLICY = {
    "policy_id": "POL-PERSIST", "policy_number": "MTR-PERSIST",
    "customer_id": "USR-PERSIST", "status": "active",
    "start_date": "2026-01-01", "end_date": "2027-01-01",
}


def test_claim_persistence_is_idempotent_per_workflow() -> None:
    repository = InMemoryClaimRepository([POLICY])
    claim = ClaimContext(
        customer_id="USR-PERSIST", incident_type="vehicle_collision",
        incident_date="2026-09-17", incident_location="Colombo",
    )
    first = repository.save_for_workflow(workflow_id="WF-PERSIST", claim=claim)
    second = repository.save_for_workflow(workflow_id="WF-PERSIST", claim=claim)
    assert first.claim_id == second.claim_id
    assert first.claim_reference == second.claim_reference
    assert first.policy_id == "POL-PERSIST"
    assert len(repository.claims_by_workflow) == 1


def test_claim_without_linked_policy_is_saved_as_customer_owned_draft() -> None:
    repository = InMemoryClaimRepository()
    claim = ClaimContext(
        customer_id="USR-NO-POLICY",
        incident_type="vehicle_collision",
        incident_date="2026-09-18",
        incident_location="Kandy",
    )

    stored = repository.save_for_workflow(
        workflow_id="WF-NO-POLICY",
        claim=claim,
    )

    assert stored.claim_id is not None
    assert stored.claim_reference is not None
    assert stored.customer_id == "USR-NO-POLICY"
    assert stored.policy_id is None
    assert stored.policy_number is None
    assert stored.claim_status == "policy_link_required"


def test_supabase_claim_without_policy_uses_canonical_nullable_columns() -> None:
    client = FakeSupabaseClient()
    repository = SupabaseClaimRepository(client)
    claim = ClaimContext(
        customer_id="USR-NO-POLICY",
        incident_type="vehicle_collision",
        incident_date="2026-09-18",
        incident_location="Kandy",
    )

    stored = repository.save_for_workflow(
        workflow_id="WF-SUPABASE-NO-POLICY",
        claim=claim,
    )
    row = client.rows["claims"]["WF-SUPABASE-NO-POLICY"]

    assert stored.claim_status == "policy_link_required"
    assert row["customer_id"] == "USR-NO-POLICY"
    assert row["claim_status"] == "policy_link_required"
    assert "policy_id" not in row
    assert "policy_number" not in row
    assert ("claims", "insert") in client.calls
    assert ("claims", "upsert") not in client.calls


def test_fraud_persistence_preserves_canonical_fields_and_never_decides() -> None:
    repository = InMemoryFraudRepository()
    assessment = FraudAssessmentContext(
        assessment_id="FRA-PERSIST", claim_id="CLM-PERSIST",
        risk_score=.5, rule_score=.4, anomaly_score=.8,
        risk_level="medium", recommended_action="manual_review",
        indicators=[{
            "rule_id": "REPEATED_CLAIMS", "severity": "medium", "weight": 20,
            "title": "Repeated claims", "explanation": "Requires review.",
            "evidence": {"historical_claim_count": 3},
        }],
        missing_documents=["police_report"], automated_decision=False,
        rules_version="1.0.0", model_version="isolation_forest_v1",
    )
    row = repository.save_canonical_assessment(assessment)
    repository.save_canonical_assessment(assessment)
    assert row["claim_id"] == "CLM-PERSIST"
    assert row["indicators"][0]["rule_id"] == "REPEATED_CLAIMS"
    assert row["missing_documents"] == ["police_report"]
    assert row["rules_version"] == "1.0.0"
    assert row["model_version"] == "isolation_forest_v1"
    assert row["automated_decision"] is False
    assert len(repository.assessments) == 1
