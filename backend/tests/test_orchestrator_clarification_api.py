"""HTTP tests for persisted Orchestrator clarification continuation."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.main import app
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.intake import (
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.orchestrator import ClarificationRequest, OrchestratorRequest
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole


TEST_USER = AuthenticatedUser(
    user_id="USR-TEST",
    email="test@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)


class TwoTurnIntakeClient:
    def __init__(self, complete_on_second_call: bool = True) -> None:
        self.complete_on_second_call = complete_on_second_call
        self.calls = 0

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.calls += 1
        complete = self.calls > 1 and self.complete_on_second_call
        return IntakeResponse(
            request_id=request.request_id,
            status="success",
            data=IntakeData(
                intent=IntentResult(label="claim_submission", confidence=0.8),
                missing_fields=(
                    []
                    if complete
                    else ["incident_type", "incident_date", "location"]
                ),
                requires_clarification=not complete,
            ),
        )


class FailingResumeService:
    async def resume_clarification(self, *_args, **_kwargs):
        raise RuntimeError("private exception detail")


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_customer] = lambda: TEST_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def use_service(service) -> None:
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: service
    )


def test_full_http_clarification_sequence_reuses_workflow_id(
    client: TestClient,
) -> None:
    service = OrchestratorService(
        TwoTurnIntakeClient(),
        InMemoryWorkflowRepository(),
    )
    use_service(service)

    initial = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ301",
            "text": "My car was damaged and I want to claim.",
        },
    )
    assert initial.status_code == 200
    first_body = initial.json()
    assert first_body["status"] == "awaiting_clarification"
    assert first_body["workflow_id"].startswith("WF-")

    resumed = client.post(
        f"/orchestrator/workflows/{first_body['workflow_id']}/clarify",
        json={
            "request_id": "REQ302",
            "text": "A bus hit my car yesterday near Kandy.",
        },
    )
    assert resumed.status_code == 200
    second_body = resumed.json()
    assert second_body["request_id"] == "REQ302"
    assert second_body["workflow_id"] == first_body["workflow_id"]
    assert second_body["status"] == "intake_complete"
    assert second_body["workflow_type"] == "claim_submission"
    assert second_body["requires_clarification"] is False
    assert second_body["missing_fields"] == []


def test_unknown_workflow_returns_404(client: TestClient) -> None:
    use_service(
        OrchestratorService(
            TwoTurnIntakeClient(),
            InMemoryWorkflowRepository(),
        )
    )

    response = client.post(
        "/orchestrator/workflows/WF-DOES-NOT-EXIST/clarify",
        json={"request_id": "REQ302", "text": "More information"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workflow not found"}


def test_client_cannot_supply_an_initial_workflow_id(client: TestClient) -> None:
    response = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ301",
            "workflow_id": "WF-CLIENT-CREATED",
            "text": "I want to make a claim.",
        },
    )

    assert response.status_code == 422


def test_completed_workflow_returns_409(client: TestClient) -> None:
    service = OrchestratorService(
        TwoTurnIntakeClient(complete_on_second_call=True),
        InMemoryWorkflowRepository(),
    )

    async def create_completed_workflow() -> str:
        first = await service.process_request(
            OrchestratorRequest(request_id="REQ301", text="An incomplete claim"),
            authenticated_user_id=TEST_USER.user_id,
            authenticated_user_role=TEST_USER.role.value,
        )
        second = await service.resume_clarification(
            first.workflow_id,
            ClarificationRequest(
                request_id="REQ302",
                text="Complete clarification information",
            ),
            authenticated_user_id=TEST_USER.user_id,
            authenticated_user_role=TEST_USER.role.value,
        )
        return second.workflow_id

    workflow_id = asyncio.run(create_completed_workflow())
    use_service(service)
    response = client.post(
        f"/orchestrator/workflows/{workflow_id}/clarify",
        json={"request_id": "REQ303", "text": "Another reply"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Workflow is not awaiting clarification"
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "", "text": "Valid clarification"},
        {"request_id": "REQ302", "text": "x"},
        {"request_id": "REQ302"},
        {
            "request_id": "REQ302",
            "text": "Valid clarification",
            "user_id": "UNTRUSTED",
        },
        {
            "request_id": "REQ302",
            "text": "Valid clarification",
            "workflow_id": "WF-CLIENT-CREATED",
        },
    ],
)
def test_invalid_clarification_body_returns_422(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    response = client.post(
        "/orchestrator/workflows/WF-TEST/clarify",
        json=payload,
    )

    assert response.status_code == 422


def test_unexpected_resume_failure_returns_generic_500(client: TestClient) -> None:
    use_service(FailingResumeService())

    response = client.post(
        "/orchestrator/workflows/WF-TEST/clarify",
        json={"request_id": "REQ302", "text": "Valid clarification"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Orchestrator service failed"}
    assert "private exception detail" not in response.text


def test_clarification_endpoint_appears_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/orchestrator/workflows/{workflow_id}/clarify" in paths
