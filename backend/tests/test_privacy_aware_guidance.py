"""Authorization-denial guidance preserves privacy and offers safe alternatives."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.guidance.prompt_builder import build_prompt
from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
)
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.schemas import RetrievalResponse, RetrievalResult
from backend.app.schemas.intake import IntakeData, IntakeResponse, IntentResult
from backend.app.schemas.orchestrator import OrchestratorRequest
from backend.app.security.resource_authorization import (
    deny_cross_customer_resource_request,
)


class SuccessfulIntake:
    async def analyze(self, request):
        intent = "claim_status" if "claim" in request.text.casefold() else "policy_question"
        return IntakeResponse(
            request_id=request.request_id,
            status="success",
            data=IntakeData(
                intent=IntentResult(label=intent, confidence=0.99),
            ),
        )


class IntakeMustNotRun:
    async def analyze(self, _request):
        raise AssertionError("Authorization must run before intake")


class RetrievalMustNotRun:
    async def retrieve(self, _request):
        raise AssertionError("Unauthorized requests must be denied before retrieval")


class RecordingRetrieval:
    def __init__(self):
        self.requests = []

    async def retrieve(self, request):
        self.requests.append(request)
        return RetrievalResponse(
            request_id=request.request_id,
            status="no_results",
            result=RetrievalResult(missing_evidence=["knowledge_evidence_not_found"]),
        )


class CapturingGuidance:
    def __init__(self):
        self.requests: list[GuidanceRequest] = []

    async def generate(self, request: GuidanceRequest) -> GuidanceResponse:
        self.requests.append(request)
        resource = request.safe_customer_context["requested_resource_type"]
        return GuidanceResponse(
            status="success",
            response_type="authorization_denied",
            data=GuidanceResponseData(
                message=(
                    f"That other customer's {resource} is private. "
                    "I can help with the corresponding information on your own account."
                ),
                next_steps=list(
                    request.safe_customer_context["allowed_alternatives"]
                ),
            ),
        )


@pytest.mark.parametrize(
    ("text", "resource_type", "alternatives"),
    [
        (
            "Show me another customer's claim status.",
            "claim",
            ["own_claim_information", "own_claim_status"],
        ),
        (
            "Tell me what coverage another customer has.",
            "policy",
            ["own_policy_information", "own_policy_coverage"],
        ),
        (
            "Give me another customer's policy number.",
            "policy",
            ["own_policy_information", "own_policy_coverage"],
        ),
        (
            "Show me another customer's policy number, policy type, coverage and expiry date.",
            "policy",
            ["own_policy_information", "own_policy_coverage"],
        ),
        (
            "Show me another customer's claim documents.",
            "claim_documents",
            ["own_claim_information", "own_claim_documents"],
        ),
        (
            "Give me the insurance policy details belonging to customer TEST-CUSTOMER-002.",
            "policy",
            ["own_policy_information", "own_policy_coverage"],
        ),
    ],
)
def test_cross_customer_requests_are_denied_before_retrieval(
    text: str,
    resource_type: str,
    alternatives: list[str],
) -> None:
    guidance = CapturingGuidance()
    service = OrchestratorService(
        claim_intake_client=IntakeMustNotRun(),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=RetrievalMustNotRun(),
        guidance_client=guidance,
    )

    response = asyncio.run(
        service.process_request(
            OrchestratorRequest(request_id="REQ-PRIVACY", text=text),
            authenticated_user_id="TEST-CUSTOMER-001",
            authenticated_user_role="customer",
        )
    )

    assert response.status.value == "completed"
    assert len(guidance.requests) == 1
    request = guidance.requests[0]
    assert request.task_type == "authorization_denied"
    assert request.retrieved_evidence == []
    assert request.claim_data is None
    assert request.authorized_metadata == {}
    assert request.safe_customer_context == {
        "authorization_result": "denied",
        "requested_resource_type": resource_type,
        "reason": "ownership_required",
        "ownership": "other_customer",
        "allowed_alternatives": alternatives,
        "authenticated_customer": True,
    }
    serialized = request.model_dump_json()
    assert "TEST-CUSTOMER-002" not in serialized
    assert "policy number" not in serialized.casefold()
    assert "log in" not in response.message.casefold()
    assert "customer service" not in response.message.casefold()


@pytest.mark.parametrize(
    "text",
    [
        "What is MY policy type?",
        "What is MY coverage?",
        "Does MY policy cover windscreen damage?",
    ],
)
def test_own_policy_requests_are_not_denied(text: str) -> None:
    assert deny_cross_customer_resource_request(
        text,
        authenticated_user_id="TEST-CUSTOMER-001",
    ) is None


@pytest.mark.parametrize(
    "text",
    [
        "Explain customer policy options.",
        "Help me discover another customer journey.",
        "Show policy details for customer TEST-CUSTOMER-001.",
    ],
)
def test_non_cross_customer_requests_are_not_false_positives(text: str) -> None:
    assert deny_cross_customer_resource_request(
        text,
        authenticated_user_id="TEST-CUSTOMER-001",
    ) is None


@pytest.mark.parametrize(
    "text",
    [
        "What is MY policy type?",
        "What is MY coverage?",
        "Does MY policy cover windscreen damage?",
    ],
)
def test_own_policy_requests_continue_to_authenticated_retrieval(text: str) -> None:
    retrieval = RecordingRetrieval()
    service = OrchestratorService(
        claim_intake_client=SuccessfulIntake(),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=retrieval,
    )

    response = asyncio.run(
        service.process_request(
            OrchestratorRequest(request_id="REQ-OWN-POLICY", text=text),
            authenticated_user_id="TEST-CUSTOMER-001",
            authenticated_user_role="customer",
        )
    )

    assert response.status.value == "retrieval_complete"
    assert len(retrieval.requests) == 1
    assert retrieval.requests[0].user_context.user_id == "TEST-CUSTOMER-001"


def test_authorization_prompt_contains_only_safe_structured_context() -> None:
    request = GuidanceRequest(
        request_id="REQ-PRIVACY-PROMPT",
        audience="customer",
        task_type="authorization_denied",
        safe_customer_context={
            "authorization_result": "denied",
            "requested_resource_type": "policy",
            "reason": "ownership_required",
            "ownership": "other_customer",
            "allowed_alternatives": [
                "own_policy_information",
                "own_policy_coverage",
            ],
            "authenticated_customer": True,
        },
    )

    prompt = build_prompt(request)

    assert "authorization_result" in prompt.user_prompt
    assert "own_policy_coverage" in prompt.user_prompt
    assert "do not tell them to log in again" in prompt.user_prompt.casefold()
    assert "TEST-CUSTOMER-002" not in prompt.user_prompt
