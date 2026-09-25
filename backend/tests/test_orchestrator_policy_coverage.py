"""End-to-end multi-agent orchestrator coverage retrieval tests for all policy categories."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.guidance.service import GuidanceService
from backend.app.llm.client import MockLLMClient
from backend.app.llm.config import LLMSettings
from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalGuidanceClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.claim_repository import InMemoryClaimRepository
from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.document_ingestion import DocumentIngestor
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.schemas import KnowledgeChunk, PolicyRecord
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.orchestrator import OrchestratorRequest
from backend.app.security.roles import UserRole


class MemoryRetrievalRepository:
    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self.chunks: list[KnowledgeChunk] = list(chunks or [])
        self.policies: dict[str, PolicyRecord] = {}

    def list_knowledge_chunks(
        self,
        *,
        insurance_type: str = "motor",
        document_type: str | None = None,
    ) -> list[KnowledgeChunk]:
        return [
            item for item in self.chunks
            if item.insurance_type == insurance_type
            and (document_type is None or item.document_type == document_type)
        ]

    def get_policy_by_number(self, policy_number: str, user_id: str | None = None) -> PolicyRecord | None:
        return next(
            (
                policy for policy in self.policies.values()
                if policy.policy_number == policy_number
                and policy.customer_id == user_id
            ),
            None,
        )

    def get_policy_by_id(self, policy_id: str, user_id: str | None = None) -> PolicyRecord | None:
        policy = self.policies.get(policy_id)
        return policy if policy is not None and policy.customer_id == user_id else None

    def get_knowledge_chunks_by_source(self, source_document_id: str) -> list[KnowledgeChunk]:
        return [item for item in self.chunks if item.source_document_id == source_document_id]

    def replace_knowledge_chunks(
        self, source_document_id: str, chunks: list[KnowledgeChunk]
    ) -> list[KnowledgeChunk]:
        self.chunks = [
            item for item in self.chunks if item.source_document_id != source_document_id
        ] + list(chunks)
        return list(chunks)


@pytest.fixture
def orchestrator_setup():
    corpus_repo = MemoryRetrievalRepository()
    ingestor = DocumentIngestor(corpus_repo)

    docs_dir = Path(__file__).resolve().parents[1] / "data" / "policy_docs"
    active_metadata = {"status": "active", "audience": "customer", "version": "1.0"}
    ingestor.ingest_file(docs_dir / "full_comprehensive_motor_policy.txt", document_type="policy_manual", policy_type="full_comprehensive", metadata=active_metadata)
    ingestor.ingest_file(docs_dir / "partial_comprehensive_motor_policy.txt", document_type="policy_manual", policy_type="partial_comprehensive", metadata=active_metadata)
    ingestor.ingest_file(docs_dir / "third_party_motor_policy.txt", document_type="policy_manual", policy_type="third_party", metadata=active_metadata)

    retriever = KnowledgeRetriever(repository=corpus_repo)
    retrieval_service = RetrievalService(repository=corpus_repo, knowledge_retriever=retriever)
    guidance_service = GuidanceService(MockLLMClient(LLMSettings(provider="mock")))

    claim_repo = InMemoryClaimRepository()
    workflow_repo = InMemoryWorkflowRepository()

    # Provision 3 customers with different policy types
    cust_full = "USR-CUST-FULL-001"
    cust_partial = "USR-CUST-PART-002"
    cust_tp = "USR-CUST-TP-003"
    cust_none = "USR-CUST-NONE-004"
    cust_multi = "USR-CUST-MULTI-005"

    created_policies = [
        claim_repo.create_customer_policy(customer_id=cust_full, policy_type="full_comprehensive"),
        claim_repo.create_customer_policy(customer_id=cust_partial, policy_type="partial_comprehensive"),
        claim_repo.create_customer_policy(customer_id=cust_tp, policy_type="third_party"),
    ]
    for policy in created_policies:
        corpus_repo.policies[policy["policy_id"]] = PolicyRecord.model_validate(policy)

    # Multi-policy customer
    claim_repo.create_customer_policy(customer_id=cust_multi, policy_type="full_comprehensive")
    claim_repo.create_customer_policy(customer_id=cust_multi, policy_type="third_party")

    orchestrator = OrchestratorService(
        claim_intake_client=LocalClaimIntakeClient(ClaimIntakeAgent()),
        retrieval_client=LocalRetrievalClient(retrieval_service),
        guidance_client=LocalGuidanceClient(guidance_service),
        workflow_repository=workflow_repo,
        claim_repository=claim_repo,
    )

    return {
        "orchestrator": orchestrator,
        "cust_full": cust_full,
        "cust_partial": cust_partial,
        "cust_tp": cust_tp,
        "cust_none": cust_none,
        "cust_multi": cust_multi,
    }


def test_customer_without_active_policy_receives_safe_notice(orchestrator_setup) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    user_id = orchestrator_setup["cust_none"]

    req = OrchestratorRequest(
        request_id="REQ-TEST-NONE",
        text="What is my policy coverage?",
    )

    resp = asyncio.run(
        svc.process_request(
            req,
            authenticated_user_id=user_id,
            authenticated_user_role="customer",
        )
    )
    assert resp.status is WorkflowStatus.COMPLETED
    assert "I couldn't find an active motor policy linked to your account, so I can't confirm your personal coverage." in resp.message


def test_customer_with_multiple_policies_receives_clarification_notice(orchestrator_setup) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    user_id = orchestrator_setup["cust_multi"]

    req = OrchestratorRequest(
        request_id="REQ-TEST-MULTI",
        text="What is my insurance coverage?",
    )

    resp = asyncio.run(
        svc.process_request(
            req,
            authenticated_user_id=user_id,
            authenticated_user_role="customer",
        )
    )
    assert resp.status is WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED
    assert "multiple active motor policies" in resp.message.lower()


def test_full_comprehensive_customer_retrieves_all_perils_coverage(orchestrator_setup) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    user_id = orchestrator_setup["cust_full"]

    req = OrchestratorRequest(
        request_id="REQ-TEST-FULL",
        text="What is my coverage?",
    )

    resp = asyncio.run(
        svc.process_request(
            req,
            authenticated_user_id=user_id,
            authenticated_user_role="customer",
        )
    )
    assert resp.status is WorkflowStatus.COMPLETED
    msg = resp.message.lower()
    # Check that guidance reflects full comprehensive policy wording
    assert "comprehensive" in msg or "coverage" in msg or "collision" in msg
    assert "third party only" not in msg


def test_partial_comprehensive_customer_retrieval_confirms_collision_exclusion(orchestrator_setup) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    user_id = orchestrator_setup["cust_partial"]

    req = OrchestratorRequest(
        request_id="REQ-TEST-PARTIAL",
        text="Am I covered if my car is damaged in a collision?",
    )

    resp = asyncio.run(
        svc.process_request(
            req,
            authenticated_user_id=user_id,
            authenticated_user_role="customer",
        )
    )
    assert resp.status is WorkflowStatus.COMPLETED
    msg = resp.message.lower()
    # Verify that collision exclusion is communicated
    assert "collision" in msg
    assert "excluded" in msg or "not covered" in msg or "exclusion" in msg or "partial comprehensive" in msg


def test_third_party_customer_retrieval_confirms_own_vehicle_exclusion(orchestrator_setup) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    user_id = orchestrator_setup["cust_tp"]

    req = OrchestratorRequest(
        request_id="REQ-TEST-TP",
        text="What is my coverage?",
    )

    resp = asyncio.run(
        svc.process_request(
            req,
            authenticated_user_id=user_id,
            authenticated_user_role="customer",
        )
    )
    assert resp.status is WorkflowStatus.COMPLETED
    msg = resp.message.lower()
    # Verify that third party liability is stated and own vehicle damage is not claimed as covered
    assert "third party" in msg
    assert "exclusion" in msg or "excluded" in msg or "not covered" in msg or "liability" in msg


@pytest.mark.parametrize(
    ("customer_key", "policy_type"),
    [
        ("cust_full", "full_comprehensive"),
        ("cust_partial", "partial_comprehensive"),
        ("cust_tp", "third_party"),
    ],
)
@pytest.mark.parametrize(
    "query",
    [
        "What is my policy coverage?",
        "Does my policy cover windscreen damage?",
    ],
)
def test_authenticated_policy_queries_use_only_the_active_category_corpus(
    orchestrator_setup,
    customer_key: str,
    policy_type: str,
    query: str,
) -> None:
    svc: OrchestratorService = orchestrator_setup["orchestrator"]
    response = asyncio.run(
        svc.process_request(
            OrchestratorRequest(
                request_id=f"REQ-SCOPE-{customer_key}-{len(query)}",
                text=query,
            ),
            authenticated_user_id=orchestrator_setup[customer_key],
            authenticated_user_role="customer",
        )
    )

    assert response.intake_result is not None
    assert response.intake_result.data.intent.label == "coverage_question"
    assert response.status is WorkflowStatus.COMPLETED
    assert response.retrieval_result is not None
    assert response.retrieval_result["status"] == "success"
    result = response.retrieval_result["result"]
    assert result["policy_data"]["policy_type"] == policy_type
    assert result["knowledge_evidence"]
    for evidence in result["knowledge_evidence"]:
        assert evidence["metadata"]["policy_type"] == policy_type
        assert evidence["metadata"]["status"] == "active"
        assert evidence["metadata"]["audience"] == "customer"
        assert evidence["document_type"] in {"policy_document", "policy_manual"}
    assert response.guidance_result is not None
    assert response.guidance_result["response_type"] == "coverage_answer"
    assert response.guidance_result["data"]["insufficient_evidence"] is False


@pytest.mark.parametrize(
    "query",
    [
        "What is my coverage?",
        "What is my policy coverage?",
        "What does my policy cover?",
        "What coverage do I have?",
        "Does my policy cover fire?",
        "Am I covered for theft?",
        "Does my insurance cover flood damage?",
        "Does my policy cover windscreen damage?",
    ],
)
def test_personal_coverage_wording_resolves_authenticated_policy_context(
    orchestrator_setup,
    query: str,
) -> None:
    response = asyncio.run(
        orchestrator_setup["orchestrator"].process_request(
            OrchestratorRequest(
                request_id=f"REQ-PERSONAL-{abs(hash(query))}",
                text=query,
            ),
            authenticated_user_id=orchestrator_setup["cust_full"],
            authenticated_user_role="customer",
        )
    )

    assert response.intake_result is not None
    assert response.intake_result.data.intent.label == "coverage_question"
    assert response.retrieval_result is not None
    result = response.retrieval_result["result"]
    assert result["policy_data"]["policy_type"] == "full_comprehensive"
    assert result["knowledge_evidence"]
    assert all(
        evidence["metadata"]["policy_type"] == "full_comprehensive"
        for evidence in result["knowledge_evidence"]
    )


@pytest.mark.parametrize(
    ("query", "expected_policy_type", "expected_title"),
    [
        (
            "Tell me about full comprehensive policy",
            "full_comprehensive",
            "full_comprehensive_motor_policy",
        ),
        (
            "Tell me about partial policy",
            "partial_comprehensive",
            "partial_comprehensive_motor_policy",
        ),
        (
            "Tell me about third party policy",
            "third_party",
            "third_party_motor_policy",
        ),
        (
            "Does third party insurance cover windscreen damage?",
            "third_party",
            "third_party_motor_policy",
        ),
    ],
)
def test_explicit_policy_type_overrides_authenticated_customer_category(
    orchestrator_setup,
    query: str,
    expected_policy_type: str,
    expected_title: str,
) -> None:
    response = asyncio.run(
        orchestrator_setup["orchestrator"].process_request(
            OrchestratorRequest(
                request_id=f"REQ-EXPLICIT-{abs(hash(query))}",
                text=query,
            ),
            # This customer owns full comprehensive, even when asking about
            # partial or third-party policy knowledge.
            authenticated_user_id=orchestrator_setup["cust_full"],
            authenticated_user_role="customer",
        )
    )

    assert response.status is WorkflowStatus.COMPLETED
    assert response.retrieval_result is not None
    result = response.retrieval_result["result"]
    assert result["policy_data"] is None
    assert result["knowledge_evidence"]
    assert all(
        evidence["metadata"]["policy_type"] == expected_policy_type
        for evidence in result["knowledge_evidence"]
    )
    assert expected_title in {
        evidence["source_title"] for evidence in result["knowledge_evidence"]
    }
