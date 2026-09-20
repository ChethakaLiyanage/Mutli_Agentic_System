"""Authenticated claims-officer human-review API."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.config import get_settings
from backend.app.review.repository import (
    InMemoryHumanReviewRepository,
    ReviewRepositoryError,
    SupabaseHumanReviewRepository,
)
from backend.app.review.service import (
    HumanReviewService,
    ReviewWorkflowConflictError,
    ReviewWorkflowNotFoundError,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.domain import IncidentType, RiskLevel
from backend.app.schemas.review import (
    ClaimAssignmentRequest,
    ClaimAssignmentResponse,
    HumanDecisionRequest,
    HumanDecisionResponse,
    ReviewDetailResponse,
    ReviewQueueResponse,
)
from backend.app.security.dependencies import get_current_admin, get_current_reviewer
from backend.app.services.persistence import get_application_repositories
from backend.app.services.supabase_service import get_supabase_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["human-review"])
_workflows = get_application_repositories().workflows
if get_settings().persistence_backend == "supabase":
    _review_repository = SupabaseHumanReviewRepository(
        get_supabase_client(), _workflows
    )
else:
    _review_repository = InMemoryHumanReviewRepository(_workflows)
_review_service = HumanReviewService(_review_repository)


def get_review_service() -> HumanReviewService:
    return _review_service


@router.get("/queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    _reviewer: Annotated[AuthenticatedUser, Depends(get_current_reviewer)],
    service: Annotated[HumanReviewService, Depends(get_review_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    risk_level: RiskLevel | None = None,
    incident_type: IncidentType | None = None,
) -> ReviewQueueResponse:
    """List every eligible claim oldest-first; low risk is never hidden."""
    try:
        return await service.list_queue(
            limit=limit,
            offset=offset,
            risk_level=risk_level.value if risk_level else None,
            incident_type=incident_type.value if incident_type else None,
        )
    except ReviewRepositoryError as error:
        logger.exception("Review queue repository failed")
        raise HTTPException(500, "Review queue is temporarily unavailable") from error


@router.get("/workflows/{workflow_id}", response_model=ReviewDetailResponse)
async def get_review_detail(
    workflow_id: str,
    _reviewer: Annotated[AuthenticatedUser, Depends(get_current_reviewer)],
    service: Annotated[HumanReviewService, Depends(get_review_service)],
) -> ReviewDetailResponse:
    try:
        return await service.get_detail(workflow_id)
    except ReviewWorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except ReviewWorkflowConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ReviewRepositoryError as error:
        logger.exception("Review detail repository failed")
        raise HTTPException(500, "Review detail is temporarily unavailable") from error


@router.post(
    "/workflows/{workflow_id}/assign",
    response_model=ClaimAssignmentResponse,
)
async def assign_claim(
    workflow_id: str,
    request: ClaimAssignmentRequest,
    admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    service: Annotated[HumanReviewService, Depends(get_review_service)],
) -> ClaimAssignmentResponse:
    try:
        return await service.assign_claim(workflow_id, request, admin)
    except ReviewWorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except ReviewWorkflowConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ReviewRepositoryError as error:
        logger.exception("Claim assignment repository failed")
        raise HTTPException(500, "Claim assignment could not be stored") from error


@router.post(
    "/workflows/{workflow_id}/decision",
    response_model=HumanDecisionResponse,
)
async def submit_human_decision(
    workflow_id: str,
    request: HumanDecisionRequest,
    reviewer: Annotated[AuthenticatedUser, Depends(get_current_reviewer)],
    service: Annotated[HumanReviewService, Depends(get_review_service)],
) -> HumanDecisionResponse:
    try:
        return await service.submit_decision(workflow_id, request, reviewer)
    except ReviewWorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except ReviewWorkflowConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ReviewRepositoryError as error:
        logger.exception("Human decision repository failed")
        raise HTTPException(500, "Human decision could not be stored") from error
