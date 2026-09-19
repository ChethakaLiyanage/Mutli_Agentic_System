from __future__ import annotations

import asyncio
from datetime import date

import pytest

from backend.app.fraud.repository import InMemoryFraudRepository
from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalFraudClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.claim_repository import InMemoryClaimRepository
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.schemas import (
    PolicyRecord,
    ClaimRecord,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.domain import FraudAssessmentContext
from backend.app.schemas.intake import (
    DamageInformation,
    IncidentInformation,
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.orchestrator import ClarificationRequest, OrchestratorRequest


USER_ID = "USR-FRAUD-FLOW"
POLICY = {
    "policy_id": "POL-FRAUD-FLOW",
    "policy_number": "MTR-FRAUD-FLOW",
    "customer_id": USER_ID,
    "status": "active",
    "start_date": "2026-01-01",
    "end_date": "2027-01-01",
}


def intake(*, complete=True, label="claim_submission") -> IntakeResponse:
    return IntakeResponse(
        request_id="placeholder", status="success",
        data=IntakeData(
            intent=IntentResult(label=label, confidence=0.91),
            incident=IncidentInformation(
                type="vehicle_collision" if complete else None,
                date_text="today" if complete else None,
                normalized_date=date.today().isoformat() if complete else None,
                location="Colombo" if complete else None,
            ),
            damage=DamageInformation(areas=["front bumper"] if complete else []),
            missing_fields=[] if complete else ["incident_type", "incident_date", "location"],
            requires_clarification=not complete,
        ),
    )


class FakeIntake:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        self.calls += 1
        return self.responses.pop(0).model_copy(update={"request_id": request.request_id})


class FakeRetrieval:
    def __init__(self, *, status="success"):
        self.status = status
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.requests.append(request)
        return RetrievalResponse(
            request_id=request.request_id,
            status=self.status,
            result=RetrievalResult(
                policy_data=PolicyRecord(**POLICY),
                historical_claims=[], document_facts=[],
            ),
        )


class FakeFraud:
    def __init__(self, level="medium", action="manual_review", error=None):
        self.level = level
        self.action = action
        self.error = error
        self.calls = []

    async def assess(self, **kwargs) -> FraudAssessmentContext:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FraudAssessmentContext(
            claim_id=kwargs["claim"].claim_id,
            risk_score={"low": 0.1, "medium": 0.5, "high": 0.8}[self.level],
            rule_score={"low": 0.0, "medium": 0.5, "high": 0.8}[self.level],
            risk_level=self.level,
            indicators=[], recommended_action=self.action,
            automated_decision=False,
        )


def service(intake_client, retrieval=None, fraud=None, claims=None, assessments=None):
    return OrchestratorService(
        claim_intake_client=intake_client,
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=retrieval or FakeRetrieval(),
        fraud_client=fraud or FakeFraud(),
        claim_repository=claims or InMemoryClaimRepository([POLICY]),
        fraud_repository=assessments or InMemoryFraudRepository(),
    )


@pytest.mark.parametrize(
    ("level", "action"),
    [("low", "continue_processing"), ("medium", "manual_review"), ("high", "escalate")],
)
def test_every_risk_level_ends_at_human_review(level, action) -> None:
    fraud = FakeFraud(level, action)
    orchestrator = service(FakeIntake(intake()), fraud=fraud)
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-FRAUD", text="My car collided today in Colombo."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert response.status is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert response.workflow_type is WorkflowType.CLAIM_SUBMISSION
    assert response.fraud_risk_level is None
    assert response.fraud_result is None
    saved = asyncio.run(orchestrator.workflow_repository.get(response.workflow_id))
    assert saved.fraud_result["risk_level"] == level
    assert saved.fraud_result["recommended_action"] == action
    assert saved.fraud_result["automated_decision"] is False
    assert "approved" not in response.message.lower()
    assert "rejected" not in response.message.lower()


def test_claim_flow_uses_trusted_identity_and_persists_once() -> None:
    claims = InMemoryClaimRepository([POLICY])
    assessments = InMemoryFraudRepository()
    retrieval = FakeRetrieval()
    orchestrator = service(FakeIntake(intake()), retrieval, claims=claims, assessments=assessments)
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-OWNER", text="A collision happened today in Colombo."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert len(claims.claims_by_workflow) == 1
    assert len(assessments.assessments) == 1
    assert retrieval.requests[0].user_context.user_id == USER_ID
    saved = asyncio.run(orchestrator.workflow_repository.get(response.workflow_id))
    assert retrieval.requests[0].claim_lookup.claim_id == saved.fraud_result["claim_id"]
    assert retrieval.requests[0].policy_context.policy_id == POLICY["policy_id"]


def test_claim_without_linked_policy_is_saved_and_stops_before_downstream_agents() -> None:
    claims = InMemoryClaimRepository()
    retrieval = FakeRetrieval()
    fraud = FakeFraud()
    orchestrator = service(
        FakeIntake(intake()),
        retrieval,
        fraud=fraud,
        claims=claims,
    )

    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(
            request_id="REQ-NO-POLICY",
            text="My car crashed yesterday near Kandy.",
        ),
        authenticated_user_id=USER_ID,
        authenticated_user_role="customer",
    ))

    assert response.status is WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED
    assert response.errors[0].code == "POLICY_LINK_REQUIRED"
    assert "claim details were saved" in response.message
    assert "policy" in response.message.lower()
    assert retrieval.requests == []
    assert fraud.calls == []
    stored = claims.claims_by_workflow[response.workflow_id]
    assert stored.customer_id == USER_ID
    assert stored.policy_id is None
    assert stored.claim_status == "policy_link_required"


@pytest.mark.parametrize(
    "intent",
    ["policy_question", "coverage_question", "required_documents_question", "general_information"],
)
def test_information_requests_never_call_fraud(intent) -> None:
    fraud = FakeFraud()
    orchestrator = service(FakeIntake(intake(label=intent)), fraud=fraud)
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-INFO", text="Please explain this policy question."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert response.status is WorkflowStatus.RETRIEVAL_COMPLETE
    assert fraud.calls == []


def test_clarification_resumes_same_workflow_without_duplicate_claim() -> None:
    claims = InMemoryClaimRepository([POLICY])
    orchestrator = service(FakeIntake(intake(complete=False), intake()), claims=claims)
    first = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-CLARIFY-1", text="My car was damaged and I want to claim."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    second = asyncio.run(orchestrator.resume_clarification(
        first.workflow_id,
        ClarificationRequest(request_id="REQ-CLARIFY-2", text="It collided today in Colombo."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert second.workflow_id == first.workflow_id
    assert second.status is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert len(claims.claims_by_workflow) == 1


def test_fraud_failure_is_controlled_and_internal_detail_is_hidden() -> None:
    orchestrator = service(
        FakeIntake(intake()), fraud=FakeFraud(error=RuntimeError("secret detail"))
    )
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-FAIL", text="A collision happened today in Colombo."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert response.status is WorkflowStatus.FAILED
    assert response.errors[0].code == "FRAUD_TRIAGE_FAILED"
    assert "secret detail" not in response.model_dump_json()


def test_real_fraud_engine_handles_missing_amount_without_fabrication() -> None:
    orchestrator = service(FakeIntake(intake()), fraud=LocalFraudClient())
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(request_id="REQ-REAL", text="A collision happened today in Colombo."),
        authenticated_user_id=USER_ID, authenticated_user_role="customer",
    ))
    assert response.status is WorkflowStatus.AWAITING_HUMAN_REVIEW
    saved = asyncio.run(orchestrator.workflow_repository.get(response.workflow_id))
    assert saved.fraud_result["anomaly_score"] is None
    assert saved.fraud_result["automated_decision"] is False
    assert response.missing_document_summary == []
    assert response.guidance_result is not None
    assert response.guidance_result["response_type"] in {"claim_progress", "awaiting_human_review"}
    assert "claims officer" in response.message.lower()
    assert "risk" not in response.message.lower()
    assert "fraud" not in response.message.lower()


class SyntheticStructuredRepository:
    def get_policy_by_id(self, policy_id, user_id):
        if policy_id == POLICY["policy_id"] and user_id == USER_ID:
            return PolicyRecord(**POLICY)
        return None

    def get_policy_by_number(self, policy_number, user_id):
        if policy_number == POLICY["policy_number"] and user_id == USER_ID:
            return PolicyRecord(**POLICY)
        return None

    def get_claim_by_id(self, claim_id, user_id):
        return ClaimRecord(
            claim_id=claim_id, claim_reference="REF-SYNTHETIC",
            customer_id=user_id, policy_id=POLICY["policy_id"],
            claim_type="vehicle_collision", incident_date="2026-09-16",
            incident_location="Kandy", claimed_amount=None,
            status="awaiting_human_review",
        )

    def get_policy_claim_history(self, **_kwargs):
        return []

    def get_claim_documents(self, **_kwargs):
        return []


def test_real_agent1_agent2_agent3_pipeline_with_synthetic_storage() -> None:
    retrieval = LocalRetrievalClient(
        RetrievalService(repository=SyntheticStructuredRepository())
    )
    orchestrator = OrchestratorService(
        claim_intake_client=LocalClaimIntakeClient(),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=retrieval,
        fraud_client=LocalFraudClient(),
        claim_repository=InMemoryClaimRepository([POLICY]),
        fraud_repository=InMemoryFraudRepository(),
    )
    response = asyncio.run(orchestrator.process_request(
        OrchestratorRequest(
            request_id="REQ-REAL-PIPELINE",
            text="A bus hit my car yesterday near Kandy and damaged the left door.",
        ),
        authenticated_user_id=USER_ID,
        authenticated_user_role="customer",
    ))
    assert response.status is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert response.intake_result.data.intent.label == "claim_submission"
    assert response.retrieval_result["result"]["policy_data"] is None
    saved = asyncio.run(orchestrator.workflow_repository.get(response.workflow_id))
    assert saved.fraud_result["automated_decision"] is False
