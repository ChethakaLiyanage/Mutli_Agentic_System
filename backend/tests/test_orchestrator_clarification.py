"""Service tests for persisted multi-turn clarification workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from backend.app.orchestrator.agent_clients import LocalClaimIntakeClient
from backend.app.orchestrator.constants import (
    MAX_CLARIFICATION_ATTEMPTS,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import (
    OrchestratorService,
    WorkflowNotFoundError,
    WorkflowNotResumableError,
)
from backend.app.schemas.intake import (
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.orchestrator import (
    ClarificationRequest,
    ClarificationResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)


@dataclass
class IntakeOutcome:
    missing_fields: list[str]
    requires_clarification: bool
    label: str | None = "claim_submission"


class SequentialClaimIntakeClient:
    def __init__(self, outcomes: list[IntakeOutcome | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[IntakeRequest] = []

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return IntakeResponse(
            request_id=request.request_id,
            status="success",
            data=IntakeData(
                intent=IntentResult(label=outcome.label, confidence=0.8),
                missing_fields=outcome.missing_fields,
                requires_clarification=outcome.requires_clarification,
            ),
        )


def incomplete(*fields: str) -> IntakeOutcome:
    return IntakeOutcome(list(fields), True)


def complete() -> IntakeOutcome:
    return IntakeOutcome([], False)


def test_one_clarification_completes_the_same_workflow() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        client = SequentialClaimIntakeClient(
            [incomplete("incident_type", "incident_date", "location"), complete()]
        )
        service = OrchestratorService(client, repository)

        initial = await service.process_request(
            OrchestratorRequest(
                request_id="REQ001",
                text="My car was damaged and I want to claim.",
            ),
            authenticated_user_id="trusted-user",
            authenticated_user_role="claimant",
        )
        assert isinstance(initial, ClarificationResponse)

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(
                request_id="REQ002",
                text="A bus hit it yesterday in Kandy.",
            ),
            authenticated_user_id="different-caller-not-yet-enforced",
            authenticated_user_role="reviewer",
        )

        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.request_id == "REQ002"
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.status is WorkflowStatus.INTAKE_COMPLETE
        assert resumed.workflow_type is WorkflowType.CLAIM_SUBMISSION
        assert resumed.requires_clarification is False
        assert resumed.missing_fields == []
        assert client.requests[1].text == (
            "My car was damaged and I want to claim. "
            "A bus hit it yesterday in Kandy."
        )

        saved = await repository.get(initial.workflow_id)
        assert saved is not None
        assert saved.original_text == "My car was damaged and I want to claim."
        assert saved.accumulated_text == client.requests[1].text
        assert saved.clarification_count == 1
        assert saved.last_request_id == "REQ002"
        assert saved.audit_trail[0] == initial.audit_trail[0]
        assert saved.authenticated_user_id == "trusted-user"
        assert saved.authenticated_user_role == "claimant"

    asyncio.run(scenario())


def test_multiple_clarifications_preserve_remaining_fields_and_audit() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        client = SequentialClaimIntakeClient(
            [
                incomplete("incident_type", "incident_date", "location"),
                incomplete("incident_type", "location"),
                complete(),
            ]
        )
        service = OrchestratorService(client, repository)
        initial = await service.process_request(
            OrchestratorRequest(request_id="REQ001", text="I want to claim damage.")
        )
        assert isinstance(initial, ClarificationResponse)

        first_reply = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ002", text="It happened yesterday."),
        )
        assert isinstance(first_reply, ClarificationResponse)
        assert first_reply.workflow_id == initial.workflow_id
        assert first_reply.missing_fields == ["incident_type", "location"]

        second_reply = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ003", text="A bus hit it in Kandy."),
        )
        assert isinstance(second_reply, OrchestratorResponse)
        assert second_reply.status is WorkflowStatus.INTAKE_COMPLETE
        saved = await repository.get(initial.workflow_id)
        assert saved is not None
        assert saved.clarification_count == 2
        messages = [event.message for event in saved.audit_trail]
        assert "Clarification received" in messages
        assert "Clarification analysis completed" in messages
        assert "Intake completed after clarification" in messages

    asyncio.run(scenario())


def test_unknown_and_non_resumable_workflows_are_rejected() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        service = OrchestratorService(
            SequentialClaimIntakeClient([complete()]),
            repository,
        )
        with pytest.raises(WorkflowNotFoundError):
            await service.resume_clarification(
                "WF-DOES-NOT-EXIST",
                ClarificationRequest(request_id="REQ002", text="More detail"),
            )

        completed = await service.process_request(
            OrchestratorRequest(request_id="REQ001", text="A complete claim message")
        )
        with pytest.raises(WorkflowNotResumableError):
            await service.resume_clarification(
                completed.workflow_id,
                ClarificationRequest(request_id="REQ002", text="More detail"),
            )

    asyncio.run(scenario())


def test_clarification_limit_requires_manual_assistance_and_stops_calls() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        always_missing = incomplete("incident_type", "location")
        client = SequentialClaimIntakeClient(
            [always_missing] * (MAX_CLARIFICATION_ATTEMPTS + 1)
        )
        service = OrchestratorService(client, repository)
        result = await service.process_request(
            OrchestratorRequest(request_id="REQ001", text="I want to claim.")
        )

        for attempt in range(1, MAX_CLARIFICATION_ATTEMPTS + 1):
            result = await service.resume_clarification(
                result.workflow_id,
                ClarificationRequest(
                    request_id=f"REQ00{attempt + 1}",
                    text=f"Additional information {attempt}",
                ),
            )

        assert isinstance(result, OrchestratorResponse)
        assert result.status is WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED
        assert result.errors[0].code == "CLARIFICATION_LIMIT_REACHED"
        assert len(client.requests) == MAX_CLARIFICATION_ATTEMPTS + 1
        with pytest.raises(WorkflowNotResumableError):
            await service.resume_clarification(
                result.workflow_id,
                ClarificationRequest(request_id="REQ999", text="Another reply"),
            )
        assert len(client.requests) == MAX_CLARIFICATION_ATTEMPTS + 1

    asyncio.run(scenario())


def test_agent_failure_during_clarification_is_persisted_safely() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        secret = "internal model path must not leak"
        client = SequentialClaimIntakeClient(
            [incomplete("incident_type"), RuntimeError(secret)]
        )
        service = OrchestratorService(client, repository)
        initial = await service.process_request(
            OrchestratorRequest(request_id="REQ001", text="I want to claim.")
        )
        result = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ002", text="More information"),
        )

        assert isinstance(result, OrchestratorResponse)
        assert result.status is WorkflowStatus.FAILED
        assert result.errors[0].code == "CLARIFICATION_ANALYSIS_FAILED"
        assert secret not in result.model_dump_json()
        saved = await repository.get(initial.workflow_id)
        assert saved is not None
        assert saved.current_status is WorkflowStatus.FAILED
        assert saved.audit_trail[-1].status.value == "failed"

    asyncio.run(scenario())


def test_real_agent_one_completes_after_clarification() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        service = OrchestratorService(LocalClaimIntakeClient(), repository)
        initial = await service.process_request(
            OrchestratorRequest(
                request_id="REAL001",
                text="My car was damaged and I want to claim.",
            )
        )
        assert isinstance(initial, ClarificationResponse)

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(
                request_id="REAL002",
                text="A bus hit my car yesterday near Kandy.",
            ),
        )
        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.status is WorkflowStatus.INTAKE_COMPLETE
        assert resumed.workflow_type is WorkflowType.CLAIM_SUBMISSION
        assert resumed.missing_fields == []

    asyncio.run(scenario())
