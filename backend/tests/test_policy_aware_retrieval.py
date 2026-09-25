"""Tests for policy-aware knowledge retrieval and cross-policy contamination prevention."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.retrieval.document_ingestion import DocumentIngestor
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.schemas import (
    IntentContext,
    KnowledgeChunk,
    PolicyLookupContext,
    PolicyRecord,
    RetrievalRequest,
    UserContext,
)
from backend.app.retrieval.service import RetrievalService


class MemoryRetrievalRepository:
    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self.chunks: list[KnowledgeChunk] = list(chunks or [])

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
        return None

    def get_policy_by_id(self, policy_id: str, user_id: str | None = None) -> PolicyRecord | None:
        return None

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
def policy_corpus_repo() -> MemoryRetrievalRepository:
    repo = MemoryRetrievalRepository()
    ingestor = DocumentIngestor(repo)

    docs_dir = Path(__file__).resolve().parents[1] / "data" / "policy_docs"
    full_doc = docs_dir / "full_comprehensive_motor_policy.txt"
    partial_doc = docs_dir / "partial_comprehensive_motor_policy.txt"
    third_party_doc = docs_dir / "third_party_motor_policy.txt"

    ingestor.ingest_file(full_doc, document_type="policy_manual", policy_type="full_comprehensive")
    ingestor.ingest_file(partial_doc, document_type="policy_manual", policy_type="partial_comprehensive")
    ingestor.ingest_file(third_party_doc, document_type="policy_manual", policy_type="third_party")

    return repo


def test_ingestion_tags_chunks_with_correct_policy_type(policy_corpus_repo: MemoryRetrievalRepository) -> None:
    chunks = policy_corpus_repo.chunks
    assert len(chunks) > 0

    full_chunks = [c for c in chunks if c.metadata.get("policy_type") == "full_comprehensive"]
    partial_chunks = [c for c in chunks if c.metadata.get("policy_type") == "partial_comprehensive"]
    third_party_chunks = [c for c in chunks if c.metadata.get("policy_type") == "third_party"]

    assert len(full_chunks) >= 3
    assert len(partial_chunks) >= 3
    assert len(third_party_chunks) >= 3


def test_third_party_retrieval_never_returns_comprehensive_chunks(
    policy_corpus_repo: MemoryRetrievalRepository,
) -> None:
    retriever = KnowledgeRetriever(repository=policy_corpus_repo)

    # Customer asks about collision coverage under a third-party policy
    results = retriever.retrieve(
        query="Am I covered for accidental collision damage to my vehicle?",
        policy_type="third_party",
        top_k=5,
        min_relevance_score=0.1,
    )

    assert len(results) > 0
    for evidence in results:
        # Strictly verify zero cross-policy contamination
        assert evidence.metadata.get("policy_type") == "third_party", (
            f"Cross-policy leak detected! Found chunk with policy_type={evidence.metadata.get('policy_type')}"
        )
        assert "full comprehensive" not in evidence.source_title.lower()
        assert "partial comprehensive" not in evidence.source_title.lower()

    # Verify that the retrieved evidence explains own-vehicle exclusions
    combined = " ".join(e.content.lower() for e in results)
    assert "not covered" in combined or "exclusion" in combined or "third party" in combined


def test_partial_comprehensive_retrieval_excludes_collision_coverage(
    policy_corpus_repo: MemoryRetrievalRepository,
) -> None:
    retriever = KnowledgeRetriever(repository=policy_corpus_repo)

    results = retriever.retrieve(
        query="Does my policy cover accidental vehicle collision damage?",
        policy_type="partial_comprehensive",
        top_k=5,
        min_relevance_score=0.1,
    )

    assert len(results) > 0
    for evidence in results:
        assert evidence.metadata.get("policy_type") == "partial_comprehensive"

    combined = " ".join(e.content.lower() for e in results)
    # Partial comprehensive document explicitly states collision is excluded
    assert "collision" in combined
    assert "exclusion" in combined or "not covered" in combined or "excluded" in combined


def test_full_comprehensive_retrieval_returns_all_perils(
    policy_corpus_repo: MemoryRetrievalRepository,
) -> None:
    retriever = KnowledgeRetriever(repository=policy_corpus_repo)

    results = retriever.retrieve(
        query="Am I covered for collision, fire, theft, and flood?",
        policy_type="full_comprehensive",
        top_k=5,
        min_relevance_score=0.1,
    )

    assert len(results) > 0
    for evidence in results:
        assert evidence.metadata.get("policy_type") == "full_comprehensive"

    combined = " ".join(e.content.lower() for e in results)
    assert "collision" in combined or "fire" in combined or "comprehensive" in combined


def test_retrieval_service_respects_policy_lookup_context(
    policy_corpus_repo: MemoryRetrievalRepository,
) -> None:
    retriever = KnowledgeRetriever(repository=policy_corpus_repo)
    service = RetrievalService(repository=policy_corpus_repo, knowledge_retriever=retriever)

    # Retrieval request with policy context for a third_party policyholder
    request = RetrievalRequest(
        request_id="REQ-TEST-TP",
        query="What is my coverage?",
        user_context=UserContext(user_id="USR-TP-1"),
        intent_context=IntentContext(intent="coverage_question"),
        policy_context=PolicyLookupContext(
            policy_number="POL-12345",
            policy_type="third_party",
        ),
    )

    response = service.retrieve(request)
    assert response.status == "success"
    assert len(response.result.knowledge_evidence) > 0

    for ev in response.result.knowledge_evidence:
        assert ev.metadata.get("policy_type") == "third_party"


def test_policy_retrieval_distinguishes_missing_active_document() -> None:
    repo = MemoryRetrievalRepository()
    service = RetrievalService(
        repository=repo,
        knowledge_retriever=KnowledgeRetriever(repository=repo),
    )
    response = service.retrieve(
        RetrievalRequest(
            request_id="REQ-NO-ACTIVE-DOC",
            query="What is my policy coverage?",
            user_context=UserContext(user_id="USR-1"),
            intent_context=IntentContext(intent="coverage_question"),
            policy_context=PolicyLookupContext(
                policy_number="POL-1",
                policy_type="full_comprehensive",
            ),
        )
    )

    assert "matching_active_policy_document_not_found" in response.result.missing_evidence
    assert response.result.knowledge_evidence == []


def test_explicit_category_missing_document_is_not_described_as_own_policy() -> None:
    repo = MemoryRetrievalRepository()
    service = RetrievalService(
        repository=repo,
        knowledge_retriever=KnowledgeRetriever(repository=repo),
    )
    response = service.retrieve(
        RetrievalRequest(
            request_id="REQ-NO-EXPLICIT-DOC",
            query="Tell me about third party policy",
            user_context=UserContext(user_id="USR-1"),
            intent_context=IntentContext(intent="policy_question"),
            policy_context=PolicyLookupContext(policy_type="third_party"),
        )
    )

    assert "requested_policy_document_not_found" in response.result.missing_evidence
    assert "matching_active_policy_document_not_found" not in response.result.missing_evidence


def test_policy_retrieval_distinguishes_active_document_without_relevant_evidence(
    policy_corpus_repo: MemoryRetrievalRepository,
) -> None:
    service = RetrievalService(
        repository=policy_corpus_repo,
        knowledge_retriever=KnowledgeRetriever(repository=policy_corpus_repo),
    )
    response = service.retrieve(
        RetrievalRequest(
            request_id="REQ-NO-RELEVANT-EVIDENCE",
            query="quantum spacecraft propulsion",
            user_context=UserContext(user_id="USR-1"),
            intent_context=IntentContext(intent="coverage_question"),
            policy_context=PolicyLookupContext(
                policy_number="POL-1",
                policy_type="full_comprehensive",
            ),
        )
    )

    assert "relevant_policy_evidence_not_found" in response.result.missing_evidence
    assert "matching_active_policy_document_not_found" not in response.result.missing_evidence
    assert response.result.knowledge_evidence == []
