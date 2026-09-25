from __future__ import annotations

import asyncio
from datetime import date

import pytest

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.domain import (
    ClaimContext,
    HumanDecision,
    HumanDecisionContext,
    IncidentType,
)
from backend.app.schemas.orchestrator import OrchestratorRequest


def _state(status: WorkflowStatus) -> WorkflowState:
    workflow_id = f"WF-STATUS-{status.value.upper()}"
    return WorkflowState(
        workflow_id=workflow_id,
        request_id="REQ-ORIGINAL",
        last_request_id="REQ-ORIGINAL",
        raw_text="A theft claim",
        original_text="A theft claim",
        accumulated_text="A theft claim",
        authenticated_user_id="USR-1",
        authenticated_user_role="customer",
        workflow_type=WorkflowType.CLAIM_SUBMISSION,
        current_status=status,
        claim_context=ClaimContext(
            claim_id="CLM-THEFT-1",
            customer_id="USR-1",
            incident_type=IncidentType.THEFT_OR_BREAK_IN,
            incident_date=date(2026, 9, 1),
            claim_status=status.value,
        ),
        guidance_result={
            "status": "success",
            "response_type": "claim_document_requirements",
            "agent": "guidance_agent",
            "data": {
                "message": "Please upload the required documents.",
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
                "grounded": True,
                "reviewer_summary": None,
            },
            "warnings": [],
        },
    )


@pytest.mark.parametrize(
    ("status", "expected_text", "decision"),
    [
        (WorkflowStatus.AWAITING_ASSIGNMENT, "waiting to be assigned", None),
        (WorkflowStatus.AWAITING_HUMAN_REVIEW, "waiting for a claims officer", None),
        (WorkflowStatus.UNDER_HUMAN_REVIEW, "is reviewing", None),
        (
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            "requested additional information",
            HumanDecision.REQUEST_MORE_INFORMATION,
        ),
        (WorkflowStatus.APPROVED, "approved", HumanDecision.APPROVE),
        (WorkflowStatus.REJECTED, "rejected", HumanDecision.REJECT),
    ],
)
def test_status_read_replaces_stale_document_guidance(
    status: WorkflowStatus,
    expected_text: str,
    decision: HumanDecision | None,
) -> None:
    repo = InMemoryWorkflowRepository()
    state = _state(status)
    if decision is not None:
        state.human_review_result = HumanDecisionContext(
            decision_id="DEC-1",
            workflow_id=state.workflow_id,
            claim_id=state.claim_context.claim_id,
            decision=decision,
            reviewer_id="OFFICER-1",
            reason="Please review the recorded officer outcome.",
        ).model_dump(mode="json")
    asyncio.run(repo.save(state))
    service = OrchestratorService(workflow_repository=repo)

    response = asyncio.run(
        service.get_customer_workflow_result(
            state.workflow_id,
            authenticated_user_id="USR-1",
        )
    )

    assert response.status is status
    assert expected_text in response.message.lower()
    assert "upload the required documents" not in response.message.lower()
    assert response.fraud_result is None
    saved = asyncio.run(repo.get(state.workflow_id))
    assert saved.guidance_result["_workflow_status"] == status.value


def test_typed_status_question_reads_active_workflow_without_new_claim() -> None:
    repo = InMemoryWorkflowRepository()
    state = _state(WorkflowStatus.AWAITING_ASSIGNMENT)
    asyncio.run(repo.save(state))
    service = OrchestratorService(workflow_repository=repo)

    response = asyncio.run(
        service.process_request(
            OrchestratorRequest(
                request_id="REQ-STATUS",
                text="What is my claim status?",
                context_workflow_id=state.workflow_id,
            ),
            authenticated_user_id="USR-1",
            authenticated_user_role="customer",
        )
    )

    assert response.workflow_id == state.workflow_id
    assert response.status is WorkflowStatus.AWAITING_ASSIGNMENT
    assert "waiting to be assigned" in response.message.lower()
    assert "upload the required documents" not in response.message.lower()
