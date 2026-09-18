"""Tests for the Orchestrator's deterministic pure-greeting response."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.greetings import (
    GREETING_RESPONSE_MESSAGE,
    is_pure_greeting,
)
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.intake import (
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


class RecordingIntakeClient:
    def __init__(self, response: IntakeResponse | None = None) -> None:
        self.response = response
        self.requests: list[IntakeRequest] = []

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.requests.append(request)
        if self.response is None:
            raise AssertionError("No Agent 1 response was configured")
        return self.response


class ForbiddenDownstreamComponent:
    async def retrieve(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("Agent 2 must not run for a pure greeting")

    async def assess(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("Agent 3 must not run for a pure greeting")

    async def generate(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("Agent 4 must not run for a pure greeting")

    def save_for_workflow(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("A claim must not be created for a pure greeting")

    def save_canonical_assessment(
        self, *_args: object, **_kwargs: object
    ) -> None:
        raise AssertionError("Fraud persistence must not run for a pure greeting")


def intake_response(
    label: str,
    *,
    requires_clarification: bool = False,
    missing_fields: list[str] | None = None,
) -> IntakeResponse:
    return IntakeResponse(
        request_id="REQ-GREETING",
        status="success",
        data=IntakeData(
            intent=IntentResult(label=label, confidence=0.9),
            requires_clarification=requires_clarification,
            missing_fields=missing_fields or [],
        ),
    )


@pytest.mark.parametrize(
    "text",
    [
        "hi",
        "Hello",
        " hey! ",
        "hello there",
        "Good morning.",
        "GOOD AFTERNOON",
        "good evening!!!",
        "god mornin",
        "gud evening",
        "helo",
    ],
)
def test_recognizes_only_supported_pure_greeting_forms(text: str) -> None:
    assert is_pure_greeting(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hi I want to make a claim",
        "hey, does my policy cover flood damage?",
        "hello please check my claim status",
        "my car is damaged",
        "this happened yesterday",
        "helo i wana make a clam",
        "good mornin does my polcy covr flood",
    ],
)
def test_does_not_treat_insurance_or_ambiguous_requests_as_pure_greetings(
    text: str,
) -> None:
    assert is_pure_greeting(text) is False


def test_greeting_runs_agent_one_skips_downstream_and_persists_completed() -> None:
    repository = InMemoryWorkflowRepository()
    intake_client = RecordingIntakeClient(intake_response("greeting"))
    forbidden = ForbiddenDownstreamComponent()
    service = OrchestratorService(
        claim_intake_client=intake_client,
        workflow_repository=repository,
        retrieval_client=forbidden,  # type: ignore[arg-type]
        fraud_client=forbidden,  # type: ignore[arg-type]
        claim_repository=forbidden,  # type: ignore[arg-type]
        fraud_repository=forbidden,  # type: ignore[arg-type]
        guidance_client=forbidden,  # type: ignore[arg-type]
    )

    response = asyncio.run(
        service.process_request(
            OrchestratorRequest(request_id="REQ-GREETING", text="Hello!"),
            authenticated_user_id="USR-CUSTOMER",
            authenticated_user_role="customer",
        )
    )
    stored = asyncio.run(repository.get(response.workflow_id))

    assert isinstance(response, OrchestratorResponse)
    assert response.status is WorkflowStatus.COMPLETED
    assert response.workflow_type is WorkflowType.UNKNOWN
    assert response.message == GREETING_RESPONSE_MESSAGE
    assert response.requires_clarification is False
    assert response.intake_result is not None
    assert response.intake_result.data.intent.label == "greeting"
    assert response.retrieval_result is None
    assert response.fraud_result is None
    assert response.human_review_result is None
    assert response.guidance_result is None
    assert len(intake_client.requests) == 1
    assert intake_client.requests[0].text == "Hello!"
    assert stored is not None
    assert stored.current_status is WorkflowStatus.COMPLETED
    assert stored.authenticated_user_id == "USR-CUSTOMER"
    assert [event.step for event in stored.audit_trail] == [
        "orchestrator",
        "claim_intake",
        "claim_intake",
        "workflow_routing",
        "greeting",
    ]


@pytest.mark.parametrize(
    ("text", "label", "workflow_type"),
    [
        (
            "hi I want to make a claim",
            "claim_submission",
            WorkflowType.CLAIM_SUBMISSION,
        ),
        (
            "hey, does my policy cover flood damage?",
            "coverage_question",
            WorkflowType.INFORMATION_REQUEST,
        ),
    ],
)
def test_greeting_plus_insurance_request_uses_normal_agent_one_pipeline(
    text: str,
    label: str,
    workflow_type: WorkflowType,
) -> None:
    client = RecordingIntakeClient(intake_response(label))
    response = asyncio.run(
        OrchestratorService(claim_intake_client=client).process_request(
            OrchestratorRequest(request_id="REQ-GREETING", text=text)
        )
    )

    assert isinstance(response, OrchestratorResponse)
    assert response.status is WorkflowStatus.INTAKE_COMPLETE
    assert response.workflow_type is workflow_type
    assert len(client.requests) == 1
    assert client.requests[0].text == text


def test_ambiguous_insurance_request_keeps_existing_clarification_behavior() -> None:
    client = RecordingIntakeClient(
        intake_response(
            "claim_submission",
            requires_clarification=True,
            missing_fields=["incident_type", "incident_date", "location"],
        )
    )
    response = asyncio.run(
        OrchestratorService(claim_intake_client=client).process_request(
            OrchestratorRequest(
                request_id="REQ-GREETING",
                text="my car is damaged",
            )
        )
    )

    assert isinstance(response, ClarificationResponse)
    assert response.status is WorkflowStatus.AWAITING_CLARIFICATION
    assert response.missing_fields == [
        "incident_type",
        "incident_date",
        "location",
    ]
    assert len(client.requests) == 1


def test_real_agent_handles_transposed_short_greeting_without_downstream_calls() -> None:
    forbidden = ForbiddenDownstreamComponent()
    response = asyncio.run(
        OrchestratorService(
            retrieval_client=forbidden,  # type: ignore[arg-type]
            fraud_client=forbidden,  # type: ignore[arg-type]
            claim_repository=forbidden,  # type: ignore[arg-type]
            fraud_repository=forbidden,  # type: ignore[arg-type]
            guidance_client=forbidden,  # type: ignore[arg-type]
        ).process_request(
            OrchestratorRequest(request_id="REQ-IH", text="ih")
        )
    )

    assert isinstance(response, OrchestratorResponse)
    assert response.status is WorkflowStatus.COMPLETED
    assert response.intake_result is not None
    assert response.intake_result.data.intent.label == "greeting"
    assert response.missing_fields == []
    assert response.requires_clarification is False
    assert response.message == GREETING_RESPONSE_MESSAGE


def test_ambiguous_short_help_still_requires_clarification() -> None:
    response = asyncio.run(
        OrchestratorService().process_request(
            OrchestratorRequest(request_id="REQ-HELP", text="help")
        )
    )

    assert isinstance(response, ClarificationResponse)
    assert response.status is WorkflowStatus.AWAITING_CLARIFICATION
    assert response.missing_fields == []
    assert response.questions == [response.reason]
