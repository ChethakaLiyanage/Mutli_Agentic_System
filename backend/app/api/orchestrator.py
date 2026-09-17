"""REST endpoint for the motor-insurance workflow Orchestrator."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.service import (
    OrchestratorService,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowNotResumableError,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.orchestrator import (
    ClarificationRequest,
    ClarificationResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from backend.app.security.dependencies import get_current_customer
from backend.app.services.persistence import get_application_repositories


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
_workflow_repository = get_application_repositories().workflows
_orchestrator_service = OrchestratorService(
    claim_intake_client=LocalClaimIntakeClient(),
    retrieval_client=LocalRetrievalClient(),
    workflow_repository=_workflow_repository,
)


def get_orchestrator_service() -> OrchestratorService:
    """Provide the replaceable application-level Orchestrator service."""

    return _orchestrator_service


@router.post(
    "/process",
    response_model=OrchestratorResponse | ClarificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a motor-insurance request",
    description=(
        "Run Claim Intake analysis and, for information requests, controlled "
        "Agent 2 retrieval before returning the current workflow state."
    ),
)
async def process_orchestrator_request(
    request: OrchestratorRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse | ClarificationResponse:
    """Validate and process one independent workflow request."""

    logger.info("%s orchestrator request received", request.request_id)
    try:
        response = await service.process_request(
            request,
            authenticated_user_id=current_user.user_id,
            authenticated_user_role=current_user.role.value,
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


@router.post(
    "/workflows/{workflow_id}/clarify",
    response_model=OrchestratorResponse | ClarificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Continue a workflow with clarification",
    description=(
        "Append a clarification message to an awaiting workflow and rerun "
        "Claim Intake Agent analysis using the accumulated context."
    ),
)
async def clarify_orchestrator_workflow(
    workflow_id: str,
    request: ClarificationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse | ClarificationResponse:
    """Resume one persisted workflow without trusting body-supplied identity."""

    logger.info(
        "%s workflow %s clarification received",
        request.request_id,
        workflow_id,
    )
    try:
        response = await service.resume_clarification(
            workflow_id,
            request,
            authenticated_user_id=current_user.user_id,
            authenticated_user_role=current_user.role.value,
        )
    except WorkflowNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        ) from error
    except WorkflowNotResumableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow is not awaiting clarification",
        ) from error
    except WorkflowAccessDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this workflow",
        ) from error
    except Exception as error:
        logger.exception(
            "%s workflow %s clarification failed",
            request.request_id,
            workflow_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Orchestrator service failed",
        ) from error

    logger.info(
        "%s workflow %s clarification completed: %s",
        request.request_id,
        workflow_id,
        response.status.value,
    )
    return response
