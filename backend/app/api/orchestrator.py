"""REST endpoint for the motor-insurance workflow Orchestrator."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator.agent_clients import LocalClaimIntakeClient
from backend.app.orchestrator.service import OrchestratorService
from backend.app.schemas.orchestrator import (
    ClarificationResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
_orchestrator_service = OrchestratorService(LocalClaimIntakeClient())


def get_orchestrator_service() -> OrchestratorService:
    """Provide the replaceable application-level Orchestrator service."""

    return _orchestrator_service


@router.post(
    "/process",
    response_model=OrchestratorResponse | ClarificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a motor-insurance request",
    description=(
        "Run Claim Intake Agent analysis and return either a downstream-ready "
        "workflow decision or a deterministic clarification request."
    ),
)
async def process_orchestrator_request(
    request: OrchestratorRequest,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse | ClarificationResponse:
    """Validate and process one independent workflow request."""

    logger.info("%s orchestrator request received", request.request_id)
    try:
        # TODO: Supply trusted identity through a FastAPI security dependency.
        response = await service.process_request(
            request,
            authenticated_user_id=None,
            authenticated_user_role=None,
        )
    except Exception as error:
        logger.exception(
            "%s orchestrator service failed",
            request.request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Orchestrator service failed",
        ) from error

    logger.info(
        "%s orchestrator completed: %s",
        request.request_id,
        response.status.value,
    )
    return response
