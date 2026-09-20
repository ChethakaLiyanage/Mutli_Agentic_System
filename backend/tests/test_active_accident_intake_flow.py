"""Regression test suite for active accident statements vs hypothetical queries,
contextual clarification generation without redundant date queries,
and multi-turn clarification claim advancement.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.api import orchestrator as orchestrator_api
from backend.app.graph.state import WorkflowState
from backend.app.guidance.fallbacks import build_deterministic_guidance_response
from backend.app.guidance.schemas import GuidanceRequest
from backend.app.main import app
from backend.app.nlp.date_extraction import extract_date
from backend.app.nlp.incident_extraction import extract_incident_type
from backend.app.nlp.intent_classifier import predict_intent
from backend.app.orchestrator.agent_clients import LocalGuidanceClient
from backend.app.orchestrator.claim_repository import (
    InMemoryClaimRepository,
    get_claim_repository,
)
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.api.claims import get_workflow_repository
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.schemas import (
    KnowledgeEvidence,
    PolicyRecord,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.intake import IntakeRequest
from backend.app.schemas.orchestrator import ClarificationRequest, OrchestratorRequest
from backend.app.security.dependencies import get_current_customer, get_current_user
from backend.app.security.roles import UserRole


CUSTOMER_USER = AuthenticatedUser(
    user_id="USR-CUST-ACTIVE-1",
    email="customer@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)


class DummyRetrievalClient:
    async def retrieve(self, request: RetrievalRequest, *args, **kwargs) -> RetrievalResponse:
        return RetrievalResponse(
            request_id=request.request_id,
            status="success",
            result=RetrievalResult(
                policy_data=PolicyRecord(
                    policy_id="POL-1",
                    policy_number="POL-001",
                    customer_id=CUSTOMER_USER.user_id,
                    status="active",
                    start_date="2025-01-01",
                    end_date="2027-01-01",
                    coverage_details={"collision": True},
                ),
                knowledge_evidence=[
                    KnowledgeEvidence(
                        evidence_id="EVD-1",
                        source_id="DOC-1",
                        source_title="Collision Document Requirements",
                        content="For collision claims, you must submit a repair estimate and damage photos.",
                    )
                ],
            ),
        )


def test_active_vs_hypothetical_accident_intent_distinction():
    """Verify distinction between active accident statements and hypothetical questions."""
    # Active statements -> claim_submission
    active_statements = [
        "im accidented just now what shoul i do?",
        "I just had an accident, what should I do?",
        "i just had accident",
        "had an accident just now",
        "i got accident few mins ago",
        "someone hit my car just now",
        "my car got hit today",
        "i crashed my car what should i do",
        "just got into accident",
        "accident happened few minutes ago",
    ]
    for statement in active_statements:
        intent, conf = predict_intent(statement)
        assert intent == "claim_submission", f"Failed for active statement: {statement} (got {intent})"
        assert conf >= 0.50

    # Hypothetical questions -> general_information
    hypothetical_questions = [
        "What should I do if I have an accident?",
        "What should I do in case of an accident?",
        "If I get into an accident what should I do?",
        "What is the procedure if my car gets damaged?",
        "What should a driver do if an accident occurs?",
    ]
    for question in hypothetical_questions:
        intent, conf = predict_intent(question)
        assert intent == "general_information", f"Failed for hypothetical question: {question} (got {intent})"
        assert conf >= 0.50


def test_agent_1_extraction_for_active_accident():
    """Verify Agent 1 extracts known temporal facts and does NOT invent collision type."""
    agent = ClaimIntakeAgent()
    request = IntakeRequest(request_id="REQ-TEST-1", text="im accidented just now what shoul i do?")
    response = agent.analyze(request)

    assert response.status == "success"
    data = response.data

    # Intent is claim_submission
    assert data.intent.label == "claim_submission"

    # incident_type is NOT invented (remains None because specific collision was not described)
    assert data.incident.type is None

    # date_text is extracted and normalized to today
    assert data.incident.date_text == "just now"
    assert data.incident.normalized_date == date.today().isoformat()

    # location is missing
    assert data.incident.location is None

    # missing_fields does NOT contain incident_date because it was provided as 'just now'
    assert "incident_date" not in data.missing_fields
    assert "incident_type" in data.missing_fields
    assert "location" in data.missing_fields
    assert data.requires_clarification is True


def test_clarification_message_does_not_ask_for_date_again():
    """Verify that clarification message asks what happened and where, without repeating date."""
    req = GuidanceRequest(
        request_id="REQ-GUIDE-1",
        audience="customer",
        task_type="clarification_question",
        intent="claim_submission",
        workflow_status="awaiting_clarification",
        missing_fields=["incident_type", "location"],
        known_fields={"date_text": "just now", "incident_date": date.today().isoformat()},
    )
    guidance_resp = build_deterministic_guidance_response(req)
    msg = guidance_resp.data.message

    assert "what happened" in msg.lower()
    assert "where it happened" in msg.lower()
    assert "damage occurred" in msg.lower()
    # Must NOT ask when it happened
    assert "when" not in msg.lower()


def test_end_to_end_clarification_and_advance_lifecycle():
    """Test multi-turn flow: active accident -> awaiting_clarification -> clarification answer -> awaiting_documents."""
    async def _test():
        workflows_repo = InMemoryWorkflowRepository()
        claims_repo = InMemoryClaimRepository(
            policies=[
                {"policy_id": "POL-1", "policy_number": "POL-001", "customer_id": CUSTOMER_USER.user_id, "status": "active"}
            ]
        )
        retrieval_client = DummyRetrievalClient()
        guidance_client = LocalGuidanceClient()

        service = OrchestratorService(
            workflow_repository=workflows_repo,
            claim_repository=claims_repo,
            retrieval_client=retrieval_client,
            guidance_client=guidance_client,
        )

        # Turn 1: Customer reports active accident
        turn1_req = OrchestratorRequest(
            request_id="REQ-T1",
            text="im accidented just now what shoul i do?",
        )
        resp1 = await service.process_request(
            turn1_req,
            authenticated_user_id=CUSTOMER_USER.user_id,
            authenticated_user_role=CUSTOMER_USER.role.value,
        )

        # Must be awaiting clarification
        assert resp1.status == WorkflowStatus.AWAITING_CLARIFICATION
        assert resp1.workflow_type == WorkflowType.CLARIFICATION
        assert resp1.intake_result.data.intent.label == "claim_submission"
        assert "incident_date" not in resp1.missing_fields
        assert "incident_type" in resp1.missing_fields
        assert "location" in resp1.missing_fields
        # Contextual message
        assert "what happened" in resp1.message.lower()
        assert "where it happened" in resp1.message.lower()
        assert "when" not in resp1.message.lower()

        # Turn 2: Customer provides clarification
        turn2_req = ClarificationRequest(
            request_id="REQ-T2",
            text="I collided with another car in Colombo and my front bumper and headlight are damaged.",
        )
        resp2 = await service.resume_clarification(
            workflow_id=resp1.workflow_id,
            request=turn2_req,
            authenticated_user_id=CUSTOMER_USER.user_id,
            authenticated_user_role=CUSTOMER_USER.role.value,
        )

        # Must advance to awaiting_documents with created claim
        assert resp2.status == WorkflowStatus.AWAITING_DOCUMENTS
        assert resp2.workflow_type == WorkflowType.CLAIM_SUBMISSION

        # Verify claim state was properly created and populated
        final_state = await workflows_repo.get(resp1.workflow_id)
        assert final_state is not None
        assert final_state.current_status == WorkflowStatus.AWAITING_DOCUMENTS
        assert final_state.claim_context is not None
        assert final_state.claim_context.claim_id is not None
        assert final_state.claim_context.claim_id.startswith("CLM-")
        assert final_state.claim_context.incident_type.value == "vehicle_collision"
        assert final_state.claim_context.incident_location == "Colombo"
        assert final_state.claim_context.incident_date == date.today()
        assert "front bumper" in final_state.claim_context.damage_areas
        assert "headlight" in final_state.claim_context.damage_areas
        assert final_state.retrieval_result is not None
        assert final_state.guidance_result is not None

    asyncio.run(_test())
