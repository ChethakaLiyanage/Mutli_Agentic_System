"""Policy and Knowledge Document repository and bootstrap management."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PolicyDocument(BaseModel):
    """Authoritative metadata record for a controlled policy/knowledge document version."""

    id: str
    root_document_id: str
    title: str
    document_type: str
    policy_type: str | None = None
    audience: str = "customer"
    version: str = "1.0"
    original_filename: str
    storage_path: str | None = None
    checksum: str | None = None
    status: str = "active"  # processing, active, superseded, failed, archived
    chunks_count: int = 0
    previous_version_id: str | None = None
    change_summary: str | None = None
    uploaded_by: str = "admin"
    created_at: str = Field(default_factory=_utc_now_iso)
    activated_at: str | None = None
    superseded_at: str | None = None
    updated_at: str = Field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class PolicyDocumentRepository(Protocol):
    """Protocol for durable storage and retrieval of policy documents."""

    def list_documents(
        self,
        *,
        status: str | None = None,
        policy_type: str | None = None,
        document_type: str | None = None,
        audience: str | None = None,
        root_only: bool = False,
    ) -> list[PolicyDocument]: ...

    def get_document_by_id(self, document_id: str) -> PolicyDocument | None: ...

    def get_active_by_root_id(self, root_document_id: str) -> PolicyDocument | None: ...

    def get_versions_for_root(self, root_document_id: str) -> list[PolicyDocument]: ...

    def create_document(self, document: PolicyDocument) -> PolicyDocument: ...

    def update_document(
        self, document_id: str, updates: dict[str, Any]
    ) -> PolicyDocument: ...

    def mark_superseded(
        self, document_id: str, *, superseded_by_id: str | None = None
    ) -> PolicyDocument | None: ...


class InMemoryPolicyDocumentRepository:
    """Thread-safe in-memory policy document store for testing and fallback."""

    def __init__(self, initial_documents: list[PolicyDocument] | None = None) -> None:
        self._documents: dict[str, PolicyDocument] = {
            doc.id: doc for doc in (initial_documents or [])
        }

    def list_documents(
        self,
        *,
        status: str | None = None,
        policy_type: str | None = None,
        document_type: str | None = None,
        audience: str | None = None,
        root_only: bool = False,
    ) -> list[PolicyDocument]:
        docs = list(self._documents.values())
        if status is not None:
            docs = [d for d in docs if d.status == status]
        if policy_type is not None:
            docs = [d for d in docs if d.policy_type == policy_type]
        if document_type is not None:
            docs = [d for d in docs if d.document_type == document_type]
        if audience is not None:
            docs = [d for d in docs if d.audience == audience]

        if root_only:
            # Group by root_document_id and pick the latest active or highest version
            roots: dict[str, PolicyDocument] = {}
            for d in sorted(docs, key=lambda x: (x.status == "active", x.created_at), reverse=True):
                if d.root_document_id not in roots:
                    roots[d.root_document_id] = d
            return list(roots.values())

        return sorted(docs, key=lambda x: x.created_at, reverse=True)

    def get_document_by_id(self, document_id: str) -> PolicyDocument | None:
        return self._documents.get(document_id)

    def get_active_by_root_id(self, root_document_id: str) -> PolicyDocument | None:
        for doc in self._documents.values():
            if doc.root_document_id == root_document_id and doc.status == "active":
                return doc
        return None

    def get_versions_for_root(self, root_document_id: str) -> list[PolicyDocument]:
        matches = [
            doc for doc in self._documents.values()
            if doc.root_document_id == root_document_id
        ]
        return sorted(matches, key=lambda x: x.created_at, reverse=True)

    def create_document(self, document: PolicyDocument) -> PolicyDocument:
        self._documents[document.id] = document
        return document

    def update_document(
        self, document_id: str, updates: dict[str, Any]
    ) -> PolicyDocument:
        current = self._documents.get(document_id)
        if not current:
            raise KeyError(f"Document {document_id} not found")
        dumped = current.model_dump()
        dumped.update(updates)
        dumped["updated_at"] = _utc_now_iso()
        updated = PolicyDocument.model_validate(dumped)
        self._documents[document_id] = updated
        return updated

    def mark_superseded(
        self, document_id: str, *, superseded_by_id: str | None = None
    ) -> PolicyDocument | None:
        current = self._documents.get(document_id)
        if not current:
            return None
        now_iso = _utc_now_iso()
        dumped = current.model_dump()
        dumped["status"] = "superseded"
        dumped["superseded_at"] = now_iso
        dumped["updated_at"] = now_iso
        if superseded_by_id:
            meta = dict(dumped.get("metadata") or {})
            meta["superseded_by_id"] = superseded_by_id
            dumped["metadata"] = meta
        updated = PolicyDocument.model_validate(dumped)
        self._documents[document_id] = updated
        return updated


class SupabasePolicyDocumentRepository:
    """Production Supabase repository for policy documents with local file fallback."""

    def __init__(
        self,
        client: Any,
        fallback_file: Path | None = None,
    ) -> None:
        self._client = client
        self._fallback_path = fallback_file or Path("backend/data/policy_documents.json")
        self._fallback_repo = InMemoryPolicyDocumentRepository()
        self._table_available: bool | None = None
        self._load_fallback_from_disk()

    def _load_fallback_from_disk(self) -> None:
        if self._fallback_path.is_file():
            try:
                raw = json.loads(self._fallback_path.read_text(encoding="utf-8"))
                for item in raw:
                    doc = PolicyDocument.model_validate(item)
                    self._fallback_repo.create_document(doc)
            except Exception as e:
                logger.warning("Could not read policy documents fallback file: %s", e)

    def _persist_fallback_to_disk(self) -> None:
        try:
            self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
            all_docs = [
                d.model_dump(mode="json")
                for d in self._fallback_repo.list_documents()
            ]
            self._fallback_path.write_text(
                json.dumps(all_docs, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Failed writing policy documents fallback to disk: %s", e)

    def _check_table(self) -> bool:
        if self._table_available is not None:
            return self._table_available
        try:
            self._client.table("policy_documents").select("id").limit(1).execute()
            self._table_available = True
        except Exception as e:
            logger.info("policy_documents table not yet ready in Supabase (%s), using local fallback store", e)
            self._table_available = False
        return self._table_available

    def list_documents(
        self,
        *,
        status: str | None = None,
        policy_type: str | None = None,
        document_type: str | None = None,
        audience: str | None = None,
        root_only: bool = False,
    ) -> list[PolicyDocument]:
        if not self._check_table():
            return self._fallback_repo.list_documents(
                status=status,
                policy_type=policy_type,
                document_type=document_type,
                audience=audience,
                root_only=root_only,
            )
        try:
            query = self._client.table("policy_documents").select("*")
            if status is not None:
                query = query.eq("status", status)
            if policy_type is not None:
                query = query.eq("policy_type", policy_type)
            if document_type is not None:
                query = query.eq("document_type", document_type)
            if audience is not None:
                query = query.eq("audience", audience)
            res = query.order("created_at", desc=True).execute()
            docs = [PolicyDocument.model_validate(row) for row in (res.data or [])]
            if root_only:
                roots: dict[str, PolicyDocument] = {}
                for d in sorted(docs, key=lambda x: (x.status == "active", x.created_at), reverse=True):
                    if d.root_document_id not in roots:
                        roots[d.root_document_id] = d
                return list(roots.values())
            return docs
        except Exception as e:
            logger.warning("Supabase list_documents failed: %s; using fallback", e)
            return self._fallback_repo.list_documents(
                status=status,
                policy_type=policy_type,
                document_type=document_type,
                audience=audience,
                root_only=root_only,
            )

    def get_document_by_id(self, document_id: str) -> PolicyDocument | None:
        if not self._check_table():
            return self._fallback_repo.get_document_by_id(document_id)
        try:
            res = (
                self._client.table("policy_documents")
                .select("*")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return PolicyDocument.model_validate(res.data[0])
            return self._fallback_repo.get_document_by_id(document_id)
        except Exception:
            return self._fallback_repo.get_document_by_id(document_id)

    def get_active_by_root_id(self, root_document_id: str) -> PolicyDocument | None:
        if not self._check_table():
            return self._fallback_repo.get_active_by_root_id(root_document_id)
        try:
            res = (
                self._client.table("policy_documents")
                .select("*")
                .eq("root_document_id", root_document_id)
                .eq("status", "active")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                return PolicyDocument.model_validate(res.data[0])
            return self._fallback_repo.get_active_by_root_id(root_document_id)
        except Exception:
            return self._fallback_repo.get_active_by_root_id(root_document_id)

    def get_versions_for_root(self, root_document_id: str) -> list[PolicyDocument]:
        if not self._check_table():
            return self._fallback_repo.get_versions_for_root(root_document_id)
        try:
            res = (
                self._client.table("policy_documents")
                .select("*")
                .eq("root_document_id", root_document_id)
                .order("created_at", desc=True)
                .execute()
            )
            if res.data:
                return [PolicyDocument.model_validate(row) for row in res.data]
            return self._fallback_repo.get_versions_for_root(root_document_id)
        except Exception:
            return self._fallback_repo.get_versions_for_root(root_document_id)

    def create_document(self, document: PolicyDocument) -> PolicyDocument:
        # Update fallback store first
        self._fallback_repo.create_document(document)
        self._persist_fallback_to_disk()
        if self._check_table():
            try:
                row = document.model_dump(mode="json")
                self._client.table("policy_documents").insert(row).execute()
            except Exception as e:
                logger.warning("Supabase insert policy_documents failed: %s; preserved locally", e)
        return document

    def update_document(
        self, document_id: str, updates: dict[str, Any]
    ) -> PolicyDocument:
        updated = self._fallback_repo.update_document(document_id, updates)
        self._persist_fallback_to_disk()
        if self._check_table():
            try:
                payload = dict(updates)
                payload["updated_at"] = _utc_now_iso()
                self._client.table("policy_documents").update(payload).eq("id", document_id).execute()
            except Exception as e:
                logger.warning("Supabase update policy_documents failed: %s; preserved locally", e)
        return updated

    def mark_superseded(
        self, document_id: str, *, superseded_by_id: str | None = None
    ) -> PolicyDocument | None:
        updated = self._fallback_repo.mark_superseded(
            document_id, superseded_by_id=superseded_by_id
        )
        self._persist_fallback_to_disk()
        if self._check_table() and updated:
            try:
                payload = {
                    "status": "superseded",
                    "superseded_at": updated.superseded_at,
                    "updated_at": updated.updated_at,
                    "metadata": updated.metadata,
                }
                self._client.table("policy_documents").update(payload).eq("id", document_id).execute()
            except Exception as e:
                logger.warning("Supabase mark_superseded failed: %s; preserved locally", e)
        return updated


_global_doc_repo: PolicyDocumentRepository | None = None


def get_policy_document_repository() -> PolicyDocumentRepository:
    """Singleton accessor for policy document repository."""
    global _global_doc_repo
    if _global_doc_repo is None:
        from backend.app.config import get_settings
        from backend.app.services.supabase_service import get_supabase_client

        settings = get_settings()
        if settings.persistence_backend == "supabase":
            try:
                client = get_supabase_client(settings)
                _global_doc_repo = SupabasePolicyDocumentRepository(client)
            except Exception as e:
                logger.warning("Failed to connect Supabase for PolicyDocumentRepository: %s", e)
                _global_doc_repo = InMemoryPolicyDocumentRepository()
        else:
            _global_doc_repo = InMemoryPolicyDocumentRepository()
    return _global_doc_repo


def _format_clean_title(filename_stem: str) -> str:
    """Convert filename like 'synthetic_claim_reporting_timelines' to 'Claim Reporting Timelines'."""
    clean = filename_stem
    if clean.startswith("synthetic_"):
        clean = clean[len("synthetic_"):]
    words = [w.capitalize() for w in clean.replace("_", " ").replace("-", " ").split()]
    return " ".join(words)


def bootstrap_existing_documents(
    doc_repo: PolicyDocumentRepository,
    policy_docs_dir: Path | str | None = None,
    chunk_repo: Any | None = None,
) -> list[PolicyDocument]:
    """Scan existing policy documents and ensure document records exist without duplicating chunks."""
    base_dir = Path(policy_docs_dir or "backend/data/policy_docs")
    if not base_dir.is_dir():
        logger.warning("Policy documents directory does not exist: %s", base_dir)
        return []

    existing_docs = {d.original_filename: d for d in doc_repo.list_documents()}
    existing_by_stem = {Path(d.original_filename).stem: d for d in existing_docs.values()}

    registered: list[PolicyDocument] = []
    for file_path in sorted(base_dir.iterdir()):
        if not file_path.is_file() or file_path.suffix.lower() not in {".txt", ".pdf", ".docx"}:
            continue

        filename = file_path.name
        stem = file_path.stem

        if filename in existing_docs or stem in existing_by_stem:
            continue

        raw_bytes = file_path.read_bytes()
        checksum = sha256(raw_bytes).hexdigest()

        # Deduce policy_type
        lowered = stem.lower()
        policy_type: str | None = None
        if "full_comprehensive" in lowered:
            policy_type = "full_comprehensive"
        elif "partial_comprehensive" in lowered:
            policy_type = "partial_comprehensive"
        elif "third_party" in lowered:
            policy_type = "third_party"

        # Deduce audience
        audience = "internal" if "internal" in lowered or "review_guide" in lowered else "customer"

        # Deduce document_type
        if policy_type is not None or "policy" in lowered:
            document_type = "policy_document"
        elif "procedure" in lowered or "process" in lowered or "steps" in lowered:
            document_type = "procedure_guide"
        elif "guide" in lowered or "guidelines" in lowered or "checklist" in lowered:
            document_type = "guideline"
        else:
            document_type = "policy_manual"

        title = _format_clean_title(stem)
        root_id = "doc-" + sha256(f"{document_type}:{stem.lower()}".encode()).hexdigest()[:24]

        # Query chunk count if chunk_repo available
        chunks_count = 0
        if chunk_repo and hasattr(chunk_repo, "get_knowledge_chunks_by_source"):
            try:
                matched_chunks = chunk_repo.get_knowledge_chunks_by_source(root_id)
                chunks_count = len(matched_chunks)
            except Exception:
                chunks_count = 0

        doc_record = PolicyDocument(
            id=root_id,
            root_document_id=root_id,
            title=title,
            document_type=document_type,
            policy_type=policy_type,
            audience=audience,
            version="1.0",
            original_filename=filename,
            storage_path=str(file_path),
            checksum=checksum,
            status="active",
            chunks_count=chunks_count,
            uploaded_by="system",
            activated_at=_utc_now_iso(),
            metadata={"initial_corpus": True},
        )
        created = doc_repo.create_document(doc_record)
        registered.append(created)

    return registered
