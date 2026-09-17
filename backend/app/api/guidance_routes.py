"""FastAPI router for Agent 4: Guidance Agent / Reviewer Support Agent.

Implements Sections 8, 13.2, and 13.3 of the Agent 4 Design Guide.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status
from ..guidance.schemas import GuidanceRequest, GuidanceResponse
from ..guidance.service import GuidanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guidance", tags=["guidance"])
_service = GuidanceService()


@router.get("/health", status_code=status.HTTP_200_OK)
def guidance_health() -> dict[str, str]:
    """Lightweight health check for the Guidance Agent service."""
    return {
        "status": "ok",
        "service": "guidance-agent",
        "version": "1.0.0",
    }


@router.post(
    "/generate",
    response_model=GuidanceResponse,
    status_code=status.HTTP_200_OK,
)
def generate_guidance(request: GuidanceRequest) -> GuidanceResponse:
    """Generate audience-tailored guidance or reviewer summary from structured evidence."""
    try:
        return _service.process_request(request)
    except Exception as err:
        logger.exception("Error processing guidance request: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Guidance Agent processing error: {err}",
        ) from err


@router.post(
    "/customer",
    response_model=GuidanceResponse,
    status_code=status.HTTP_200_OK,
)
def generate_customer_guidance(request: GuidanceRequest) -> GuidanceResponse:
    """Dedicated endpoint enforcing customer audience constraints."""
    customer_request = request.model_copy(update={"audience": "customer"})
    return _service.process_request(customer_request)


@router.post(
    "/reviewer-summary",
    response_model=GuidanceResponse,
    status_code=status.HTTP_200_OK,
)
def generate_reviewer_summary(request: GuidanceRequest) -> GuidanceResponse:
    """Dedicated endpoint enforcing reviewer summary constraints."""
    reviewer_request = request.model_copy(
        update={"audience": "reviewer", "task_type": "reviewer_summary"}
    )
    return _service.process_request(reviewer_request)
