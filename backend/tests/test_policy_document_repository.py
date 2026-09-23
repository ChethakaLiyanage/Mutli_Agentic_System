"""Tests for PolicyDocument domain models, repository, and existing document bootstrap."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.retrieval.document_repository import (
    InMemoryPolicyDocumentRepository,
    PolicyDocument,
    bootstrap_existing_documents,
)


def test_in_memory_policy_document_crud():
    repo = InMemoryPolicyDocumentRepository()

    doc = PolicyDocument(
        id="doc-test-1",
        root_document_id="doc-test-1",
        title="Collision Claims Procedure",
        document_type="procedure_guide",
        policy_type=None,
        audience="customer",
        version="1.0",
        original_filename="collision_claims_procedure.txt",
        status="active",
        chunks_count=4,
    )

    created = repo.create_document(doc)
    assert created.id == "doc-test-1"

    # List
    docs = repo.list_documents()
    assert len(docs) == 1
    assert docs[0].title == "Collision Claims Procedure"

    # Get by ID and active root
    assert repo.get_document_by_id("doc-test-1") is not None
    assert repo.get_active_by_root_id("doc-test-1") is not None

    # Mark superseded
    superseded = repo.mark_superseded("doc-test-1", superseded_by_id="doc-test-2")
    assert superseded is not None
    assert superseded.status == "superseded"
    assert superseded.superseded_at is not None
    assert repo.get_active_by_root_id("doc-test-1") is None

    # Add V2
    doc_v2 = PolicyDocument(
        id="doc-test-2",
        root_document_id="doc-test-1",
        title="Collision Claims Procedure",
        document_type="procedure_guide",
        policy_type=None,
        audience="customer",
        version="2.0",
        original_filename="collision_claims_procedure_v2.txt",
        status="active",
        chunks_count=5,
        previous_version_id="doc-test-1",
    )
    repo.create_document(doc_v2)

    versions = repo.get_versions_for_root("doc-test-1")
    assert len(versions) == 2
    version_numbers = [v.version for v in versions]
    assert "1.0" in version_numbers and "2.0" in version_numbers

    # Root-only listing returns only the active one
    roots = repo.list_documents(root_only=True)
    assert len(roots) == 1
    assert roots[0].version == "2.0"
    assert roots[0].status == "active"


def test_bootstrap_existing_documents():
    repo = InMemoryPolicyDocumentRepository()

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "full_comprehensive_motor_policy.txt").write_text(
            "Full comprehensive terms and conditions.", encoding="utf-8"
        )
        (tmp_path / "claims_reporting_deadlines.txt").write_text(
            "Report claims within required deadlines.", encoding="utf-8"
        )
        (tmp_path / "internal_claims_review_guide.txt").write_text(
            "Internal claim assessment guide for officers.", encoding="utf-8"
        )

        bootstrapped = bootstrap_existing_documents(repo, policy_docs_dir=tmp_path)
        assert len(bootstrapped) == 3

        docs = repo.list_documents()
        assert len(docs) == 3

        # Verify inferred attributes
        full_doc = next(d for d in docs if "full_comprehensive" in d.original_filename)
        assert full_doc.policy_type == "full_comprehensive"
        assert full_doc.audience == "customer"
        assert full_doc.status == "active"
        assert full_doc.version == "1.0"

        internal_doc = next(d for d in docs if "internal" in d.original_filename)
        assert internal_doc.audience == "internal"

        # Verify idempotence: second run bootstraps 0
        second_run = bootstrap_existing_documents(repo, policy_docs_dir=tmp_path)
        assert len(second_run) == 0
        assert len(repo.list_documents()) == 3
