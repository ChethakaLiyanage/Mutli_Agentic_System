"""Authenticated HTTP integration tests for workflow ownership enforcement."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.config import Settings, get_settings
from backend.app.main import app
from backend.app.orchestrator.agent_clients import LocalClaimIntakeClient
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.intake import (
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.security.dependencies import get_user_repository
from backend.app.security.jwt import create_access_token
from backend.app.security.password import hash_password
from backend.app.security.roles import UserRole
from backend.app.security.user_repository import InMemoryUserRepository


OWNERSHIP_SETTINGS = Settings(
    jwt_secret="ownership-tests-only-secret-long-enough",
    jwt_access_token_expire_minutes=15,
)


class CountingIncompleteIntakeClient:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.calls += 1
        return IntakeResponse(
            request_id=request.request_id,
            status="success",
            data=IntakeData(
                intent=IntentResult(label="claim_submission", confidence=0.8),
                missing_fields=["incident_type", "incident_date", "location"],
                requires_clarification=True,
            ),
        )


@pytest.fixture
def ownership_client() -> Iterator[
    tuple[TestClient, InMemoryUserRepository, InMemoryWorkflowRepository]
]:
    user_repository = InMemoryUserRepository()
    workflow_repository = InMemoryWorkflowRepository()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_settings] = lambda: OWNERSHIP_SETTINGS
    with TestClient(app) as client:
        yield client, user_repository, workflow_repository
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    registered = client.post(
        "/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "securepass123"},
    )
    assert login.status_code == 200
    return registered.json()["user_id"], login.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_full_authenticated_real_agent_workflow_resumes_for_owner(
    ownership_client: tuple[
        TestClient,
        InMemoryUserRepository,
        InMemoryWorkflowRepository,
    ],
) -> None:
    client, _, workflow_repository = ownership_client
    service = OrchestratorService(
        LocalClaimIntakeClient(),
        workflow_repository,
    )
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: service
    )
    user_id, token = register_and_login(client, "owner@example.com")

    initial = client.post(
        "/orchestrator/process",
        headers=bearer(token),
        json={
            "request_id": "REQ501",
            "text": "My car was damaged and I want to claim.",
        },
    )
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["status"] == "awaiting_clarification"

    resumed = client.post(
        (
            "/orchestrator/workflows/"
            f"{initial_body['workflow_id']}/clarify"
        ),
        headers=bearer(token),
        json={
            "request_id": "REQ502",
            "text": "A bus hit my car yesterday near Kandy.",
        },
    )
    assert resumed.status_code == 200
    resumed_body = resumed.json()
    assert resumed_body["workflow_id"] == initial_body["workflow_id"]
    assert resumed_body["status"] == "intake_complete"
    assert resumed_body["workflow_type"] == "claim_submission"

    saved = asyncio.run(workflow_repository.get(initial_body["workflow_id"]))
    assert saved is not None
    assert saved.authenticated_user_id == user_id
    assert saved.authenticated_user_role == "customer"


def test_cross_user_clarification_is_forbidden_without_mutation_or_agent_call(
    ownership_client: tuple[
        TestClient,
        InMemoryUserRepository,
        InMemoryWorkflowRepository,
    ],
) -> None:
    client, _, workflow_repository = ownership_client
    intake_client = CountingIncompleteIntakeClient()
    service = OrchestratorService(intake_client, workflow_repository)
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: service
    )
    _, owner_token = register_and_login(client, "owner@example.com")
    _, other_token = register_and_login(client, "other@example.com")

    initial = client.post(
        "/orchestrator/process",
        headers=bearer(owner_token),
        json={"request_id": "REQ510", "text": "I want to make a claim."},
    )
    workflow_id = initial.json()["workflow_id"]
    before = asyncio.run(workflow_repository.get(workflow_id))
    assert before is not None
    calls_before = intake_client.calls

    denied = client.post(
        f"/orchestrator/workflows/{workflow_id}/clarify",
        headers=bearer(other_token),
        json={"request_id": "REQ511", "text": "Attempted clarification"},
    )

    assert denied.status_code == 403
    assert denied.json() == {
        "detail": "You are not authorized to access this workflow"
    }
    assert set(denied.json()) == {"detail"}
    assert intake_client.calls == calls_before
    after = asyncio.run(workflow_repository.get(workflow_id))
    assert after == before


def test_orchestrator_requires_authentication_and_rejects_identity_spoofing(
    ownership_client: tuple[
        TestClient,
        InMemoryUserRepository,
        InMemoryWorkflowRepository,
    ],
) -> None:
    client, _, workflow_repository = ownership_client
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: OrchestratorService(
            CountingIncompleteIntakeClient(),
            workflow_repository,
        )
    )

    no_token = client.post(
        "/orchestrator/process",
        json={"request_id": "REQ520", "text": "I want to make a claim."},
    )
    _, token = register_and_login(client, "customer@example.com")
    spoofed = client.post(
        "/orchestrator/process",
        headers=bearer(token),
        json={
            "request_id": "REQ521",
            "text": "I want to make a claim.",
            "user_id": "someone-else",
        },
    )

    assert no_token.status_code == 401
    assert spoofed.status_code == 422


def test_non_customer_role_cannot_create_customer_workflow(
    ownership_client: tuple[
        TestClient,
        InMemoryUserRepository,
        InMemoryWorkflowRepository,
    ],
) -> None:
    client, user_repository, workflow_repository = ownership_client
    officer = asyncio.run(
        user_repository.create_user(
            email="officer@example.com",
            password_hash=hash_password("securepass123"),
            role=UserRole.CLAIMS_OFFICER,
        )
    )
    token = create_access_token(
        officer.user_id,
        officer.role,
        OWNERSHIP_SETTINGS,
    )
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = (
        lambda: OrchestratorService(
            CountingIncompleteIntakeClient(),
            workflow_repository,
        )
    )

    response = client.post(
        "/orchestrator/process",
        headers=bearer(token),
        json={"request_id": "REQ530", "text": "I want to make a claim."},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "You are not authorized to perform this action"
    }
