"""End-to-end integration tests for Admin Policy Document Management, atomic replacement, and live TF-IDF refresh."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.retrieval.document_ingestion import DocumentIngestor
from backend.app.retrieval.document_repository import (
    InMemoryPolicyDocumentRepository,
    PolicyDocument,
    get_policy_document_repository,
)
from backend.app.retrieval.knowledge_retriever import (
    KnowledgeRetriever,
    get_shared_knowledge_retriever,
    set_shared_knowledge_retriever,
)
from backend.app.retrieval.schemas import KnowledgeChunk
from backend.app.security.dependencies import (
    get_current_admin,
    get_current_user,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.roles import UserRole


class MemoryChunkRepository:
    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self.chunks = list(chunks or [])

    def list_knowledge_chunks(self, *, insurance_type: str = "motor", document_type=None):
        return [c for c in self.chunks if c.insurance_type == insurance_type]

    def get_knowledge_chunks_by_source(self, source_document_id: str):
        return [c for c in self.chunks if c.source_document_id == source_document_id]

    def upsert_knowledge_chunks(self, chunks: list[KnowledgeChunk]):
        chunk_map = {c.chunk_id: c for c in self.chunks}
        for item in chunks:
            chunk_map[item.chunk_id] = item
        self.chunks = list(chunk_map.values())
        return chunks

    def replace_knowledge_chunks(self, source_document_id: str, chunks: list[KnowledgeChunk]):
        self.chunks = [c for c in self.chunks if c.source_document_id != source_document_id]
        self.chunks.extend(chunks)
        return chunks

    def mark_chunks_status_for_source(self, source_document_id: str, status: str):
        count = 0
        for c in self.chunks:
            if c.source_document_id == source_document_id:
                c.metadata["status"] = status
                count += 1
        return count


from datetime import datetime, timezone


@pytest.fixture
def mock_admin_user():
    return AuthenticatedUser(
        user_id="USR-ADMIN-100",
        email="admin@example.com",
        role=UserRole.ADMIN,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_customer_user():
    return AuthenticatedUser(
        user_id="USR-CUST-100",
        email="customer@example.com",
        role=UserRole.CUSTOMER,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def isolated_document_env(mock_admin_user):
    test_doc_repo = InMemoryPolicyDocumentRepository()
    test_chunk_repo = MemoryChunkRepository()
    test_retriever = KnowledgeRetriever(repository=test_chunk_repo)
    set_shared_knowledge_retriever(test_retriever)

    # Dependency overrides
    app.dependency_overrides[get_policy_document_repository] = lambda: test_doc_repo
    app.dependency_overrides[get_current_admin] = lambda: mock_admin_user

    from backend.app.api import admin_documents
    orig_get_chunk = admin_documents._get_chunk_repository
    admin_documents._get_chunk_repository = lambda: test_chunk_repo

    client = TestClient(app)

    yield {
        "client": client,
        "doc_repo": test_doc_repo,
        "chunk_repo": test_chunk_repo,
        "retriever": test_retriever,
    }

    # Teardown
    app.dependency_overrides.clear()
    admin_documents._get_chunk_repository = orig_get_chunk
    set_shared_knowledge_retriever(None)


def test_admin_lists_and_views_documents(isolated_document_env):
    client = isolated_document_env["client"]
    doc_repo = isolated_document_env["doc_repo"]

    # Seed an active document
    doc = PolicyDocument(
        id="doc-procedure-01",
        root_document_id="doc-procedure-01",
        title="Motor Claims Procedure Guide",
        document_type="procedure_guide",
        policy_type=None,
        audience="customer",
        version="1.0",
        original_filename="motor_claims_procedure.txt",
        status="active",
        chunks_count=3,
    )
    doc_repo.create_document(doc)

    # List documents
    res = client.get("/admin/policy-documents")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["documents"][0]["title"] == "Motor Claims Procedure Guide"

    # View document detail
    detail_res = client.get("/admin/policy-documents/doc-procedure-01")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["document"]["id"] == "doc-procedure-01"
    assert detail["chunks_count"] == 3


def test_admin_uploads_new_document_and_immediate_retrieval(isolated_document_env):
    client = isolated_document_env["client"]
    retriever = isolated_document_env["retriever"]

    file_content = (
        "SECTION 1: EMERGENCY RESPONSE\n"
        "In the event of an emergency or roadside breakdown, contact the 24/7 hotline at 011-2345678.\n"
        "Ensure all passengers move to safety behind the road barrier immediately.\n"
    ).encode("utf-8")

    response = client.post(
        "/admin/policy-documents",
        data={
            "title": "Emergency Response and Breakdown Guide",
            "document_type": "guideline",
            "policy_type": "none",
            "audience": "customer",
            "version": "1.0",
        },
        files={"file": ("emergency_guide.txt", BytesIO(file_content), "text/plain")},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["success"] is True
    assert result["document"]["status"] == "active"
    assert result["chunks_indexed"] > 0

    # Test immediate retrieval in Agent 2 without any backend restart
    evidence = retriever.retrieve("roadside breakdown emergency hotline")
    assert len(evidence) > 0
    assert "011-2345678" in evidence[0].content


def test_atomic_replacement_scenario_alpha_to_beta(isolated_document_env):
    """The critical update test scenario:

    1. V1 has rule: 'TEST_CURRENT_RULE_ALPHA: Collision claims must be reported within 7 days.'
    2. Verify Agent 2 retrieves ALPHA.
    3. Admin replaces document with V2 containing:
       'TEST_UPDATED_RULE_BETA: Collision claims must be reported within 14 days.'
       (ALPHA is removed from V2).
    4. WITHOUT backend restart, query Agent 2.
    5. Expected: BETA retrieved. ALPHA is NOT retrieved.
    6. V1 is marked superseded; V2 is active.
    """
    client = isolated_document_env["client"]
    doc_repo = isolated_document_env["doc_repo"]
    retriever = isolated_document_env["retriever"]

    v1_content = (
        "SECTION 1: REPORTING TIMELINES\n"
        "TEST_CURRENT_RULE_ALPHA: Collision claims must be reported within 7 days of the incident date.\n"
        "Failure to report within 7 days may result in claim delay.\n"
    ).encode("utf-8")

    # 1. Upload V1
    v1_res = client.post(
        "/admin/policy-documents",
        data={
            "title": "Motor Claims Reporting Timelines",
            "document_type": "procedure_guide",
            "policy_type": "none",
            "audience": "customer",
            "version": "1.0",
        },
        files={"file": ("reporting_timelines.txt", BytesIO(v1_content), "text/plain")},
    )
    assert v1_res.status_code == 201
    v1_id = v1_res.json()["document"]["id"]

    # 2. Verify Agent 2 retrieves ALPHA
    alpha_evidence = retriever.retrieve("How many days do I have to report a collision claim?")
    assert len(alpha_evidence) > 0
    assert "TEST_CURRENT_RULE_ALPHA" in alpha_evidence[0].content
    assert "7 days" in alpha_evidence[0].content

    # 3. Admin replaces with V2 (BETA with 14 days)
    v2_content = (
        "SECTION 1: REPORTING TIMELINES\n"
        "TEST_UPDATED_RULE_BETA: Collision claims must be reported within 14 days of the incident date.\n"
        "All collision notifications must be received within the 14-day window.\n"
    ).encode("utf-8")

    v2_res = client.post(
        f"/admin/policy-documents/{v1_id}/replace",
        data={
            "version": "2.0",
            "change_summary": "Extended collision reporting window from 7 to 14 days",
        },
        files={"file": ("reporting_timelines_v2.txt", BytesIO(v2_content), "text/plain")},
    )
    assert v2_res.status_code == 200
    v2_data = v2_res.json()
    assert v2_data["success"] is True
    assert v2_data["document"]["version"] == "2.0"
    assert v2_data["document"]["status"] == "active"

    # Verify status in repository
    v1_updated = doc_repo.get_document_by_id(v1_id)
    assert v1_updated.status == "superseded"
    assert v1_updated.superseded_at is not None

    # 4 & 5. Query Agent 2 again WITHOUT restarting
    beta_evidence = retriever.retrieve("How many days do I have to report a collision claim?")
    assert len(beta_evidence) > 0

    # BETA must be retrieved
    assert "TEST_UPDATED_RULE_BETA" in beta_evidence[0].content
    assert "14 days" in beta_evidence[0].content

    # ALPHA must NEVER be returned in any current retrieved evidence
    for item in beta_evidence:
        assert "TEST_CURRENT_RULE_ALPHA" not in item.content
        assert "7 days" not in item.content


def test_failed_replacement_leaves_active_version_intact(isolated_document_env):
    client = isolated_document_env["client"]
    doc_repo = isolated_document_env["doc_repo"]
    retriever = isolated_document_env["retriever"]

    initial_content = (
        "SECTION 1: VALID PROCEDURE\n"
        "Valid active claim filing guidelines.\n"
    ).encode("utf-8")

    # Create V1
    init_res = client.post(
        "/admin/policy-documents",
        data={
            "title": "Claim Filing Guide",
            "document_type": "procedure_guide",
            "version": "1.0",
        },
        files={"file": ("filing_guide.txt", BytesIO(initial_content), "text/plain")},
    )
    v1_id = init_res.json()["document"]["id"]

    # Attempt replace with empty or unsupported format
    empty_res = client.post(
        f"/admin/policy-documents/{v1_id}/replace",
        data={"version": "2.0"},
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )
    assert empty_res.status_code == 400

    # V1 must remain active
    v1_current = doc_repo.get_document_by_id(v1_id)
    assert v1_current.status == "active"

    # Index must not be corrupted
    evidence = retriever.retrieve("claim filing guidelines")
    assert len(evidence) > 0
    assert "Valid active claim filing guidelines" in evidence[0].content


def test_security_authorization_checks(mock_customer_user):
    app.dependency_overrides.clear()
    client = TestClient(app)

    # 1. Unauthenticated request -> 401 Unauthorized
    res = client.get("/admin/policy-documents")
    assert res.status_code == 401

    res_post = client.post(
        "/admin/policy-documents",
        data={"title": "Unauthorized"},
        files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert res_post.status_code == 401

    # 2. Customer authenticated user accessing admin endpoint -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: mock_customer_user
    res_customer = client.get("/admin/policy-documents")
    assert res_customer.status_code == 403

    app.dependency_overrides.clear()


def test_unsupported_file_extension_rejected(isolated_document_env):
    client = isolated_document_env["client"]

    res = client.post(
        "/admin/policy-documents",
        data={"title": "Malicious Script", "document_type": "policy_document"},
        files={"file": ("payload.exe", BytesIO(b"MZ..."), "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "Unsupported format" in res.json()["detail"]
