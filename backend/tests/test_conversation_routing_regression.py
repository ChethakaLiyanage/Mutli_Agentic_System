"""Regression tests for customer claim vs. information conversation routing.

Verifies:
1. Intent classification distinguishes active claim incidents from informational questions.
2. Informational questions containing words like 'collision', 'accident', 'claim', 'report'
   are routed to Agent 2 knowledge retrieval and NOT to claim clarification.
3. Ingested knowledge document (sample_motor_claims_update_test.txt containing
   IRWA-ALPHA-2109 and 21 days reporting deadline) is retrieved for customer inquiries.
4. Active claim workflows in awaiting_clarification can be interrupted by informational
   questions without losing the pending claim state or polluting accumulated_text,
   and subsequent claim clarification completes the original claim.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.main import app
from backend.app.nlp.intent_classifier import predict_intent
from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.knowledge_retriever import get_shared_knowledge_retriever
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole


TEST_USER = AuthenticatedUser(
    user_id="USR-REGRESSION-001",
    email="test.customer@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_customer] = lambda: TEST_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_test_service(repo: InMemoryWorkflowRepository | None = None) -> OrchestratorService:
    repository = repo or InMemoryWorkflowRepository()
    return OrchestratorService(
        claim_intake_client=LocalClaimIntakeClient(),
        retrieval_client=LocalRetrievalClient(),
        workflow_repository=repository,
    )


# ---------------------------------------------------------------------------
# Section 1: Intent Classification Discrimination
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("query", "expected_label"),
    [
        ("I had an accident yesterday.", "claim_submission"),
        ("I collided with a lorry yesterday.", "claim_submission"),
        ("I want to make a collision claim.", "claim_submission"),
        ("I crashed my car into a barrier today.", "claim_submission"),
        ("A truck collided with my vehicle on the highway.", "claim_submission"),
    ],
)
def test_active_incident_classified_as_claim_submission(query: str, expected_label: str) -> None:
    label, confidence = predict_intent(query)
    assert label == expected_label, f"Expected {expected_label} for '{query}', got {label} ({confidence:.4f})"
    assert confidence >= 0.40


@pytest.mark.parametrize(
    ("query", "expected_labels"),
    [
        ("What is the special reference code for motor collision claims?", ["general_information", "policy_question"]),
        ("How many days do I have to report a motor collision?", ["policy_question", "general_information"]),
        ("What documents are required for a collision claim?", ["required_documents_question"]),
        ("What documents do I need for a collision claim?", ["required_documents_question"]),
        ("Does my policy cover collision damage?", ["coverage_question"]),
        ("What should I do if I have an accident?", ["policy_question", "general_information"]),
    ],
)
def test_informational_question_not_classified_as_claim_submission(
    query: str,
    expected_labels: list[str],
) -> None:
    label, confidence = predict_intent(query)
    assert label != "claim_submission", f"Query '{query}' was incorrectly classified as claim_submission!"
    assert label != "claim_status", f"Query '{query}' was incorrectly classified as claim_status!"
    assert label in expected_labels, f"Expected one of {expected_labels} for '{query}', got {label} ({confidence:.4f})"


# ---------------------------------------------------------------------------
# Section 2: Direct Agent 2 Retrieval on Ingested Test Document
# ---------------------------------------------------------------------------

def test_agent2_retrieves_special_reference_code() -> None:
    """Agent 2 must retrieve IRWA-ALPHA-2109 from the ingested test document."""
    retriever = get_shared_knowledge_retriever()
    evidence_items = retriever.retrieve("What is the special reference code for motor collision claims?")
    assert len(evidence_items) > 0, "No evidence retrieved for reference code query"
    combined_text = " ".join(e.content for e in evidence_items)
    assert "IRWA-ALPHA-2109" in combined_text, (
        "Agent 2 failed to retrieve IRWA-ALPHA-2109 chunk from knowledge document"
    )


def test_agent2_retrieves_reporting_deadline() -> None:
    """Agent 2 must retrieve 21 days from the ingested test document."""
    retriever = get_shared_knowledge_retriever()
    evidence_items = retriever.retrieve("How many days do I have to report a motor collision?")
    assert len(evidence_items) > 0, "No evidence retrieved for reporting deadline query"
    combined_text = " ".join(e.content for e in evidence_items)
    assert "21 days" in combined_text.lower(), (
        "Agent 2 failed to retrieve 21 days reporting deadline from knowledge document"
    )


# ---------------------------------------------------------------------------
# Section 3: Orchestrator End-to-End Routing for Informational Queries
# ---------------------------------------------------------------------------

def test_orchestrator_routes_reference_code_query_to_information(client: TestClient) -> None:
    """Special reference code query must route to information_request and retrieve IRWA-ALPHA-2109."""
    service = make_test_service()
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service

    response = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ-ROUTING-1",
            "text": "What is the special reference code for motor collision claims?",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["workflow_type"] == WorkflowType.INFORMATION_REQUEST.value
    assert data["status"] != WorkflowStatus.AWAITING_CLARIFICATION.value
    evidence_chunks = data.get("evidence_summary") or []
    assert len(evidence_chunks) > 0
    all_chunks = " ".join(c.get("content", "") for c in evidence_chunks)
    assert "IRWA-ALPHA-2109" in all_chunks


def test_orchestrator_routes_reporting_days_query_to_information(client: TestClient) -> None:
    """Reporting days query must route to information_request and retrieve 21 days."""
    service = make_test_service()
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service

    response = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ-ROUTING-2",
            "text": "How many days do I have to report a motor collision?",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["workflow_type"] == WorkflowType.INFORMATION_REQUEST.value
    assert data["status"] != WorkflowStatus.AWAITING_CLARIFICATION.value
    evidence_chunks = data.get("evidence_summary") or []
    assert len(evidence_chunks) > 0
    all_chunks = " ".join(c.get("content", "") for c in evidence_chunks)
    assert "21 days" in all_chunks.lower()


# ---------------------------------------------------------------------------
# Section 4: Claim Interruption and Continuity Workflow
# ---------------------------------------------------------------------------

def test_information_query_during_claim_clarification_preserves_claim_state(client: TestClient) -> None:
    """Customer asking an information question during claim clarification receives an

    answer via Agent 2 without corrupting the claim state or accumulated_text,
    and subsequent clarification completes the claim.
    """
    repo = InMemoryWorkflowRepository()
    service = make_test_service(repo=repo)
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service

    # Step 1: Start a claim that requires clarification (missing location and date)
    claim_start = client.post(
        "/orchestrator/process",
        json={
            "request_id": "REQ-CLAIM-START",
            "text": "I had a car accident and my front bumper is damaged.",
        },
    )
    assert claim_start.status_code == 200, claim_start.text
    claim_data = claim_start.json()
    assert claim_data["status"] == WorkflowStatus.AWAITING_CLARIFICATION.value
    workflow_id = claim_data["workflow_id"]

    saved_claim_before = asyncio.run(repo.get(workflow_id))
    assert saved_claim_before is not None
    assert saved_claim_before.current_status == WorkflowStatus.AWAITING_CLARIFICATION

    # Step 2: Customer interrupts with an informational question about collision claims
    interruption = client.post(
        f"/orchestrator/workflows/{workflow_id}/clarify",
        json={
            "request_id": "REQ-CLAIM-INTERRUPT",
            "text": "What is the special reference code for motor collision claims?",
        },
    )
    assert interruption.status_code == 200, interruption.text
    interruption_data = interruption.json()

    # Informational response returned, referencing the pending claim workflow
    assert interruption_data["workflow_type"] == WorkflowType.INFORMATION_REQUEST.value
    assert interruption_data.get("pending_claim_workflow_id") == workflow_id
    evidence_chunks = interruption_data.get("evidence_summary") or []
    assert len(evidence_chunks) > 0
    all_evidence = " ".join(c.get("content", "") for c in evidence_chunks)
    assert "IRWA-ALPHA-2109" in all_evidence

    # Verify claim state in repository is still awaiting_clarification and accumulated_text was NOT polluted
    saved_claim_during = asyncio.run(repo.get(workflow_id))
    assert saved_claim_during is not None
    assert saved_claim_during.current_status == WorkflowStatus.AWAITING_CLARIFICATION
    assert "special reference code" not in saved_claim_during.accumulated_text.lower()

    # Step 3: Customer provides missing incident details
    clarify_response = client.post(
        f"/orchestrator/workflows/{workflow_id}/clarify",
        json={
            "request_id": "REQ-CLAIM-FINISH",
            "text": "It was a collision yesterday in Kandy.",
        },
    )
    assert clarify_response.status_code == 200, clarify_response.text
    final_data = clarify_response.json()

    # The claim continues forward (intake completed)
    assert final_data["workflow_id"] == workflow_id
    assert final_data["status"] in (
        WorkflowStatus.INTAKE_COMPLETE.value,
        WorkflowStatus.COMPLETED.value,
    )
