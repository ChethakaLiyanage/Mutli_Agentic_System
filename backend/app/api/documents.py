"""API endpoints for customer claim document uploads."""

from __future__ import annotations

import logging
from typing import Annotated, Any

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.api.orchestrator import get_orchestrator_service
from backend.app.config import Settings, get_settings
from backend.app.orchestrator.service import (
    OrchestratorService,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
)
from backend.app.schemas.auth import AuthenticatedUser, UserRole
from backend.app.schemas.domain import DocumentReference, DocumentType
from backend.app.security.dependencies import bearer_scheme, get_current_customer, get_user_repository
from backend.app.security.jwt import InvalidAccessTokenError, decode_access_token
from backend.app.security.user_repository import UserRepository
from backend.app.services.document_service import DocumentService, get_document_repository
from backend.app.services.repository_errors import RepositoryError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["claim-documents"])
_document_service = DocumentService()


def get_document_service() -> DocumentService:
    return _document_service


async def get_flexible_user(
    credentials=Depends(bearer_scheme),
    token: str | None = Query(None),
    repository: UserRepository = Depends(get_user_repository),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    token_str = None
    if credentials and credentials.scheme.lower() == "bearer":
        token_str = credentials.credentials
    elif token:
        token_str = token

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(token_str, settings)
    except InvalidAccessTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        user = await repository.get_by_id(claims["sub"])
    except RepositoryError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from error

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/orchestrator/workflows/{workflow_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_claim_document(
    workflow_id: str,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)] = None,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """Upload a supporting document for an active claim in awaiting_documents."""
    state = await orchestrator_service.workflow_repository.get(workflow_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    if state.authenticated_user_id != current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You are not authorized to upload documents for this workflow",
        )
    if not state.claim_context or not state.claim_context.claim_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No active claim draft exists for this workflow",
        )

    claim_id = state.claim_context.claim_id
    try:
        record = await document_service.upload_document(
            claim_id=claim_id,
            customer_id=current_user.user_id,
            file=file,
            document_type_str=document_type,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception as e:
        logger.exception("Failed to store document for claim %s", claim_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to store document",
        ) from e

    # Update workflow state claim_context document references
    doc_ref = DocumentReference(
        document_id=record["document_id"],
        document_type=DocumentType(record["document_type"]),
    )
    if not any(ref.document_id == doc_ref.document_id for ref in state.claim_context.document_references):
        state.claim_context = state.claim_context.model_copy(
            update={
                "document_references": [
                    *state.claim_context.document_references,
                    doc_ref,
                ]
            }
        )
        await orchestrator_service.workflow_repository.save(state)

    return {
        "document_id": record["document_id"],
        "claim_id": claim_id,
        "document_type": record["document_type"],
        "file_name": record["file_name"],
        "created_at": record["created_at"],
        "message": "Document uploaded successfully",
    }


@router.get("/orchestrator/workflows/{workflow_id}/documents")
async def list_claim_documents(
    workflow_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)] = None,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
    document_service: DocumentService = Depends(get_document_service),
) -> list[dict[str, Any]]:
    """List customer's uploaded documents for this workflow."""
    state = await orchestrator_service.workflow_repository.get(workflow_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    if state.authenticated_user_id != current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You are not authorized to view documents for this workflow",
        )
    if not state.claim_context or not state.claim_context.claim_id:
        return []

    docs = await document_service.list_documents(
        claim_id=state.claim_context.claim_id,
        customer_id=current_user.user_id,
    )
    return [
        {
            "document_id": doc["document_id"],
            "claim_id": doc["claim_id"],
            "document_type": doc["document_type"],
            "file_name": doc["file_name"],
            "created_at": doc.get("created_at"),
            "file_size": (doc.get("metadata") or {}).get("file_size"),
            "download_url": f"/documents/{doc['document_id']}/download",
        }
        for doc in docs
    ]


@router.get("/documents/{document_id}/download")
@router.get("/documents/{document_id}/view")
@router.get("/documents/{document_id}/content")
@router.get("/orchestrator/workflows/documents/{document_id}/download")
async def download_document(
    document_id: str,
    as_attachment: bool = Query(False),
    user: AuthenticatedUser = Depends(get_flexible_user),
    document_service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    """Download or view a submitted claim document.

    Accessible to the customer who uploaded it, claims officers, and admins.
    """
    doc = await document_service.get_document(document_id)
    file_path = document_service.get_document_file_path(document_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document file not found on server")

    if user.role not in (UserRole.ADMIN, UserRole.CLAIMS_OFFICER):
        doc_cust_id = (doc or {}).get("customer_id")
        if doc_cust_id and doc_cust_id != user.user_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You are not authorized to view this document",
            )

    meta = (doc or {}).get("metadata") or {}
    filename = (
        meta.get("original_filename")
        or (doc or {}).get("file_name")
        or file_path.name.replace(f"{document_id}_", "", 1)
    )
    content_type = meta.get("content_type")
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(filename)
        content_type = guessed_type or "application/octet-stream"

    disposition = "attachment" if as_attachment else "inline"
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=filename,
        content_disposition_type=disposition,
    )
