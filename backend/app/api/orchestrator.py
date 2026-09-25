from __future__ import annotations
from backend.app.security.input_sanitization import InputSanitizationError, sanitize_user_text
"""REST endpoint for the motor-insurance workflow Orchestrator."""


import logging
from typing import Annotated

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator.agent_clients import (
    LocalFraudClient,
    LocalGuidanceClient,
    LocalClaimIntakeClient,
)
from backend.app.config import get_settings
from backend.app.orchestrator.claim_repository import (
    InMemoryClaimRepository,
    SupabaseClaimRepository,
    get_claim_repository,
)
from backend.app.fraud.repository import FraudRepository, InMemoryFraudRepository
from backend.app.orchestrator.agent_clients import LocalRetrievalClient
from backend.app.orchestrator.service import (
    InvalidWorkflowTransition,
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
from backend.app.services.supabase_service import get_supabase_client


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
_workflow_repository = get_application_repositories().workflows
_settings = get_settings()
_claim_repository = get_claim_repository()
if _settings.persistence_backend == "supabase":
    _supabase_client = get_supabase_client(_settings)
    _fraud_repository = FraudRepository(_supabase_client)
    _retrieval_client = LocalRetrievalClient()
else:
    _fraud_repository = InMemoryFraudRepository()
    _retrieval_client = None
_orchestrator_service = OrchestratorService(
    claim_intake_client=LocalClaimIntakeClient(),
    retrieval_client=_retrieval_client,
    fraud_client=LocalFraudClient(),
    claim_repository=_claim_repository,
    fraud_repository=_fraud_repository,
    guidance_client=LocalGuidanceClient(),
    workflow_repository=_workflow_repository,
)


def get_orchestrator_service() -> OrchestratorService:
    """Provide the replaceable application-level Orchestrator service."""

    return _orchestrator_service


@router.get(
    "/workflows/{workflow_id}",
    response_model=OrchestratorResponse,
    summary="Get an owner-safe workflow result",
)
async def get_customer_workflow_result(
    workflow_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse:
    try:
        return await service.get_customer_workflow_result(
            workflow_id,
            authenticated_user_id=current_user.user_id,
        )
    except WorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except WorkflowAccessDeniedError as error:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You are not authorized to access this workflow",
        ) from error
    except Exception as error:
        logger.exception("Customer workflow result failed for %s", workflow_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Workflow result is temporarily unavailable",
        ) from error


@router.post(
    "/process",
    response_model=OrchestratorResponse | ClarificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a motor-insurance request",
    description=(
        "Run Claim Intake analysis, controlled retrieval, and claim risk triage "
        "for the applicable workflow without making a claim decision."
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
        request = request.model_copy(
            update={"text": sanitize_user_text(request.text)}
        )
        response = await service.process_request(
            request,
            authenticated_user_id=current_user.user_id,
            authenticated_user_role=current_user.role.value,
        )
    except InputSanitizationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
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
        request = request.model_copy(
            update={"text": sanitize_user_text(request.text)}
        )
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


@router.post(
    "/workflows/{workflow_id}/submit-claim",
    response_model=OrchestratorResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Submit claim documents for fraud triage and review",
    description=(
        "Validate customer documents, run Agent 3 fraud triage, generate internal review summary, and transition to awaiting_assignment."
    ),
)
async def submit_claim(
    workflow_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse:
    logger.info("Workflow %s submit-claim received for customer %s", workflow_id, current_user.user_id)
    try:
        response = await service.submit_claim(
            workflow_id,
            authenticated_user_id=current_user.user_id,
        )
        return response
    except WorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except WorkflowAccessDeniedError as error:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You are not authorized to access this workflow",
        ) from error
    except InvalidWorkflowTransition as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            str(error),
        ) from error
    except Exception as error:
        logger.exception("Submit claim failed for workflow %s", workflow_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Claim submission failed",
        ) from error


@router.post(
    "/workflows/{workflow_id}/recheck-documents",
    response_model=OrchestratorResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Recheck uploaded claim documents",
)
async def recheck_documents(
    workflow_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse:
    try:
        return await service.recheck_documents(
            workflow_id,
            authenticated_user_id=current_user.user_id,
        )
    except WorkflowNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found") from error
    except WorkflowAccessDeniedError as error:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You are not authorized to access this workflow",
        ) from error
    except InvalidWorkflowTransition as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except Exception as error:
        logger.exception("Document recheck failed for workflow %s", workflow_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Document recheck failed",
        ) from error

