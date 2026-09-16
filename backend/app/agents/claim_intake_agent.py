"""Claim Intake & Query Understanding Agent foundation."""

from backend.app.schemas.intake import (
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)


class ClaimIntakeAgent:
    """Provide the stable intake interface used by the future orchestrator.

    NLP components are intentionally not connected yet. Until they are, the
    response is marked as pending and contains no facts inferred from the text.
    """

    def analyze(self, request: IntakeRequest) -> IntakeResponse:
        """Return an evidence-safe placeholder response for a validated request."""

        if not isinstance(request, IntakeRequest):
            raise TypeError("request must be an IntakeRequest instance")

        return IntakeResponse(
            request_id=request.request_id,
            status="pending",
            data=IntakeData(
                intent=IntentResult(label=None, confidence=0.0),
            ),
        )
