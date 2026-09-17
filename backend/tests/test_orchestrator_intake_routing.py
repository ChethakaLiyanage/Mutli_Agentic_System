"""Deterministic tests for Orchestrator Step 2 intake routing."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.orchestrator.constants import (
    AuditEventStatus,
    LOW_CONFIDENCE_CLARIFICATION_MESSAGE,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.intake import (
    DamageInformation,
    IncidentInformation,
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.orchestrator import (
    ClarificationResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)


class FakeClaimIntakeClient:
    def __init__(
        self,
        response: IntakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requests: list[IntakeRequest] = []

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def intake_response(
    *,
    label: str | None,
    missing_fields: list[str] | None = None,
    requires_clarification: bool = False,
    status: str = "success",
    incident_type: str | None = None,
    damage_areas: list[str] | None = None,
) -> IntakeResponse:
    return IntakeResponse(
        request_id="REQ001",
        status=status,
        data=IntakeData(
            intent=IntentResult(label=label, confidence=0.82),
            incident=IncidentInformation(type=incident_type),
            damage=DamageInformation(areas=damage_areas or []),
            missing_fields=missing_fields or [],
            requires_clarification=requires_clarification,
        ),
        errors=["Internal intake detail"] if status == "error" else [],
    )


def process(
    client: FakeClaimIntakeClient,
    text: str,
) -> OrchestratorResponse | ClarificationResponse:
    return asyncio.run(
        OrchestratorService(client).process_request(
            OrchestratorRequest(request_id="REQ001", text=text)
        )
    )


@pytest.mark.parametrize(
    ("label", "text", "expected_workflow"),
    [
        (
            "claim_submission",
            "A bus hit my car yesterday near Kandy and damaged the left door.",
            WorkflowType.CLAIM_SUBMISSION,
        ),
        (
            "coverage_question",
            "Does my policy cover flood damage?",
            WorkflowType.INFORMATION_REQUEST,
        ),
        (
            "required_documents_question",
            "What documents do I need for a motor insurance claim?",
            WorkflowType.INFORMATION_REQUEST,
        ),
        (
            "claim_status",
            "I want to check the status of my claim.",
            WorkflowType.CLAIM_STATUS,
        ),
    ],
)
def test_successful_intents_are_ready_for_future_routing(
    label: str,
    text: str,
    expected_workflow: WorkflowType,
) -> None:
    client = FakeClaimIntakeClient(
        intake_response(
            label=label,
            incident_type="flood_damage" if label == "coverage_question" else None,
        )
    )

    result = process(client, text)

    assert isinstance(result, OrchestratorResponse)
    assert result.status is WorkflowStatus.INTAKE_COMPLETE
    assert result.workflow_type is expected_workflow
    assert result.requires_clarification is False
    assert result.missing_fields == []
    assert result.intake_result is client.response
    assert len(client.requests) == 1
    assert client.requests[0].text == text
    assert result.retrieval_result is None
    assert result.fraud_result is None
    assert result.guidance_result is None


def test_incomplete_claim_returns_deterministic_field_questions() -> None:
    missing = ["incident_type", "incident_date", "location"]
    result = process(
        FakeClaimIntakeClient(
            intake_response(
                label="claim_submission",
                missing_fields=missing,
                requires_clarification=True,
            )
        ),
        "My car was damaged and I want to claim.",
    )

    assert isinstance(result, ClarificationResponse)
    assert result.status is WorkflowStatus.AWAITING_CLARIFICATION
    assert result.workflow_type is WorkflowType.CLARIFICATION
    assert result.requires_clarification is True
    assert result.missing_fields == missing
    assert result.questions == [
        "What happened to your vehicle?",
        "When did the incident happen?",
        "Where did the incident happen?",
    ]
    assert result.intake_result is not None
    assert result.audit_trail[-1].status is AuditEventStatus.AWAITING_INPUT
    assert "Clarification required" in result.audit_trail[-1].message


def test_claim_missing_fields_trigger_clarification_even_if_agent_flag_is_false() -> None:
    result = process(
        FakeClaimIntakeClient(
            intake_response(
                label="claim_submission",
                missing_fields=["location"],
                requires_clarification=False,
            )
        ),
        "I need to claim for an accident yesterday.",
    )

    assert isinstance(result, ClarificationResponse)
    assert result.questions == ["Where did the incident happen?"]


def test_low_confidence_clarification_uses_generic_message() -> None:
    result = process(
        FakeClaimIntakeClient(
            intake_response(
                label="general_information",
                requires_clarification=True,
            )
        ),
        "Can you help me with something?",
    )

    assert isinstance(result, ClarificationResponse)
    assert result.missing_fields == []
    assert result.reason == LOW_CONFIDENCE_CLARIFICATION_MESSAGE
    assert result.questions == [LOW_CONFIDENCE_CLARIFICATION_MESSAGE]


def test_missing_or_unknown_intent_stops_for_clarification() -> None:
    result = process(
        FakeClaimIntakeClient(intake_response(label=None)),
        "I am not sure what I need.",
    )

    assert isinstance(result, ClarificationResponse)
    assert result.workflow_type is WorkflowType.CLARIFICATION
    assert result.status is WorkflowStatus.AWAITING_CLARIFICATION
    assert result.questions == [LOW_CONFIDENCE_CLARIFICATION_MESSAGE]


def test_client_exception_returns_controlled_failure_without_leaking_details() -> None:
    secret_detail = "database password was accidentally logged"
    result = process(
        FakeClaimIntakeClient(error=RuntimeError(secret_detail)),
        "I need help with my claim.",
    )

    assert isinstance(result, OrchestratorResponse)
    assert result.status is WorkflowStatus.FAILED
    assert result.errors[0].code == "CLAIM_INTAKE_FAILED"
    assert result.errors[0].step == "claim_intake"
    assert secret_detail not in result.model_dump_json()
    assert result.audit_trail[-1].status is AuditEventStatus.FAILED
    assert result.audit_trail[-1].message == "Claim Intake failed"


def test_agent_error_response_is_preserved_but_public_error_is_controlled() -> None:
    agent_response = intake_response(label=None, status="error")
    result = process(
        FakeClaimIntakeClient(agent_response),
        "I need help with my claim.",
    )

    assert isinstance(result, OrchestratorResponse)
    assert result.status is WorkflowStatus.FAILED
    assert result.intake_result is agent_response
    assert result.errors[0].message == "Claim Intake Agent failed to analyze the request"
    assert "Internal intake detail" not in result.errors[0].message


def test_audit_trail_records_intake_and_workflow_decision_without_raw_text() -> None:
    raw_text = "My private claim wording should not enter the audit trail."
    result = process(
        FakeClaimIntakeClient(intake_response(label="general_information")),
        raw_text,
    )

    assert isinstance(result, OrchestratorResponse)
    messages = [event.message for event in result.audit_trail]
    assert messages == [
        "Workflow request received",
        "Claim intake started",
        "Claim intake completed",
        "Workflow type determined as information_request",
        "Request understood and ready for downstream routing",
    ]
    assert raw_text not in " ".join(messages)
