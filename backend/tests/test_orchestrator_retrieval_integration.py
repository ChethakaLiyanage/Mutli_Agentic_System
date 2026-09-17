from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.main import app
from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.schemas import (
    KnowledgeChunk,
    KnowledgeEvidence,
    RetrievalError,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.auth import AuthenticatedUser
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
)
from backend.app.security.dependencies import get_current_customer
from backend.app.security.roles import UserRole


OWNER_ID = "USR-STEP4"
OWNER_ROLE = "customer"


class FakeIntakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, IntakeResponse):
            return outcome.model_copy(update={"request_id": request.request_id})
        label, clarification = outcome
        return IntakeResponse(
            request_id=request.request_id,
            status="success",
            data=IntakeData(
                intent=IntentResult(label=label, confidence=0.87),
                requires_clarification=clarification,
            ),
        )


class FakeRetrievalClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response.model_copy(update={"request_id": request.request_id})


def retrieval_response(status="success", *, evidence=True, warnings=None):
    knowledge = []
    if evidence:
        knowledge.append(KnowledgeEvidence(
            evidence_id="CHK-THEFT", source_id="DOC-GUIDE",
            source_title="Synthetic Claims Guide", section="Theft documents",
            document_type="procedure_guide",
            content="A theft claim requires a police report and vehicle registration.",
            relevance_score=0.91,
            metadata={
                "source_document_id": "DOC-GUIDE", "chunk_id": "CHK-THEFT",
                "document_type": "procedure_guide", "content_hash": "internal",
            },
        ))
    errors = []
    if status == "failed":
        errors = [RetrievalError(
            error_code="retrieval_failed", message="Retrieval could not be completed safely.",
            source="retrieval_service", retryable=True,
        )]
    return RetrievalResponse(
        request_id="placeholder", status=status,
        result=RetrievalResult(
            knowledge_evidence=knowledge,
            missing_evidence=(
                ["knowledge_evidence_not_found"] if status == "no_results" else []
            ),
            warnings=warnings or [],
        ), errors=errors,
    )


async def _process(label, retrieval, *, text="What documents are required for theft?"):
    repository = InMemoryWorkflowRepository()
    service = OrchestratorService(
        claim_intake_client=FakeIntakeClient([(label, False)]),
        workflow_repository=repository,
        retrieval_client=retrieval,
    )
    response = await service.process_request(
        OrchestratorRequest(request_id="REQ-STEP4", text=text),
        authenticated_user_id=OWNER_ID,
        authenticated_user_role=OWNER_ROLE,
    )
    return response, repository


@pytest.mark.parametrize(
    "intent",
    ["policy_question", "coverage_question", "required_documents_question", "general_information"],
)
def test_all_information_intents_route_to_retrieval_and_persist(intent):
    client = FakeRetrievalClient(retrieval_response())
    response, repository = asyncio.run(_process(intent, client))
    assert response.status is WorkflowStatus.RETRIEVAL_COMPLETE
    assert response.workflow_type is WorkflowType.INFORMATION_REQUEST
    assert response.retrieval_result["status"] == "success"
    assert response.evidence_summary[0]["evidence_id"] == "CHK-THEFT"
    assert "content_hash" not in response.evidence_summary[0]["metadata"]
    assert len(client.requests) == 1
    saved = asyncio.run(repository.get(response.workflow_id))
    assert saved.retrieval_result["result"]["knowledge_evidence"]
    assert saved.intake_result is not None


def test_retrieval_receives_original_natural_language_and_trusted_identity():
    text = "Does my policy cover flood damage?"
    client = FakeRetrievalClient(retrieval_response())
    asyncio.run(_process("coverage_question", client, text=text))
    request = client.requests[0]
    assert request.query == text
    assert request.user_context.user_id == OWNER_ID
    assert request.policy_context is None


@pytest.mark.parametrize(
    ("retrieval_status", "expected_status"),
    [
        ("partial_success", WorkflowStatus.RETRIEVAL_COMPLETE),
        ("no_results", WorkflowStatus.RETRIEVAL_COMPLETE),
        ("failed", WorkflowStatus.FAILED),
    ],
)
def test_retrieval_statuses_are_handled_explicitly(retrieval_status, expected_status):
    response, _ = asyncio.run(_process(
        "policy_question",
        FakeRetrievalClient(retrieval_response(
            retrieval_status,
            evidence=retrieval_status == "partial_success",
            warnings=["generic evidence only"] if retrieval_status == "partial_success" else [],
        )),
    ))
    assert response.status is expected_status
    assert response.retrieval_status == retrieval_status
    if retrieval_status == "partial_success":
        assert response.warnings == ["generic evidence only"]
        assert response.evidence_summary
    elif retrieval_status == "no_results":
        assert response.evidence_summary == []
        assert response.message == "No relevant controlled evidence was found."
    else:
        assert response.errors[0].code == "RETRIEVAL_FAILED"


def test_retrieval_client_exception_is_controlled_and_persisted():
    detail = "secret SQL and filesystem details"
    response, repository = asyncio.run(_process(
        "general_information", FakeRetrievalClient(error=RuntimeError(detail))
    ))
    assert response.status is WorkflowStatus.FAILED
    assert detail not in response.model_dump_json()
    saved = asyncio.run(repository.get(response.workflow_id))
    assert saved.current_status is WorkflowStatus.FAILED
    assert saved.audit_trail[-1].status.value == "failed"


def test_claim_submission_does_not_call_retrieval():
    client = FakeRetrievalClient(retrieval_response())
    response, _ = asyncio.run(_process("claim_submission", client))
    assert response.status is WorkflowStatus.INTAKE_COMPLETE
    assert response.retrieval_result is None
    assert client.requests == []


def test_clarification_can_continue_into_information_retrieval():
    async def scenario():
        repository = InMemoryWorkflowRepository()
        intake = FakeIntakeClient([
            ("general_information", True),
            ("coverage_question", False),
        ])
        retrieval = FakeRetrievalClient(retrieval_response())
        service = OrchestratorService(intake, repository, retrieval)
        initial = await service.process_request(
            OrchestratorRequest(request_id="REQ-1", text="Can you help?"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert isinstance(initial, ClarificationResponse)
        resumed = await service.resume_clarification(
            initial.workflow_id,
            ClarificationRequest(request_id="REQ-2", text="Is flood covered?"),
            authenticated_user_id=OWNER_ID,
            authenticated_user_role=OWNER_ROLE,
        )
        assert resumed.workflow_id == initial.workflow_id
        assert resumed.status is WorkflowStatus.RETRIEVAL_COMPLETE
        assert retrieval.requests[0].query == "Can you help? Is flood covered?"
    asyncio.run(scenario())


class MemoryCorpusRepository:
    def __init__(self, chunks): self.chunks = chunks
    def list_knowledge_chunks(self, *, insurance_type="motor", document_type=None):
        return [item for item in self.chunks if document_type is None or item.document_type == document_type]


class EmptyStructuredRepository:
    def get_policy_by_id(self, *args, **kwargs): return None
    def get_policy_by_number(self, *args, **kwargs): return None
    def get_claim_by_id(self, *args, **kwargs): return None
    def get_claim_by_reference(self, *args, **kwargs): return None
    def get_policy_claim_history(self, *args, **kwargs): return []
    def get_claim_documents(self, *args, **kwargs): return []


def test_real_agent1_to_real_lexical_agent2_without_downstream_agents():
    content = "A theft claim requires a police report, vehicle registration, and claim form."
    chunk = KnowledgeChunk(
        chunk_id="CHK-REAL", source_document_id="DOC-REAL",
        source_title="Synthetic Theft Guide", document_type="procedure_guide",
        section="Required documents", content=content,
        normalized_content=preprocess_for_retrieval(content), metadata={},
    )
    lexical = KnowledgeRetriever(repository=MemoryCorpusRepository([chunk]))
    retrieval_service = RetrievalService(EmptyStructuredRepository(), lexical)
    service = OrchestratorService(
        claim_intake_client=LocalClaimIntakeClient(),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=LocalRetrievalClient(retrieval_service),
    )
    response = asyncio.run(service.process_request(
        OrchestratorRequest(
            request_id="REQ-REAL",
            text="Do you need the other vehicle's registration number",
        ),
        authenticated_user_id=OWNER_ID,
        authenticated_user_role=OWNER_ROLE,
    ))
    assert response.workflow_type is WorkflowType.INFORMATION_REQUEST
    assert response.status is WorkflowStatus.RETRIEVAL_COMPLETE
    assert response.evidence_summary[0]["evidence_id"] == "CHK-REAL"
    assert response.fraud_result is None
    assert response.guidance_result is None


def test_authenticated_orchestrator_api_returns_retrieval_complete():
    user = AuthenticatedUser(
        user_id=OWNER_ID, email="step4@example.com", role=UserRole.CUSTOMER,
        created_at=datetime.now(timezone.utc),
    )
    service = OrchestratorService(
        claim_intake_client=FakeIntakeClient([("required_documents_question", False)]),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=FakeRetrievalClient(retrieval_response()),
    )
    app.dependency_overrides[get_current_customer] = lambda: user
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            http_response = client.post(
                "/orchestrator/process",
                json={"request_id": "REQ-API", "text": "What documents are required for theft?"},
            )
        assert http_response.status_code == 200
        body = http_response.json()
        assert body["status"] == "retrieval_complete"
        assert body["workflow_type"] == "information_request"
        assert body["retrieval_result"]["status"] == "success"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("retrieval_status", "workflow_status"),
    [("no_results", "retrieval_complete"), ("failed", "failed")],
)
def test_authenticated_api_handles_no_results_and_failure(
    retrieval_status, workflow_status
):
    user = AuthenticatedUser(
        user_id=OWNER_ID, email="step4@example.com", role=UserRole.CUSTOMER,
        created_at=datetime.now(timezone.utc),
    )
    service = OrchestratorService(
        claim_intake_client=FakeIntakeClient([("policy_question", False)]),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=FakeRetrievalClient(
            retrieval_response(retrieval_status, evidence=False)
        ),
    )
    app.dependency_overrides[get_current_customer] = lambda: user
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orchestrator/process",
                json={"request_id": "REQ-API-STATUS", "text": "Explain motor insurance"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == workflow_status
        assert response.json()["retrieval_status"] == retrieval_status
    finally:
        app.dependency_overrides.clear()


def test_authenticated_clarification_api_continues_to_retrieval():
    user = AuthenticatedUser(
        user_id=OWNER_ID, email="step4@example.com", role=UserRole.CUSTOMER,
        created_at=datetime.now(timezone.utc),
    )
    service = OrchestratorService(
        claim_intake_client=FakeIntakeClient([
            ("general_information", True), ("coverage_question", False)
        ]),
        workflow_repository=InMemoryWorkflowRepository(),
        retrieval_client=FakeRetrievalClient(retrieval_response()),
    )
    app.dependency_overrides[get_current_customer] = lambda: user
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: service
    try:
        with TestClient(app) as client:
            initial = client.post(
                "/orchestrator/process",
                json={"request_id": "REQ-C1", "text": "Can you help?"},
            ).json()
            resumed = client.post(
                f"/orchestrator/workflows/{initial['workflow_id']}/clarify",
                json={"request_id": "REQ-C2", "text": "Is flood covered?"},
            )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "retrieval_complete"
        assert resumed.json()["workflow_id"] == initial["workflow_id"]
    finally:
        app.dependency_overrides.clear()
