"""Document upload, validation, and metadata persistence service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from fastapi import UploadFile

from backend.app.config import get_settings
from backend.app.schemas.domain import DocumentType
from backend.app.services.supabase_service import get_supabase_client

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/jpg",
}

DOCUMENT_TYPE_MAP = {
    "police_report": DocumentType.POLICE_REPORT,
    "repair_estimate": DocumentType.REPAIR_ESTIMATE,
    "claim_form": DocumentType.CLAIM_FORM,
    "vehicle_registration": DocumentType.VEHICLE_REGISTRATION,
    "damage_photo": DocumentType.DAMAGE_PHOTO,
    "damage_photos": DocumentType.DAMAGE_PHOTO,
    "identity_document": DocumentType.IDENTITY_DOCUMENT,
    "driving_licence": DocumentType.IDENTITY_DOCUMENT,
    "driving_license": DocumentType.IDENTITY_DOCUMENT,
    "license": DocumentType.IDENTITY_DOCUMENT,
    "keys_information": DocumentType.OTHER,
    "information_about_keys": DocumentType.OTHER,
    "policy_document": DocumentType.POLICY_DOCUMENT,
    "invoice": DocumentType.INVOICE,
    "photo": DocumentType.PHOTO,
    "other": DocumentType.OTHER,
}


def normalize_document_type(raw_type: str | None) -> DocumentType:
    if not raw_type:
        return DocumentType.OTHER
    cleaned = Path(raw_type).stem.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = DOCUMENT_TYPE_MAP.get(cleaned)
    if normalized is not None:
        return normalized

    filename_hints = (
        ("repair_estimate", DocumentType.REPAIR_ESTIMATE),
        ("vehicle_registration", DocumentType.VEHICLE_REGISTRATION),
        ("damage_photo", DocumentType.DAMAGE_PHOTO),
        ("damage_photos", DocumentType.DAMAGE_PHOTO),
        ("police_report", DocumentType.POLICE_REPORT),
        ("driving_licence", DocumentType.IDENTITY_DOCUMENT),
        ("driving_license", DocumentType.IDENTITY_DOCUMENT),
    )
    return next(
        (document_type for hint, document_type in filename_hints if hint in cleaned),
        DocumentType.OTHER,
    )


def sanitize_filename(filename: str) -> str:
    cleaned = Path(filename).name
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", cleaned)
    return cleaned or f"document_{uuid4().hex[:8]}.pdf"


@runtime_checkable
class DocumentRepository(Protocol):
    async def save_document(self, document: dict[str, Any]) -> dict[str, Any]: ...
    async def get_documents_for_claim(self, claim_id: str, customer_id: str) -> list[dict[str, Any]]: ...
    async def get_document_by_id(self, document_id: str) -> dict[str, Any] | None: ...


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    async def save_document(self, document: dict[str, Any]) -> dict[str, Any]:
        doc_id = document["document_id"]
        self.documents[doc_id] = dict(document)
        return dict(document)

    async def get_documents_for_claim(self, claim_id: str, customer_id: str) -> list[dict[str, Any]]:
        return [
            dict(doc) for doc in self.documents.values()
            if doc.get("claim_id") == claim_id and doc.get("customer_id") == customer_id
        ]

    async def get_document_by_id(self, document_id: str) -> dict[str, Any] | None:
        doc = self.documents.get(document_id)
        return dict(doc) if doc else None


class SupabaseDocumentRepository:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client or get_supabase_client()

    async def save_document(self, document: dict[str, Any]) -> dict[str, Any]:
        payload = {key: val for key, val in document.items() if val is not None}
        response = await asyncio.to_thread(
            lambda: self._client.table("claim_documents").insert(payload).execute()
        )
        return dict(response.data[0]) if response.data else payload

    async def get_documents_for_claim(self, claim_id: str, customer_id: str) -> list[dict[str, Any]]:
        try:
            response = await asyncio.to_thread(
                lambda: self._client.table("claim_documents")
                .select("*")
                .eq("claim_id", claim_id)
                .eq("customer_id", customer_id)
                .execute()
            )
            return list(response.data or [])
        except Exception:
            return []

    async def get_document_by_id(self, document_id: str) -> dict[str, Any] | None:
        try:
            response = await asyncio.to_thread(
                lambda: self._client.table("claim_documents")
                .select("*")
                .eq("document_id", document_id)
                .execute()
            )
            if response.data:
                return dict(response.data[0])
            return None
        except Exception:
            return None


_in_memory_repo = InMemoryDocumentRepository()


def get_document_repository() -> DocumentRepository:
    settings = get_settings()
    if settings.persistence_backend == "supabase":
        return SupabaseDocumentRepository()
    return _in_memory_repo


class DocumentService:
    def __init__(self, repository: DocumentRepository | None = None) -> None:
        self.repository = repository or get_document_repository()
        self.upload_dir = Path("backend/data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_document(
        self,
        *,
        claim_id: str,
        customer_id: str,
        file: UploadFile,
        document_type_str: str | None = None,
    ) -> dict[str, Any]:
        original_name = file.filename or "uploaded_file"
        sanitized_name = sanitize_filename(original_name)
        ext = Path(sanitized_name).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
            )
        if len(content) == 0:
            raise ValueError("Uploaded file is empty")

        doc_type = normalize_document_type(document_type_str or original_name)
        doc_id = f"DOC-{uuid4().hex.upper()}"
        storage_ref = f"claims/{claim_id}/{doc_id}_{sanitized_name}"

        # Write to local storage fallback safely
        local_path = self.upload_dir / f"{doc_id}_{sanitized_name}"
        try:
            local_path.write_bytes(content)
        except Exception:
            pass

        now = datetime.now(timezone.utc).isoformat()
        document_record = {
            "document_id": doc_id,
            "claim_id": claim_id,
            "customer_id": customer_id,
            "document_type": doc_type.value,
            "file_name": sanitized_name,
            "storage_reference": storage_ref,
            "document_facts": {},
            "metadata": {
                "file_size": len(content),
                "original_filename": original_name,
                "content_type": file.content_type,
                "uploaded_at": now,
            },
            "created_at": now,
        }

        persisted = await self.repository.save_document(document_record)
        return persisted

    async def list_documents(self, claim_id: str, customer_id: str) -> list[dict[str, Any]]:
        return await self.repository.get_documents_for_claim(claim_id, customer_id)

    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        doc = await self.repository.get_document_by_id(document_id)
        if doc:
            return doc
        # Local file fallback lookup
        file_path = self.get_document_file_path(document_id)
        if file_path and file_path.is_file():
            cleaned_name = file_path.name.replace(f"{document_id}_", "", 1)
            return {
                "document_id": document_id,
                "file_name": cleaned_name,
                "document_type": "other",
                "metadata": {
                    "original_filename": cleaned_name,
                    "file_size": file_path.stat().st_size,
                },
            }
        return None

    def get_document_file_path(self, document_id: str, file_name: str | None = None) -> Path | None:
        if file_name:
            exact = self.upload_dir / f"{document_id}_{file_name}"
            if exact.exists() and exact.is_file():
                return exact
        matches = list(self.upload_dir.glob(f"{document_id}_*"))
        if matches and matches[0].is_file():
            return matches[0]
        return None
