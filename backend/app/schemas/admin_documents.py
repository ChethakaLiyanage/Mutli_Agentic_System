"""Schemas for Admin Policy and Knowledge Document Management."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

DocumentStatus = Literal["processing", "active", "superseded", "failed", "archived"]
DocumentAudience = Literal["customer", "internal", "all"]


class PolicyDocumentItem(BaseModel):
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
    status: DocumentStatus = "active"
    chunks_count: int = 0
    previous_version_id: str | None = None
    change_summary: str | None = None
    uploaded_by: str = "admin"
    created_at: str
    activated_at: str | None = None
    superseded_at: str | None = None
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDocumentListResponse(BaseModel):
    documents: list[PolicyDocumentItem]
    total: int


class PolicyDocumentDetailResponse(BaseModel):
    document: PolicyDocumentItem
    content_preview: str | None = None
    chunks_count: int = 0


class PolicyDocumentVersionsResponse(BaseModel):
    root_document_id: str
    title: str
    versions: list[PolicyDocumentItem]


class PolicyDocumentOperationResponse(BaseModel):
    success: bool
    message: str
    document: PolicyDocumentItem
    chunks_indexed: int = 0
