"""Tests for policy-specific customer retrieval isolation and audience boundaries."""

import pytest
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.schemas import KnowledgeChunk


class MemoryKnowledgeRepo:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks

    def list_knowledge_chunks(self, *, insurance_type: str = "motor", document_type=None):
        return [c for c in self.chunks if c.insurance_type == insurance_type]


@pytest.fixture
def multi_policy_corpus():
    chunks = [
        # Full Comprehensive chunk
        KnowledgeChunk(
            chunk_id="chk-full-01",
            source_document_id="doc-full-comp",
            source_title="Full Comprehensive Motor Policy",
            document_type="policy_document",
            content=(
                "FULL COMPREHENSIVE COVERAGE: Under this policy, own-vehicle damage from fire, "
                "theft, flood, vandalism, and accidental collision is fully covered. "
                "The insurer covers all repairs up to the agreed vehicle market value."
            ),
            normalized_content=(
                "full comprehensive coverage under this policy own vehicle damage from fire "
                "theft flood vandalism and accidental collision is fully covered"
            ),
            metadata={"policy_type": "full_comprehensive", "audience": "customer", "status": "active"},
        ),
        # Partial Comprehensive chunk
        KnowledgeChunk(
            chunk_id="chk-part-01",
            source_document_id="doc-part-comp",
            source_title="Partial Comprehensive Motor Policy",
            document_type="policy_document",
            content=(
                "PARTIAL COMPREHENSIVE COVERAGE: Covers fire, theft, flood, and windscreen. "
                "EXCLUSION: Accidental collision damage to your own vehicle is strictly excluded. "
                "Third-party liability is covered."
            ),
            normalized_content=(
                "partial comprehensive coverage covers fire theft flood and windscreen "
                "exclusion accidental collision damage to your own vehicle is strictly excluded"
            ),
            metadata={"policy_type": "partial_comprehensive", "audience": "customer", "status": "active"},
        ),
        # Third Party chunk
        KnowledgeChunk(
            chunk_id="chk-third-01",
            source_document_id="doc-third-party",
            source_title="Third Party Motor Policy",
            document_type="policy_document",
            content=(
                "THIRD PARTY ONLY POLICY: Provides cover solely for third-party bodily injury "
                "and third-party property damage. EXCLUSION: All damage to your own vehicle, "
                "including fire, theft, collision, and flood, is strictly excluded."
            ),
            normalized_content=(
                "third party only policy provides cover solely for third party bodily injury "
                "and third party property damage exclusion all damage to your own vehicle "
                "including fire theft collision and flood is strictly excluded"
            ),
            metadata={"policy_type": "third_party", "audience": "customer", "status": "active"},
        ),
        # Internal-only claims guide chunk
        KnowledgeChunk(
            chunk_id="chk-internal-01",
            source_document_id="doc-internal-manual",
            source_title="Internal Claims Officer Fraud Manual",
            document_type="policy_manual",
            content=(
                "INTERNAL CLAIMS MANUAL: Check for high risk indicators such as recent policy inception, "
                "staged collision patterns, and discrepancies in police report references."
            ),
            normalized_content=(
                "internal claims manual check for high risk indicators such as recent policy inception "
                "staged collision patterns and discrepancies in police report references"
            ),
            metadata={"audience": "internal", "status": "active"},
        ),
    ]
    return chunks


def test_third_party_customer_retrieval_isolation(multi_policy_corpus):
    retriever = KnowledgeRetriever(repository=MemoryKnowledgeRepo(multi_policy_corpus))
    retriever.refresh()

    # Third party customer asks about fire damage
    evidence = retriever.retrieve(
        "Does my policy cover fire damage to my own car?",
        policy_type="third_party",
        audience="customer",
    )

    assert len(evidence) > 0
    # Must retrieve Third Party document with exclusion
    assert evidence[0].metadata["source_document_id"] == "doc-third-party"
    assert "strictly excluded" in evidence[0].content

    # Must NOT retrieve Full Comprehensive chunk
    source_ids = [e.metadata["source_document_id"] for e in evidence]
    assert "doc-full-comp" not in source_ids


def test_full_comprehensive_customer_retrieval_isolation(multi_policy_corpus):
    retriever = KnowledgeRetriever(repository=MemoryKnowledgeRepo(multi_policy_corpus))
    retriever.refresh()

    evidence = retriever.retrieve(
        "Does my policy cover accidental collision damage to my vehicle?",
        policy_type="full_comprehensive",
        audience="customer",
    )

    assert len(evidence) > 0
    assert evidence[0].metadata["source_document_id"] == "doc-full-comp"
    assert "fully covered" in evidence[0].content

    source_ids = [e.metadata["source_document_id"] for e in evidence]
    assert "doc-part-comp" not in source_ids
    assert "doc-third-party" not in source_ids


def test_partial_comprehensive_customer_retrieval_isolation(multi_policy_corpus):
    retriever = KnowledgeRetriever(repository=MemoryKnowledgeRepo(multi_policy_corpus))
    retriever.refresh()

    evidence = retriever.retrieve(
        "Does my policy cover collision damage?",
        policy_type="partial_comprehensive",
        audience="customer",
    )

    assert len(evidence) > 0
    assert evidence[0].metadata["source_document_id"] == "doc-part-comp"
    assert "collision damage to your own vehicle is strictly excluded" in evidence[0].content


def test_customer_cannot_retrieve_internal_documents(multi_policy_corpus):
    retriever = KnowledgeRetriever(repository=MemoryKnowledgeRepo(multi_policy_corpus))
    retriever.refresh()

    # Customer queries about fraud indicators
    evidence = retriever.retrieve(
        "What are high risk indicators for claims?",
        audience="customer",
        allow_internal=False,
    )

    # Internal manual must never be returned to customer
    source_ids = [e.metadata["source_document_id"] for e in evidence]
    assert "doc-internal-manual" not in source_ids
