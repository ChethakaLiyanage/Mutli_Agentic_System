"""Pydantic schemas for claim document handling."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class ClaimDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    claim_id: str
    customer_id: str | None = None
    document_type: str
    original_filename: str
    file_size_bytes: int | None = None
    content_type: str | None = None
    uploaded_at: Any = None
    download_url: str | None = None
