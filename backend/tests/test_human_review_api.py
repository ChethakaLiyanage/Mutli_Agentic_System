from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api import reviewer as reviewer_api
from backend.app.main import app
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.review.repository import InMemoryHumanReviewRepository
from backend.app.review.service import HumanReviewService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.dependencies import get_current_user
from backend.app.security.roles import UserRole
from backend.tests.test_human_review_service import review_state


def user(role: UserRole) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=f"USER-{role.value}", email=f"{role.value}@example.com",
        role=role, created_at=datetime.now(timezone.utc),
    )


def build_service() -> HumanReviewService:
    workflows = InMemoryWorkflowRepository()
    asyncio.run(workflows.save(review_state("API", risk="high")))
    asyncio.run(workflows.save(review_state("API-SECOND", risk="low")))
    return HumanReviewService(InMemoryHumanReviewRepository(workflows))


@pytest.fixture
def client():
    service = build_service()
    app.dependency_overrides[reviewer_api.get_review_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", [
    "/review/queue",
    "/review/workflows/API",
    "/review/workflows/API/decision",
])
def test_customer_is_forbidden_from_review_endpoints(client, path) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(UserRole.CUSTOMER)
    if path.endswith("decision"):
        response = client.post(path, json={"decision": "approve", "reason": "Reviewed."})
    else:
        response = client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", [
    "/review/queue", "/review/workflows/API", "/review/workflows/API/decision",
])
def test_unauthenticated_reviewer_endpoints_return_401(client, path) -> None:
    if path.endswith("decision"):
        response = client.post(path, json={"decision": "approve", "reason": "Reviewed."})
    else:
        response = client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("role", [UserRole.CLAIMS_OFFICER, UserRole.ADMIN])
def test_officer_and_admin_can_list_queue(client, role) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(role)
    response = client.get("/review/queue?limit=1&offset=0")
    assert response.status_code == 200
    assert response.json()["returned"] == 1
    assert response.json()["items"][0]["workflow_id"] == "API"


def test_reviewer_can_view_detail_and_submit_decision(client) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(UserRole.CLAIMS_OFFICER)
    detail = client.get("/review/workflows/API")
    assert detail.status_code == 200
    assert detail.json()["fraud_assessment"]["risk_level"] == "high"
    decision = client.post("/review/workflows/API/decision", json={
        "decision": "approve", "reason": "Documents and circumstances verified."
    })
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert decision.json()["decision"]["reviewer_id"] == "USER-claims_officer"


def test_duplicate_decision_returns_409(client) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(UserRole.CLAIMS_OFFICER)
    payload = {"decision": "approve", "reason": "Evidence verified."}
    assert client.post("/review/workflows/API/decision", json=payload).status_code == 200
    response = client.post("/review/workflows/API/decision", json={
        "decision": "reject", "reason": "Contradictory attempt."
    })
    assert response.status_code == 409


def test_invalid_decision_and_short_reason_return_422(client) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(UserRole.ADMIN)
    assert client.post("/review/workflows/API/decision", json={
        "decision": "auto_reject", "reason": "Invalid decision."
    }).status_code == 422
    assert client.post("/review/workflows/API/decision", json={
        "decision": "reject", "reason": "x"
    }).status_code == 422


def test_not_found_returns_404(client) -> None:
    app.dependency_overrides[get_current_user] = lambda: user(UserRole.ADMIN)
    assert client.get("/review/workflows/UNKNOWN").status_code == 404
