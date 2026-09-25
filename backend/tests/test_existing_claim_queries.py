"""Existing-claim routing, ownership, and contextual coverage regressions."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
)
from backend.app.nlp.intent_classifier import predict_intent
from backend.app.orchestrator.claim_repository import InMemoryClaimRepository
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.schemas import (
    KnowledgeEvidence,
    PolicyRecord,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from backend.app.schemas.domain import ClaimContext
from backend.app.schemas.orchestrator import OrchestratorRequest


OWNER = "TEST-CUSTOMER-001"
OTHER = "TEST-CUSTOMER-002"
OWN_CLAIM_ID = "CLM-OWN-TEST"
OTHER_CLAIM_ID = "CLM-OTHER-USER"


class CapturingGuidance:
    def __init__(self) -> None:
        self.requests: list[GuidanceRequest] = []

    async def generate(self, request: GuidanceRequest) -> GuidanceResponse:
        self.requests.append(request)
        if request.task_type == "claim_information":
            claim = request.safe_customer_context["claim"]
            message = (
                f"Claim {claim['claim_id']} records {claim['incident_type']} "
                f"damage and is {claim['claim_status']}."
            )
        elif request.task_type == "authorization_denied":
            message = (
                "I can't provide information for that claim because claim "
                "information is private. I can help with your own claims instead."
            )
        else:
            message = "Your policy evidence has been applied to the damage in your claim."
        return GuidanceResponse(
            status="success",
            response_type=request.task_type,
            data=GuidanceResponseData(message=message),
        )


class CapturingRetrieval:
    def __init__(self) -> None:
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.requests.append(request)
        return RetrievalResponse(
            request_id=request.request_id,
            status="success",
            result=RetrievalResult(
                policy_data=PolicyRecord(
                    policy_id="POL-OWN-TP",
                    policy_number="MTR-OWN-TP",
                    customer_id=OWNER,
                    status="active",
                    coverage_type="third_party",
                    policy_type="third_party",
                    start_date="2026-01-01",
                    end_date="2027-01-01",
                ),
                knowledge_evidence=[
                    KnowledgeEvidence(
                        evidence_id="CHK-TP-WINDSCREEN",
                        source_id="DOC-TP-ACTIVE",
                        source_title="Active Third Party Motor Policy",
                        section="Windscreen",
                        document_type="policy_manual",
                        content=(
                            "Third party cover excludes windscreen damage to "
                            "the insured vehicle."
                        ),
                        relevance_score=0.91,
                        metadata={
                            "policy_type": "third_party",
                            "status": "active",
                            "version": "3",
                            "audience": "customer",
                        },
                    )
                ],
            ),
        )


class RetrievalMustNotRun:
    async def retrieve(self, _request):
        raise AssertionError("Claim details must come from the claim repository")


def _claim_repository() -> InMemoryClaimRepository:
    repository = InMemoryClaimRepository(
        policies=[
            {
                "policy_id": "POL-OWN-TP",
                "policy_number": "MTR-OWN-TP",
                "customer_id": OWNER,
                "status": "active",
                "coverage_type": "third_party",
                "policy_type": "third_party",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
            }
        ]
    )
    repository.claims_by_workflow["WF-OWN"] = ClaimContext(
        claim_id=OWN_CLAIM_ID,
        claim_reference="REF-OWN-TEST",
        workflow_id="WF-OWN",
        customer_id=OWNER,
        policy_id="POL-OWN-TP",
        policy_number="MTR-OWN-TP",
        vehicle_registration="TEST-VEHICLE-001",
        incident_type="windscreen_damage",
        incident_date=date(2026, 8, 14),
        incident_location="Colombo",
        incident_description="Stone impact cracked the front windscreen.",
        damage_areas=["windscreen"],
        claim_status="under_review",
    )
    repository.claims_by_workflow["WF-OTHER"] = ClaimContext(
        claim_id=OTHER_CLAIM_ID,
        claim_reference="REF-OTHER-SECRET",
        workflow_id="WF-OTHER",
        customer_id=OTHER,
        policy_id="POL-OTHER-SECRET",
        vehicle_registration="SECRET-VEHICLE",
        incident_type="vehicle_collision",
        incident_date=date(2026, 7, 1),
        incident_location="Secret location",
        incident_description="Protected other-customer description.",
        damage_areas=["front bumper"],
        claim_status="approved",
    )
    return repository


@pytest.mark.parametrize(
    "text",
    [
        f"Show me claim {OWN_CLAIM_ID}",
        f"Show me the accident information for claim {OWN_CLAIM_ID}",
        f"What is the status of {OWN_CLAIM_ID}?",
    ],
)
def test_owned_explicit_claim_uses_repository_and_safe_agent4_context(text: str) -> None:
    guidance = CapturingGuidance()
    service = OrchestratorService(
        workflow_repository=InMemoryWorkflowRepository(),
        claim_repository=_claim_repository(),
        retrieval_client=RetrievalMustNotRun(),
        guidance_client=guidance,
    )

    response = asyncio.run(service.process_request(
        OrchestratorRequest(request_id="REQ-OWN-CLAIM", text=text),
        authenticated_user_id=OWNER,
        authenticated_user_role="customer",
    ))

    assert response.status.value == "completed"
    assert response.workflow_type.value == "claim_status"
    assert response.claim_id == OWN_CLAIM_ID
    assert response.intake_result.data.intent.label == "claim_status"
    claim_entities = [
        entity for entity in response.intake_result.data.entities
        if entity.entity_type == "CLAIM_ID"
    ]
    assert [entity.value for entity in claim_entities] == [OWN_CLAIM_ID]
    request = guidance.requests[-1]
    assert request.task_type == "claim_information"
    assert request.claim_data is None
    assert request.safe_customer_context["authorization_result"] == "allowed"
    safe_claim = request.safe_customer_context["claim"]
    assert safe_claim["claim_id"] == OWN_CLAIM_ID
    assert safe_claim["incident_type"] == "windscreen_damage"
    assert safe_claim["damage_areas"] == ["windscreen"]
    assert safe_claim["claim_status"] == "under_review"
    serialized = request.model_dump_json()
    assert OWNER not in serialized
    assert request.fraud_assessment is None
    assert request.human_decision is None


@pytest.mark.parametrize(
    "text",
    [
        f"Show me claim {OTHER_CLAIM_ID}",
        f"Show me the accident and claim information belonging to {OTHER_CLAIM_ID}",
        f"Does my policy cover the damage in {OTHER_CLAIM_ID}?",
    ],
)
def test_other_customer_claim_is_denied_before_retrieval_or_agent4_data(
    text: str,
) -> None:
    guidance = CapturingGuidance()
    service = OrchestratorService(
        workflow_repository=InMemoryWorkflowRepository(),
        claim_repository=_claim_repository(),
        retrieval_client=RetrievalMustNotRun(),
        guidance_client=guidance,
    )

    response = asyncio.run(service.process_request(
        OrchestratorRequest(request_id="REQ-OTHER-CLAIM", text=text),
        authenticated_user_id=OWNER,
        authenticated_user_role="customer",
    ))

    assert response.status.value == "completed"
    assert response.claim_id is None
    request = guidance.requests[-1]
    assert request.task_type == "authorization_denied"
    assert request.claim_data is None
    assert request.retrieved_evidence == []
    assert request.safe_customer_context["ownership"] == "not_accessible"
    serialized = request.model_dump_json()
    for protected_value in (
        OTHER_CLAIM_ID,
        OTHER,
        "REF-OTHER-SECRET",
        "POL-OTHER-SECRET",
        "SECRET-VEHICLE",
        "Secret location",
        "Protected other-customer description",
        "front bumper",
        "approved",
    ):
        assert protected_value not in serialized


def test_claim_id_coverage_uses_owned_claim_policy_and_filtered_agent2_request() -> None:
    retrieval = CapturingRetrieval()
    guidance = CapturingGuidance()
    service = OrchestratorService(
        workflow_repository=InMemoryWorkflowRepository(),
        claim_repository=_claim_repository(),
        retrieval_client=retrieval,
        guidance_client=guidance,
    )

    response = asyncio.run(service.process_request(
        OrchestratorRequest(
            request_id="REQ-CLAIM-COVERAGE",
            text=f"Does my policy cover the damage in {OWN_CLAIM_ID}?",
        ),
        authenticated_user_id=OWNER,
        authenticated_user_role="customer",
    ))

    assert response.status.value == "completed"
    assert response.workflow_type.value == "information_request"
    request = retrieval.requests[-1]
    assert request.user_context.user_id == OWNER
    assert request.claim_lookup.claim_id == OWN_CLAIM_ID
    assert request.claim_context.incident_type == "windscreen_damage"
    assert request.claim_context.damage_areas == ["windscreen"]
    assert request.policy_context.policy_id == "POL-OWN-TP"
    assert request.policy_context.policy_type == "third_party"
    assert response.evidence_summary[0]["source_id"] == "DOC-TP-ACTIVE"
    assert response.evidence_summary[0]["relevance_score"] == 0.91
    guidance_request = guidance.requests[-1]
    assert guidance_request.task_type == "coverage_answer"
    assert guidance_request.claim_data["claim_id"] == OWN_CLAIM_ID
    assert guidance_request.retrieved_evidence[0].section == "Windscreen"


def test_coverage_followup_reuses_only_owned_prior_claim_context() -> None:
    workflow_repository = InMemoryWorkflowRepository()
    retrieval = CapturingRetrieval()
    guidance = CapturingGuidance()
    service = OrchestratorService(
        workflow_repository=workflow_repository,
        claim_repository=_claim_repository(),
        retrieval_client=retrieval,
        guidance_client=guidance,
    )
    first = asyncio.run(service.process_request(
        OrchestratorRequest(
            request_id="REQ-CLAIM-FIRST",
            text=f"Show me claim {OWN_CLAIM_ID}",
        ),
        authenticated_user_id=OWNER,
        authenticated_user_role="customer",
    ))

    second = asyncio.run(service.process_request(
        OrchestratorRequest(
            request_id="REQ-CLAIM-FOLLOWUP",
            text="Is that damage covered by my policy?",
            context_workflow_id=first.workflow_id,
        ),
        authenticated_user_id=OWNER,
        authenticated_user_role="customer",
    ))

    assert second.status.value == "completed"
    request = retrieval.requests[-1]
    assert request.claim_lookup.claim_id == OWN_CLAIM_ID
    assert request.claim_context.damage_areas == ["windscreen"]
    assert any(
        event.step == "claim_context"
        and "Owned prior claim context" in event.message
        for event in second.audit_trail
    )


def test_required_documents_question_without_claim_id_stays_knowledge_query() -> None:
    label, _ = predict_intent("What documents do I need for a collision claim?")
    assert label == "required_documents_question"


def test_real_format_claim_id_is_extracted_and_routes_as_existing_claim() -> None:
    claim_id = "CLM-EFD1DCFEF7D25985BCCFAAF472EDC56B"
    label, confidence = predict_intent(
        f"Show me the accident and claim information belonging to claim id {claim_id}"
    )
    assert label == "claim_status"
    assert confidence == 0.99


def test_missing_and_other_customer_claims_have_same_non_enumerating_context() -> None:
    contexts = []
    messages = []
    for claim_id in (OTHER_CLAIM_ID, "CLM-NOT-ACCESSIBLE"):
        guidance = CapturingGuidance()
        service = OrchestratorService(
            workflow_repository=InMemoryWorkflowRepository(),
            claim_repository=_claim_repository(),
            retrieval_client=RetrievalMustNotRun(),
            guidance_client=guidance,
        )
        response = asyncio.run(service.process_request(
            OrchestratorRequest(
                request_id=f"REQ-{claim_id}",
                text=f"Show me claim {claim_id}",
            ),
            authenticated_user_id=OWNER,
            authenticated_user_role="customer",
        ))
        contexts.append(guidance.requests[-1].safe_customer_context)
        messages.append(response.message)

    assert contexts[0] == contexts[1]
    assert messages[0] == messages[1]
