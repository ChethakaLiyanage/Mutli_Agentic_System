"""Repair the three existing canonical policy files without duplicating chunks.

Run from the repository root. Identity is limited to exact, reviewed filenames;
ambiguous files are reported and left unchanged.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from backend.app.policy_types import PolicyType, normalize_policy_type
from backend.app.retrieval.document_ingestion import DocumentIngestor
from backend.app.retrieval.document_repository import get_policy_document_repository
from backend.app.retrieval.knowledge_retriever import get_shared_knowledge_retriever
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.services.supabase_service import get_supabase_client


CANONICAL_FILES: dict[str, PolicyType] = {
    "full_comprehensive_motor_policy.txt": "full_comprehensive",
    "partial_comprehensive_motor_policy.txt": "partial_comprehensive",
    "third_party_motor_policy.txt": "third_party",
}


def main() -> int:
    docs_dir = Path("backend/data/policy_docs")
    doc_repo = get_policy_document_repository()
    chunk_repo = RetrievalRepository(get_supabase_client())
    client = chunk_repo.client
    ingestor = DocumentIngestor(chunk_repo)
    all_chunks = chunk_repo.list_knowledge_chunks(insurance_type="motor")
    documents_by_filename = {
        item.original_filename: item for item in doc_repo.list_documents()
    }

    failures = 0
    for filename, policy_type in CANONICAL_FILES.items():
        path = docs_dir / filename
        document = documents_by_filename.get(filename)
        if not path.is_file() or document is None:
            print(f"AMBIGUOUS_OR_MISSING|{filename}")
            failures += 1
            continue

        checksum = sha256(path.read_bytes()).hexdigest()
        identity_chunks = [
            chunk
            for chunk in all_chunks
            if chunk.metadata.get("content_hash") == checksum
        ]

        if identity_chunks:
            source_ids = {chunk.source_document_id for chunk in identity_chunks}
            if len(source_ids) != 1:
                print(f"AMBIGUOUS_CHUNK_IDENTITY|{filename}|{sorted(source_ids)}")
                failures += 1
                continue
            source_id = next(iter(source_ids))
            repaired_chunks = []
            for chunk in identity_chunks:
                metadata = dict(chunk.metadata)
                metadata.update(
                    {
                        "policy_type": policy_type,
                        "status": "active",
                        "audience": "customer",
                        "version": document.version,
                        "document_id": document.id,
                        "root_document_id": document.root_document_id,
                    }
                )
                repaired_chunks.append(
                    chunk.model_copy(
                        update={
                            "document_type": "policy_document",
                            "metadata": metadata,
                        }
                    )
                )
            chunk_repo.replace_knowledge_chunks(source_id, repaired_chunks)
            chunk_count = len(repaired_chunks)
            action = "linked_existing_chunks"
        else:
            result = ingestor.ingest_file(
                path,
                document_type="policy_document",
                source_document_id=document.id,
                source_title=document.title,
                policy_type=policy_type,
                metadata={
                    "status": "active",
                    "audience": "customer",
                    "version": document.version,
                    "document_id": document.id,
                    "root_document_id": document.root_document_id,
                },
            )
            source_id = result.source_document_id
            chunk_count = len(
                chunk_repo.get_knowledge_chunks_by_source(source_id)
            )
            action = "ingested_existing_file"

        metadata = dict(document.metadata)
        metadata["linked_source_document_id"] = source_id
        doc_repo.update_document(
            document.id,
            {
                "document_type": "policy_document",
                "policy_type": policy_type,
                "audience": "customer",
                "status": "active",
                "checksum": checksum,
                "chunks_count": chunk_count,
                "metadata": metadata,
            },
        )
        print(
            f"REPAIRED|{policy_type}|{document.id}|{document.title}|"
            f"{document.version}|{chunk_count}|{action}"
        )

    retriever = get_shared_knowledge_retriever(repository=chunk_repo)
    indexed_count = retriever.refresh()
    print(f"ACTIVE_INDEX_CHUNKS|{indexed_count}")
    for policy_type in CANONICAL_FILES.values():
        print(
            f"POLICY_SCOPE|{policy_type}|"
            f"{retriever.has_eligible_policy_chunks(policy_type)}"
        )

    # Older deployments may not yet have the policy_type column. Preserve the
    # actual assignment and add its canonical equivalent to metadata, which is
    # the repository's supported compatibility boundary.
    assignment_repairs = 0
    policies = client.table("policies").select(
        "policy_id,coverage_type,metadata"
    ).execute().data or []
    for policy in policies:
        metadata = dict(policy.get("metadata") or {})
        canonical = normalize_policy_type(
            metadata.get("policy_type") or policy.get("coverage_type")
        )
        if canonical is None or metadata.get("policy_type") == canonical:
            continue
        metadata["policy_type"] = canonical
        client.table("policies").update({"metadata": metadata}).eq(
            "policy_id", policy["policy_id"]
        ).execute()
        assignment_repairs += 1
    print(f"CANONICAL_ASSIGNMENTS_REPAIRED|{assignment_repairs}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
