from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.fraud.repository import InMemoryFraudRepository
from backend.app.main import app
from backend.app.orchestrator.claim_repository import InMemoryClaimRepository
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.schemas import PolicyRecord, RetrievalResponse, RetrievalResult
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.domain import FraudAssessmentContext
from backend.app.schemas.intake import (
    IncidentInformation, IntakeData, IntakeResponse, IntentResult,
)
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole


USER = AuthenticatedUser(
    user_id="USR-API-FRAUD", email="fraud-api@example.com",
    role=UserRole.CUSTOMER, created_at=datetime.now(timezone.utc),
)
POLICY = {
    "policy_id": "POL-API-FRAUD", "policy_number": "MTR-API-FRAUD",
    "customer_id": USER.user_id, "status": "active",
    "start_date": "2026-01-01", "end_date": "2027-01-01",
}


class Intake:
    def __init__(self, incomplete=False):
        self.incomplete = incomplete

    async def analyze(self, request):
        incomplete = self.incomplete
        self.incomplete = False
        return IntakeResponse(
            request_id=request.request_id, status="success",
            data=IntakeData(
                intent=IntentResult(label="claim_submission", confidence=.9),
                incident=IncidentInformation(
                    type=None if incomplete else "vehicle_collision",
                    normalized_date=None if incomplete else date.today().isoformat(),
                    location=None if incomplete else "Colombo",
                ),
                missing_fields=(
                    ["incident_type", "incident_date", "location"] if incomplete else []
                ),
                requires_clarification=incomplete,
            ),
        )


class Retrieval:
    async def retrieve(self, request):
        return RetrievalResponse(
            request_id=request.request_id, status="success",
            result=RetrievalResult(policy_data=PolicyRecord(**POLICY)),
        )


class Fraud:
    def __init__(self, fail=False):
        self.fail = fail

    async def assess(self, **kwargs):
        if self.fail:
            raise RuntimeError("private failure")
        return FraudAssessmentContext(
            claim_id=kwargs["claim"].claim_id,
            risk_score=.1, rule_score=0, risk_level="low",
            recommended_action="continue_processing", automated_decision=False,
        )


def _service(*, incomplete=False, fraud_fail=False):
    return OrchestratorService(
        claim_intake_client=Intake(incomplete),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=Retrieval(), fraud_client=Fraud(fraud_fail),
        claim_repository=InMemoryClaimRepository([POLICY]),
        fraud_repository=InMemoryFraudRepository(),
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_customer] = lambda: USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_authenticated_claim_api_ends_at_human_review(client):
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = _service
    response = client.post("/orchestrator/process", json={
        "request_id": "REQ-API-FRAUD",
        "text": "My car collided today in Colombo and I want to claim.",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_type"] == "claim_submission"
    assert body["status"] == "awaiting_human_review"
    assert body["fraud_risk_level"] is None
    assert body["fraud_result"] is None


def test_authenticated_clarification_api_reaches_fraud_pipeline(client):
    service = _service(incomplete=True)
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    first = client.post("/orchestrator/process", json={
        "request_id": "REQ-API-CLARIFY-1", "text": "My car was damaged.",
    })
    workflow_id = first.json()["workflow_id"]
    second = client.post(f"/orchestrator/workflows/{workflow_id}/clarify", json={
        "request_id": "REQ-API-CLARIFY-2", "text": "It collided today in Colombo.",
    })
    assert second.status_code == 200
    assert second.json()["workflow_id"] == workflow_id
    assert second.json()["status"] == "awaiting_human_review"


def test_fraud_api_failure_is_controlled(client):
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: _service(fraud_fail=True)
    )
    response = client.post("/orchestrator/process", json={
        "request_id": "REQ-API-FAIL", "text": "My car collided today in Colombo.",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["errors"][0]["code"] == "FRAUD_TRIAGE_FAILED"
    assert "private failure" not in response.text
