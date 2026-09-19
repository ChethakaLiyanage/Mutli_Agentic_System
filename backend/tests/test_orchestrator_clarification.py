"""Service tests for persisted multi-turn clarification workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

import pytest

from backend.app.orchestrator.agent_clients import LocalClaimIntakeClient
from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.orchestrator.adapters import merge_claim_intake_results
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
    IncidentInformation,
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


OWNER_ID = "USR-OWNER"
OWNER_ROLE = "customer"


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
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(
                request_id="REQ002",
                text="A bus hit it yesterday in Kandy.",
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
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
        assert saved.authenticated_user_id == OWNER_ID
        assert saved.authenticated_user_role == OWNER_ROLE

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
            OrchestratorRequest(request_id="REQ001", text="I want to claim damage."),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)

        first_reply = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ002", text="It happened yesterday."),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(first_reply, ClarificationResponse)
        assert first_reply.workflow_id == initial.workflow_id
        assert first_reply.missing_fields == ["incident_type", "location"]

        second_reply = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ003", text="A bus hit it in Kandy."),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
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
                authenticated_user_id=OWNER_ID,
                authenticated_user_role=OWNER_ROLE,
            )

        completed = await service.process_request(
            OrchestratorRequest(request_id="REQ001", text="A complete claim message"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        with pytest.raises(WorkflowNotResumableError):
            await service.resume_clarification(
                completed.workflow_id,
                ClarificationRequest(request_id="REQ002", text="More detail"),
                authenticated_user_id=OWNER_ID,
                authenticated_user_role=OWNER_ROLE,
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
            OrchestratorRequest(request_id="REQ001", text="I want to claim."),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )

        for attempt in range(1, MAX_CLARIFICATION_ATTEMPTS + 1):
            result = await service.resume_clarification(
                result.workflow_id,
                ClarificationRequest(
                    request_id=f"REQ00{attempt + 1}",
                    text=f"Additional information {attempt}",
                ),
                authenticated_user_id=OWNER_ID,
                authenticated_user_role=OWNER_ROLE,
            )

        assert isinstance(result, OrchestratorResponse)
        assert result.status is WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED
        assert result.errors[0].code == "CLARIFICATION_LIMIT_REACHED"
        assert len(client.requests) == MAX_CLARIFICATION_ATTEMPTS + 1
        with pytest.raises(WorkflowNotResumableError):
            await service.resume_clarification(
                result.workflow_id,
                ClarificationRequest(request_id="REQ999", text="Another reply"),
                authenticated_user_id=OWNER_ID,
                authenticated_user_role=OWNER_ROLE,
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
            OrchestratorRequest(request_id="REQ001", text="I want to claim."),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        result = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ002", text="More information"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
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
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(
                request_id="REAL002",
                text="A bus hit my car yesterday near Kandy.",
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.status is WorkflowStatus.INTAKE_COMPLETE
        assert resumed.workflow_type is WorkflowType.CLAIM_SUBMISSION
        assert resumed.missing_fields == []

    asyncio.run(scenario())


def test_merge_preserves_previous_incident_type_and_recalculates_missing() -> None:
    previous = IntakeResponse(
        request_id="MERGE001",
        status="success",
        data=IntakeData(
            intent=IntentResult(label="claim_submission", confidence=0.82),
            incident=IncidentInformation(type="vehicle_collision"),
            missing_fields=["incident_date", "location"],
            requires_clarification=True,
        ),
    )
    clarification = IntakeResponse(
        request_id="MERGE002",
        status="success",
        data=IntakeData(
            intent=IntentResult(label="claim_submission", confidence=0.76),
            incident=IncidentInformation(
                date_text="yesterday",
                normalized_date="2026-09-17",
                location="Kandy",
            ),
            missing_fields=["incident_type"],
            requires_clarification=True,
        ),
    )

    merged = merge_claim_intake_results(previous, clarification)

    assert merged.data.incident.type == "vehicle_collision"
    assert merged.data.incident.normalized_date == "2026-09-17"
    assert merged.data.incident.location == "Kandy"
    assert merged.data.missing_fields == []
    assert merged.data.requires_clarification is False


def test_real_claim_clarification_merges_date_and_location_and_continues() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        agent = ClaimIntakeAgent(
            reference_date_provider=lambda: date(2026, 9, 18)
        )
        service = OrchestratorService(LocalClaimIntakeClient(agent), repository)
        initial = await service.process_request(
            OrchestratorRequest(request_id="LOC001", text="my car crashed"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)
        assert initial.missing_fields == ["incident_date", "location"]

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(
                request_id="LOC002",
                text="yesterday at Kandy",
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )

        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.status is WorkflowStatus.INTAKE_COMPLETE
        assert resumed.requires_clarification is False
        assert resumed.missing_fields == []
        assert resumed.intake_result is not None
        incident = resumed.intake_result.data.incident
        assert incident.type == "vehicle_collision"
        assert incident.date_text == "yesterday"
        assert incident.normalized_date == "2026-09-17"
        assert incident.location == "Kandy"

    asyncio.run(scenario())


def test_location_only_clarification_preserves_existing_claim_facts() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        agent = ClaimIntakeAgent(
            reference_date_provider=lambda: date(2026, 9, 18)
        )
        service = OrchestratorService(LocalClaimIntakeClient(agent), repository)
        initial = await service.process_request(
            OrchestratorRequest(
                request_id="LOC003",
                text="my car crashed yesterday",
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)
        assert initial.missing_fields == ["location"]

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="LOC004", text="Kandy"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )

        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.missing_fields == []
        assert resumed.intake_result is not None
        incident = resumed.intake_result.data.incident
        assert incident.type == "vehicle_collision"
        assert incident.date_text == "yesterday"
        assert incident.location == "Kandy"

    asyncio.run(scenario())


def test_misspelled_gazetteer_location_completes_existing_claim_context() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        agent = ClaimIntakeAgent(
            reference_date_provider=lambda: date(2026, 9, 18)
        )
        service = OrchestratorService(LocalClaimIntakeClient(agent), repository)
        initial = await service.process_request(
            OrchestratorRequest(
                request_id="LOC-NUG-1",
                text="my car crashed yesterday",
            ),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)
        assert initial.missing_fields == ["location"]
        assert initial.message is not None
        assert "yesterday" in initial.message
        assert initial.questions == [initial.message]

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="LOC-NUG-2", text="nuggeoda"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )

        assert isinstance(resumed, OrchestratorResponse)
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.requires_clarification is False
        assert resumed.intake_result is not None
        incident = resumed.intake_result.data.incident
        assert incident.type == "vehicle_collision"
        assert incident.date_text == "yesterday"
        assert incident.location == "Nugegoda"

    asyncio.run(scenario())


def test_location_only_reply_leaves_only_the_still_missing_date() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        service = OrchestratorService(LocalClaimIntakeClient(), repository)
        initial = await service.process_request(
            OrchestratorRequest(request_id="LOC005", text="my car crashed"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)

        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="LOC006", text="Kandy"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )

        assert isinstance(resumed, ClarificationResponse)
        assert resumed.missing_fields == ["incident_date"]
        assert resumed.questions == ["When did the incident happen?"]
        assert resumed.intake_result.data.incident.type == "vehicle_collision"
        assert resumed.intake_result.data.incident.location == "Kandy"

    asyncio.run(scenario())
