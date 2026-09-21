from __future__ import annotations
"""REST endpoint for the Claim Intake & Query Understanding Agent."""


import logging

from fastapi import APIRouter, HTTPException, status

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.schemas.intake import IntakeRequest, IntakeResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intake", tags=["claim-intake"])
_claim_intake_agent = ClaimIntakeAgent()


from backend.app.security.input_sanitization import (
    InputSanitizationError,
    sanitize_user_text,
)


@router.post(
    "/analyze",
    response_model=IntakeResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_intake(request: IntakeRequest) -> IntakeResponse:
    """Validate and analyze one customer motor-insurance message."""

    try:
        sanitized_text = sanitize_user_text(request.text)
        sanitized_request = request.model_copy(update={"text": sanitized_text})
        return _claim_intake_agent.analyze(sanitized_request)
    except InputSanitizationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("Unhandled failure in the claim-intake API")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Claim intake service failed",
        ) from error
