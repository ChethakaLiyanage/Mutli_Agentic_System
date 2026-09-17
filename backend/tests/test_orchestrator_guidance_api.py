from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.main import app
from backend.app.orchestrator.agent_clients import LocalGuidanceClient
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.review.repository import InMemoryHumanReviewRepository
from backend.app.review.service import HumanReviewService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.review import HumanDecisionRequest
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole
from backend.tests.test_human_review_service import review_state


def _setup():
    workflows = InMemoryWorkflowRepository()
    state = review_state("CUSTOMER-RESULT", risk="high")
    asyncio.run(workflows.save(state))
    reviewer = AuthenticatedUser(
        user_id="OFFICER-RESULT", email="officer-result@example.com",
        role=UserRole.CLAIMS_OFFICER, created_at=datetime.now(timezone.utc),
    )
    asyncio.run(HumanReviewService(
        InMemoryHumanReviewRepository(workflows)
    ).submit_decision(
        state.workflow_id,
        HumanDecisionRequest(
            decision="reject", reason="The submitted incident is outside the recorded policy period."
        ),
        reviewer,
    ))
    return state, OrchestratorService(
        workflow_repository=workflows, guidance_client=LocalGuidanceClient()
    )


def test_customer_can_get_own_safe_post_decision_guidance() -> None:
    state, service = _setup()
    customer = AuthenticatedUser(
        user_id=state.authenticated_user_id, email="owner@example.com",
        role=UserRole.CUSTOMER, created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_customer] = lambda: customer
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/orchestrator/workflows/{state.workflow_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "rejected"
        assert "recorded reason" in body["message"].lower()
        assert body["fraud_result"] is None
        assert body["human_review_result"] is None
        assert "OFFICER-RESULT" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_customer_cannot_get_another_owners_result() -> None:
    state, service = _setup()
    other = AuthenticatedUser(
        user_id="OTHER-CUSTOMER", email="other@example.com",
        role=UserRole.CUSTOMER, created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_customer] = lambda: other
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/orchestrator/workflows/{state.workflow_id}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_unauthenticated_customer_result_is_401() -> None:
    state, service = _setup()
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/orchestrator/workflows/{state.workflow_id}")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_customer_cannot_call_reviewer_endpoints() -> None:
    customer = AuthenticatedUser(
        user_id="CUST-ROLE-TEST", email="cust@example.com",
        role=UserRole.CUSTOMER, created_at=datetime.now(timezone.utc),
    )
    from backend.app.security.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: customer
    try:
        with TestClient(app) as client:
            response = client.get("/review/queue")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_claims_officer_can_call_reviewer_endpoints() -> None:
    officer = AuthenticatedUser(
        user_id="OFFICER-ROLE-TEST", email="officer@example.com",
        role=UserRole.CLAIMS_OFFICER, created_at=datetime.now(timezone.utc),
    )
    from backend.app.security.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: officer
    try:
        with TestClient(app) as client:
            response = client.get("/review/queue")
        assert response.status_code == 200
        assert "items" in response.json()
    finally:
        app.dependency_overrides.clear()

