"""HTTP API tests for Orchestrator Step 3."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.main import app
from backend.app.orchestrator.agent_clients import LocalClaimIntakeClient
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.intake import IntakeData, IntakeResponse, IntentResult
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.orchestrator import (
    ClarificationResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole


TEST_USER = AuthenticatedUser(
    user_id="USR-TEST",
    email="test@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)


class FakeOrchestratorService:
    def __init__(
        self,
        response: OrchestratorResponse | ClarificationResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[OrchestratorRequest, str | None, str | None]] = []

    async def process_request(
        self,
        request: OrchestratorRequest,
        authenticated_user_id: str | None = None,
        authenticated_user_role: str | None = None,
    ) -> OrchestratorResponse | ClarificationResponse:
        self.calls.append(
            (request, authenticated_user_id, authenticated_user_role)
        )
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_customer] = lambda: TEST_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_service(service: FakeOrchestratorService) -> None:
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: service
    )


def successful_response(
    workflow_type: WorkflowType,
    *,
    request_id: str,
    intent_label: str,
) -> OrchestratorResponse:
    intake_result = IntakeResponse(
        request_id=request_id,
        status="success",
        data=IntakeData(
            intent=IntentResult(label=intent_label, confidence=0.8),
        ),
    )
    return OrchestratorResponse(
        request_id=request_id,
        workflow_id="WF-TEST",
        status=WorkflowStatus.INTAKE_COMPLETE,
        workflow_type=workflow_type,
        intake_result=intake_result,
    )


def test_complete_claim_uses_real_http_to_agent_one_integration(
    client: TestClient,
) -> None:
    service = OrchestratorService(LocalClaimIntakeClient())
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: service
    )

    response = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ101",
            "text": (
                "A bus hit my car yesterday near Kandy and damaged the left door."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "intake_complete"
    assert body["workflow_type"] == "claim_submission"
    assert body["requires_clarification"] is False
    assert body["missing_fields"] == []
    assert body["intake_result"] is not None
    assert 0.0 <= body["intake_result"]["data"]["intent"]["confidence"] <= 1.0


def test_incomplete_claim_returns_clarification(client: TestClient) -> None:
    missing_fields = ["incident_type", "incident_date", "location"]
    service = FakeOrchestratorService(
        ClarificationResponse(
            request_id="REQ102",
            workflow_id="WF-TEST",
            intake_result=IntakeResponse(
                request_id="REQ102",
                status="success",
                data=IntakeData(
                    intent=IntentResult(
                        label="claim_submission",
                        confidence=0.8,
                    ),
                    missing_fields=missing_fields,
                    requires_clarification=True,
                ),
            ),
            missing_fields=missing_fields,
            questions=[
                "What happened to your vehicle?",
                "When did the incident happen?",
                "Where did the incident happen?",
            ],
            reason="Additional claim information is required",
        )
    )
    override_service(service)

    response = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ102",
            "text": "My car was damaged and I want to claim.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_clarification"
    assert body["workflow_type"] == "clarification"
    assert body["requires_clarification"] is True
    assert body["missing_fields"] == missing_fields
    assert body["questions"] == [
        "What happened to your vehicle?",
        "When did the incident happen?",
        "Where did the incident happen?",
    ]
    assert service.calls[0][1:] == (TEST_USER.user_id, TEST_USER.role.value)


@pytest.mark.parametrize(
    ("request_id", "text", "intent_label", "workflow_type"),
    [
        (
            "REQ103",
            "Does my policy cover flood damage?",
            "coverage_question",
            WorkflowType.INFORMATION_REQUEST,
        ),
        (
            "REQ104",
            "I want to check the status of my claim.",
            "claim_status",
            WorkflowType.CLAIM_STATUS,
        ),
    ],
)
def test_non_claim_workflow_routing_over_http(
    client: TestClient,
    request_id: str,
    text: str,
    intent_label: str,
    workflow_type: WorkflowType,
) -> None:
    service = FakeOrchestratorService(
        successful_response(
            workflow_type,
            request_id=request_id,
            intent_label=intent_label,
        )
    )
    override_service(service)

    response = client.post(
        "/orchestrator/process",
        json={"request_id": request_id, "text": text},
    )

    assert response.status_code == 200
    assert response.json()["workflow_type"] == workflow_type.value


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "", "text": "Valid text"},
        {"request_id": "REQ105", "text": "a"},
        {"request_id": "REQ105"},
        {
            "request_id": "REQ105",
            "text": "I want to make a claim.",
            "user_id": "USR999",
        },
    ],
)
def test_invalid_requests_return_422(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    response = client.post("/orchestrator/process", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_unexpected_service_failure_returns_generic_500(client: TestClient) -> None:
    internal_detail = "secret database path C:/internal/file.db"
    override_service(
        FakeOrchestratorService(error=RuntimeError(internal_detail))
    )

    response = client.post(
        "/orchestrator/process",
        json={"request_id": "REQ106", "text": "A valid request"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Orchestrator service failed"}
    assert internal_detail not in response.text


def test_orchestrator_route_appears_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/orchestrator/process"]["post"]
    assert operation["summary"] == "Process a motor-insurance request"
    assert operation["requestBody"]["required"] is True


def test_existing_health_docs_and_intake_routes_remain_available(
    client: TestClient,
) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/intake/analyze" in paths
    assert "/orchestrator/process" in paths
