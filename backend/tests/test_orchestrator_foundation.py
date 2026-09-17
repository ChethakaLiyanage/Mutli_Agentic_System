"""Tests for Orchestrator contracts, state, transitions, and Agent 1 boundary."""

from __future__ import annotations

import asyncio
from datetime import timezone

import pytest
from pydantic import ValidationError

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.agent_clients import (
    ClaimIntakeClient,
    LocalClaimIntakeClient,
)
from backend.app.orchestrator.constants import (
    AuditEventStatus,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.orchestrator.service import (
    InvalidWorkflowTransition,
    OrchestratorService,
)
from backend.app.schemas.intake import (
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.orchestrator import (
    ClarificationResponse,
    OrchestratorRequest,
)


def make_intake_response(request_id: str = "REQ001") -> IntakeResponse:
    return IntakeResponse(
        request_id=request_id,
        status="success",
        data=IntakeData(
            intent=IntentResult(label="claim_submission", confidence=0.9),
        ),
    )


def test_valid_orchestrator_request_is_normalized() -> None:
    request = OrchestratorRequest(
        request_id="  REQ001  ",
        text="  My car was damaged and I want to claim.  ",
    )

    assert request.request_id == "REQ001"
    assert request.text == "My car was damaged and I want to claim."


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "", "text": "Valid text"},
        {"request_id": "   ", "text": "Valid text"},
        {"request_id": "REQ001", "text": ""},
        {"request_id": "REQ001", "text": "x"},
    ],
)
def test_invalid_empty_or_short_request_is_rejected(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        OrchestratorRequest(**payload)


def test_request_does_not_trust_user_id_from_body() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        OrchestratorRequest(
            request_id="REQ001",
            text="A valid request",
            user_id="untrusted-user",  # type: ignore[call-arg]
        )


def test_creates_initial_serializable_workflow_state() -> None:
    service = OrchestratorService()
    request = OrchestratorRequest(
        request_id="REQ001",
        text="My car was damaged and I want to claim.",
    )

    state = service.create_initial_state(request)
    restored = WorkflowState.model_validate_json(state.model_dump_json())

    assert state.request_id == "REQ001"
    assert state.raw_text == request.text
    assert state.current_status is WorkflowStatus.RECEIVED
    assert state.workflow_type is WorkflowType.UNKNOWN
    assert state.authenticated_user_id is None
    assert state.authenticated_user_role is None
    assert state.intake_result is None
    assert state.retrieval_result is None
    assert service.to_response(state).fraud_result is None
    assert service.to_response(state).guidance_result is None
    assert restored == state


def test_authenticated_context_is_supplied_outside_request_body() -> None:
    state = OrchestratorService().create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request"),
        authenticated_user_id="trusted-user-id",
        authenticated_user_role="claimant",
    )

    assert state.authenticated_user_id == "trusted-user-id"
    assert state.authenticated_user_role == "claimant"


def test_valid_workflow_status_transition_adds_audit_event() -> None:
    service = OrchestratorService()
    state = service.create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )

    service.update_status(state, WorkflowStatus.INTAKE_PROCESSING)

    assert state.current_status is WorkflowStatus.INTAKE_PROCESSING
    assert len(state.audit_trail) == 2
    assert state.audit_trail[-1].status is AuditEventStatus.SUCCESS
    assert "intake_processing" in state.audit_trail[-1].message


def test_invalid_workflow_status_transition_is_rejected() -> None:
    service = OrchestratorService()
    state = service.create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )

    with pytest.raises(InvalidWorkflowTransition, match="received.*completed"):
        service.update_status(state, WorkflowStatus.COMPLETED)

    assert state.current_status is WorkflowStatus.RECEIVED


def test_audit_event_contains_timezone_aware_timestamp() -> None:
    state = OrchestratorService().create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )

    event = state.audit_trail[0]

    assert event.step == "orchestrator"
    assert event.status is AuditEventStatus.SUCCESS
    assert event.timestamp.tzinfo is not None
    assert event.timestamp.utcoffset() == timezone.utc.utcoffset(event.timestamp)


def test_clarification_state_and_response_representation() -> None:
    service = OrchestratorService()
    state = service.create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="I want to make a claim")
    )
    service.update_status(state, WorkflowStatus.INTAKE_PROCESSING)

    service.mark_clarification_required(
        state,
        ["incident_type", "location", "location"],
    )
    snapshot = service.to_response(state)
    clarification = ClarificationResponse(
        request_id=state.request_id,
        missing_fields=state.missing_fields,
    )

    assert state.current_status is WorkflowStatus.AWAITING_CLARIFICATION
    assert state.workflow_type is WorkflowType.CLARIFICATION
    assert state.missing_fields == ["incident_type", "location"]
    assert state.requires_clarification is True
    assert state.audit_trail[-1].status is AuditEventStatus.AWAITING_INPUT
    assert snapshot.requires_clarification is True
    assert clarification.status is WorkflowStatus.AWAITING_CLARIFICATION


def test_failure_state_and_response_representation() -> None:
    service = OrchestratorService()
    state = service.create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )

    service.mark_failed(
        state,
        code="INTAKE_UNAVAILABLE",
        message="Claim Intake Agent was unavailable",
        step="claim_intake",
    )
    response = service.to_response(state)

    assert state.current_status is WorkflowStatus.FAILED
    assert state.errors[0].code == "INTAKE_UNAVAILABLE"
    assert state.errors[0].step == "claim_intake"
    assert state.audit_trail[-1].status is AuditEventStatus.FAILED
    assert response.status is WorkflowStatus.FAILED
    assert response.errors == state.errors


def test_state_stores_agent_one_response_without_modification() -> None:
    state = OrchestratorService().create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )
    intake_response = make_intake_response()

    state.intake_result = intake_response
    response = OrchestratorService().to_response(state)

    assert response.intake_result == intake_response
    assert response.intake_result.data.intent.label == "claim_submission"
    assert response.intake_result.data.intent.confidence == 0.9


def test_local_claim_intake_client_implements_async_boundary() -> None:
    expected_response = make_intake_response()

    class StubClaimIntakeAgent:
        def analyze(self, request: IntakeRequest) -> IntakeResponse:
            assert request.request_id == "REQ001"
            return expected_response

    client = LocalClaimIntakeClient(StubClaimIntakeAgent())
    result = asyncio.run(
        client.analyze(IntakeRequest(request_id="REQ001", text="A valid request"))
    )

    assert isinstance(client, ClaimIntakeClient)
    assert result is expected_response


def test_routing_methods_remain_placeholders() -> None:
    service = OrchestratorService()
    state = service.create_initial_state(
        OrchestratorRequest(request_id="REQ001", text="A valid request")
    )

    assert service.determine_workflow_type(state) is WorkflowType.UNKNOWN
    with pytest.raises(NotImplementedError, match="routing is not implemented"):
        asyncio.run(service.route_next_step(state))
