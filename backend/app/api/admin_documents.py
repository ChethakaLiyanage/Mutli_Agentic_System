"""Admin endpoints for Policy and Knowledge Document Management."""

from __future__ import annotations

from hashlib import sha256
import logging
from pathlib import Path
import re
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import PlainTextResponse

from backend.app.retrieval.document_ingestion import (
    DocumentIngestionError,
    DocumentIngestor,
    SUPPORTED_EXTENSIONS,
)
from backend.app.retrieval.document_repository import (
    PolicyDocument,
    PolicyDocumentRepository,
    bootstrap_existing_documents,
    get_policy_document_repository,
)
from backend.app.retrieval.knowledge_retriever import get_shared_knowledge_retriever
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.schemas.admin_documents import (
    PolicyDocumentDetailResponse,
    PolicyDocumentItem,
    PolicyDocumentListResponse,
    PolicyDocumentOperationResponse,
    PolicyDocumentVersionsResponse,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.dependencies import get_current_admin
from backend.app.services.supabase_service import get_supabase_client
from backend.app.policy_types import CANONICAL_POLICY_TYPES, normalize_policy_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/policy-documents", tags=["admin-policy-documents"])

MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_DOCUMENT_TYPES = {
    "policy_document",
    "policy_manual",
    "procedure_guide",
    "guideline",
    "manual",
    "other",
}
ALLOWED_POLICY_TYPES = CANONICAL_POLICY_TYPES | {None}
ALLOWED_AUDIENCES = {"customer", "internal", "all"}


def _get_chunk_repository() -> RetrievalRepository:
    client = get_supabase_client()
    return RetrievalRepository(client)


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-_]", "_", name)
    return cleaned[:100]


@router.get(
    "",
    response_model=PolicyDocumentListResponse,
    summary="List all manageable policy documents",
)
async def list_policy_documents(
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
    status: str | None = None,
    policy_type: str | None = None,
    document_type: str | None = None,
    audience: str | None = None,
    root_only: bool = True,
) -> PolicyDocumentListResponse:
    """Retrieve list of managed policy/knowledge documents for the admin dashboard."""
    # Ensure initial corpus is bootstrapped
    existing = doc_repo.list_documents()
    if not existing:
        try:
            chunk_repo = _get_chunk_repository()
            bootstrap_existing_documents(doc_repo, chunk_repo=chunk_repo)
        except Exception as e:
            logger.warning("Auto-bootstrap during list_policy_documents failed: %s", e)

    documents = doc_repo.list_documents(
        status=status,
        policy_type=policy_type,
        document_type=document_type,
        audience=audience,
        root_only=root_only,
    )
    items = [PolicyDocumentItem.model_validate(d.model_dump()) for d in documents]
    return PolicyDocumentListResponse(documents=items, total=len(items))


@router.get(
    "/{document_id}",
    response_model=PolicyDocumentDetailResponse,
    summary="Get single policy document details",
)
async def get_policy_document(
    document_id: str,
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
) -> PolicyDocumentDetailResponse:
    doc = doc_repo.get_document_by_id(document_id)
    if not doc:
        # Check by root_document_id
        doc = doc_repo.get_active_by_root_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy document '{document_id}' not found",
        )

    content_preview = None
    if doc.storage_path and Path(doc.storage_path).is_file():
        try:
            raw_text = Path(doc.storage_path).read_text(encoding="utf-8", errors="replace")
            content_preview = raw_text[:2000]
        except Exception as e:
            logger.warning("Could not read document preview from %s: %s", doc.storage_path, e)

    item = PolicyDocumentItem.model_validate(doc.model_dump())
    return PolicyDocumentDetailResponse(
        document=item,
        content_preview=content_preview,
        chunks_count=doc.chunks_count,
    )


@router.get(
    "/{document_id}/versions",
    response_model=PolicyDocumentVersionsResponse,
    summary="Get version history of a document",
)
async def get_document_version_history(
    document_id: str,
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
) -> PolicyDocumentVersionsResponse:
    doc = doc_repo.get_document_by_id(document_id)
    if not doc:
        doc = doc_repo.get_active_by_root_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy document '{document_id}' not found",
        )

    versions = doc_repo.get_versions_for_root(doc.root_document_id)
    items = [PolicyDocumentItem.model_validate(v.model_dump()) for v in versions]
    return PolicyDocumentVersionsResponse(
        root_document_id=doc.root_document_id,
        title=doc.title,
        versions=items,
    )


@router.get(
    "/{document_id}/content",
    summary="Download or view raw content of policy document",
)
async def get_document_raw_content(
    document_id: str,
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
) -> Response:
    doc = doc_repo.get_document_by_id(document_id)
    if not doc:
        doc = doc_repo.get_active_by_root_id(document_id)
    if not doc or not doc.storage_path or not Path(doc.storage_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source content for '{document_id}' not available",
        )

    path = Path(doc.storage_path)
    content = path.read_bytes()
    media_type = "text/plain"
    if path.suffix.lower() == ".pdf":
        media_type = "application/pdf"
    elif path.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_filename}"'
        },
    )


@router.post(
    "",
    response_model=PolicyDocumentOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a new policy document",
)
async def upload_new_document(
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
    title: str = Form(...),
    document_type: str = Form("policy_document"),
    policy_type: str | None = Form(None),
    audience: str = Form("customer"),
    version: str = Form("1.0"),
    file: UploadFile = File(...),
) -> PolicyDocumentOperationResponse:
    """Upload a new controlled document, extract, chunk, persist, and refresh TF-IDF index."""
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Document title cannot be empty")

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type. Allowed: {sorted(ALLOWED_DOCUMENT_TYPES)}",
        )

    if policy_type in ("", "none", "null"):
        policy_type = None
    try:
        policy_type = normalize_policy_type(policy_type, strict=policy_type is not None)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid policy_type. Allowed: {sorted(str(x) for x in ALLOWED_POLICY_TYPES)}",
        ) from error
    if audience not in ALLOWED_AUDIENCES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid audience. Allowed: {sorted(ALLOWED_AUDIENCES)}",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}",
        )
    if document_type == "policy_document" and policy_type is None:
        raise HTTPException(
            status_code=422,
            detail="policy_type is required when document_type is policy_document",
        )

    content_bytes = await file.read()
    if not content_bytes or len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum 15MB limit")

    checksum = sha256(content_bytes).hexdigest()
    safe_filename = _sanitize_filename(file.filename)
    dest_dir = Path("backend/data/policy_docs")
    dest_dir.mkdir(parents=True, exist_ok=True)
    storage_path = dest_dir / safe_filename

    # If destination already exists with different content, namespace it
    if storage_path.is_file() and sha256(storage_path.read_bytes()).hexdigest() != checksum:
        stem = storage_path.stem
        storage_path = dest_dir / f"{stem}_{checksum[:8]}{suffix}"

    storage_path.write_bytes(content_bytes)

    root_id = "doc-" + sha256(f"{document_type}:{title.lower()}:{policy_type or ''}".encode()).hexdigest()[:24]

    # Ingestion into chunks
    chunk_repo = _get_chunk_repository()
    ingestor = DocumentIngestor(chunk_repo)

    doc_record = PolicyDocument(
        id=root_id,
        root_document_id=root_id,
        title=title,
        document_type=document_type,
        policy_type=policy_type,
        audience=audience,
        version=version.strip() or "1.0",
        original_filename=file.filename,
        storage_path=str(storage_path),
        checksum=checksum,
        status="processing",
        chunks_count=0,
        uploaded_by=_admin.email,
    )
    doc_repo.create_document(doc_record)

    try:
        result = ingestor.ingest_file(
            storage_path,
            document_type=document_type,  # type: ignore[arg-type]
            source_document_id=root_id,
            source_title=title,
            policy_type=policy_type,
            metadata={
                "status": "active",
                "version": version,
                "audience": audience,
                "document_id": root_id,
                "root_document_id": root_id,
            },
        )
    except DocumentIngestionError as err:
        logger.exception("Ingestion failed for new document %s", title)
        doc_repo.update_document(root_id, {"status": "failed", "change_summary": str(err)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document parsing/ingestion failed: {err}",
        ) from err

    # Activate
    chunks_count = result.chunks_created_or_updated
    updated = doc_repo.update_document(
        root_id,
        {
            "status": "active",
            "activated_at": doc_record.created_at,
            "chunks_count": chunks_count,
        },
    )

    # Trigger live zero-restart TF-IDF refresh
    try:
        retriever = get_shared_knowledge_retriever(repository=chunk_repo)
        refreshed_count = retriever.refresh()
    except Exception as e:
        logger.warning("Index refresh encountered issue: %s", e)
        refreshed_count = chunks_count

    return PolicyDocumentOperationResponse(
        success=True,
        message=f"Document '{title}' successfully ingested and activated with {chunks_count} chunks.",
        document=PolicyDocumentItem.model_validate(updated.model_dump()),
        chunks_indexed=refreshed_count,
    )


@router.post(
    "/{document_id}/replace",
    response_model=PolicyDocumentOperationResponse,
    summary="Upload a new replacement version of an existing document",
)
async def replace_policy_document_version(
    document_id: str,
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    doc_repo: Annotated[PolicyDocumentRepository, Depends(get_policy_document_repository)],
    version: str = Form(...),
    title: str | None = Form(None),
    change_summary: str | None = Form(None),
    file: UploadFile = File(...),
) -> PolicyDocumentOperationResponse:
    """Atomically replace an existing document with a new version without retrieval downtime.

    V1 remains active until V2 is fully parsed, chunked, and persisted.
    Upon success: V2 -> active, V1 -> superseded, TF-IDF refreshed immediately.
    If V2 fails: V2 -> failed, V1 remains active.
    """
    version = version.strip()
    if not version:
        raise HTTPException(status_code=400, detail="New version string cannot be empty")

    current_doc = doc_repo.get_document_by_id(document_id)
    if not current_doc:
        current_doc = doc_repo.get_active_by_root_id(document_id)
    if not current_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base document '{document_id}' not found",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Replacement file has no filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    content_bytes = await file.read()
    if not content_bytes or len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="Replacement file is empty")
    if len(content_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum 15MB limit")

    checksum = sha256(content_bytes).hexdigest()
    safe_filename = _sanitize_filename(file.filename)
    dest_dir = Path("backend/data/policy_docs")
    dest_dir.mkdir(parents=True, exist_ok=True)
    version_slug = version.replace(".", "_")
    storage_path = dest_dir / f"{Path(safe_filename).stem}_v{version_slug}{suffix}"
    storage_path.write_bytes(content_bytes)

    # Distinct source ID for V2
    v2_id = f"{current_doc.root_document_id}_v{version_slug}"
    new_title = (title.strip() if title and title.strip() else current_doc.title)

    v2_record = PolicyDocument(
        id=v2_id,
        root_document_id=current_doc.root_document_id,
        title=new_title,
        document_type=current_doc.document_type,
        policy_type=current_doc.policy_type,
        audience=current_doc.audience,
        version=version,
        original_filename=file.filename,
        storage_path=str(storage_path),
        checksum=checksum,
        status="processing",
        chunks_count=0,
        previous_version_id=current_doc.id,
        change_summary=change_summary,
        uploaded_by=_admin.email,
    )
    doc_repo.create_document(v2_record)

    chunk_repo = _get_chunk_repository()
    ingestor = DocumentIngestor(chunk_repo)

    try:
        result = ingestor.ingest_file(
            storage_path,
            document_type=current_doc.document_type,  # type: ignore[arg-type]
            source_document_id=v2_id,
            source_title=new_title,
            policy_type=current_doc.policy_type,
            metadata={
                "status": "active",
                "version": version,
                "audience": current_doc.audience,
                "document_id": v2_id,
                "root_document_id": current_doc.root_document_id,
            },
        )
    except DocumentIngestionError as err:
        logger.exception("Replacement ingestion failed for V%s of %s", version, current_doc.title)
        # Mark V2 failed, keep current_doc active!
        doc_repo.update_document(v2_id, {"status": "failed", "change_summary": str(err)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Replacement document failed ingestion: {err}. Previous active version remains active.",
        ) from err

    # Step: Ingestion of V2 succeeded!
    # 1. Activate V2
    chunks_count = result.chunks_created_or_updated
    activated_v2 = doc_repo.update_document(
        v2_id,
        {
            "status": "active",
            "activated_at": v2_record.created_at,
            "chunks_count": chunks_count,
        },
    )

    # 2. Mark previous version(s) superseded
    doc_repo.mark_superseded(current_doc.id, superseded_by_id=v2_id)
    # Mark old chunks superseded in chunk storage
    try:
        chunk_repo.mark_chunks_status_for_source(current_doc.id, "superseded")
    except Exception as e:
        logger.warning("Could not mark old chunks superseded for %s: %s", current_doc.id, e)

    # 3. Rebuild in-memory TF-IDF index immediately!
    retriever = get_shared_knowledge_retriever(repository=chunk_repo)
    refreshed_count = retriever.refresh()

    logger.info(
        "Successfully replaced document '%s': V%s is now active, V%s is superseded. Refreshed index (%d chunks).",
        current_doc.title,
        version,
        current_doc.version,
        refreshed_count,
    )

    return PolicyDocumentOperationResponse(
        success=True,
        message=f"Document '{new_title}' successfully upgraded to V{version}. Previous version (V{current_doc.version}) superseded.",
        document=PolicyDocumentItem.model_validate(activated_v2.model_dump()),
        chunks_indexed=refreshed_count,
    )
