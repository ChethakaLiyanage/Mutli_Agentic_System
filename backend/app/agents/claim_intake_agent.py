"""Claim Intake & Query Understanding Agent."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from backend.app.nlp.damage_extraction import extract_damage_areas
from backend.app.nlp.date_extraction import extract_date
from backend.app.nlp.entity_extraction import extract_entities
from backend.app.nlp.incident_extraction import extract_incident_type
from backend.app.nlp.intent_classifier import predict_intent
from backend.app.nlp.preprocessing import preprocess_text
from backend.app.schemas.intake import (
    DamageInformation,
    ExtractedEntity,
    IncidentInformation,
    IntakeData,
    IntakeRequest,
    IntakeResponse,
    IntentResult,
)


logger = logging.getLogger(__name__)

INTENT_CONFIDENCE_THRESHOLD = 0.50
_CLAIM_REQUIRED_FIELDS = ("incident_type", "incident_date", "location")


def _select_location(entities: list[ExtractedEntity]) -> str | None:
    """Select the first grounded location in source-text order."""

    return next(
        (
            entity.value.strip()
            for entity in entities
            if entity.entity_type == "LOCATION" and entity.value.strip()
        ),
        None,
    )


def _find_missing_claim_fields(
    incident_type: str | None,
    date_text: str | None,
    location: str | None,
) -> list[str]:
    available = {
        "incident_type": bool(incident_type),
        "incident_date": bool(date_text),
        "location": bool(location),
    }
    return [field for field in _CLAIM_REQUIRED_FIELDS if not available[field]]


class ClaimIntakeAgent:
    """Convert a customer message into a grounded structured intake response."""

    def __init__(
        self,
        confidence_threshold: float = INTENT_CONFIDENCE_THRESHOLD,
        reference_date_provider: Callable[[], date] = date.today,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        self.confidence_threshold = confidence_threshold
        self._reference_date_provider = reference_date_provider

    def analyze(self, request: IntakeRequest) -> IntakeResponse:
        """Run the complete deterministic and statistical intake pipeline."""

        if not isinstance(request, IntakeRequest):
            raise TypeError("request must be an IntakeRequest instance")

        original_text = request.text

        try:
            cleaned_text = preprocess_text(original_text)
            if not cleaned_text:
                raise ValueError("text must not be empty after preprocessing")
            intent_label, intent_confidence = predict_intent(original_text)

            entities = extract_entities(original_text)
            incident_type = extract_incident_type(original_text)
            damage_areas = extract_damage_areas(original_text)
            date_text, normalized_date = extract_date(
                original_text,
                reference_date=self._reference_date_provider(),
            )
            location = _select_location(entities)

            missing_fields = (
                _find_missing_claim_fields(incident_type, date_text, location)
                if intent_label == "claim_submission"
                else []
            )
            requires_clarification = bool(missing_fields) or (
                intent_confidence < self.confidence_threshold
            )

            return IntakeResponse(
                request_id=request.request_id,
                status="success",
                data=IntakeData(
                    intent=IntentResult(
                        label=intent_label,
                        confidence=intent_confidence,
                    ),
                    incident=IncidentInformation(
                        type=incident_type,
                        date_text=date_text,
                        normalized_date=normalized_date,
                        location=location,
                    ),
                    damage=DamageInformation(areas=damage_areas),
                    entities=entities,
                    missing_fields=missing_fields,
                    requires_clarification=requires_clarification,
                ),
            )
        except Exception:
            logger.exception(
                "Claim intake analysis failed for request %s",
                request.request_id,
            )
            return IntakeResponse(
                request_id=request.request_id,
                status="error",
                data=IntakeData(
                    intent=IntentResult(label=None, confidence=0.0),
                ),
                errors=["Claim intake analysis failed"],
            )
