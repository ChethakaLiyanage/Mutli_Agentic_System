"""Data contracts for the Claim Intake & Query Understanding Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


IntentLabel = Literal[
    "greeting",
    "claim_submission",
    "policy_question",
    "coverage_question",
    "required_documents_question",
    "claim_status",
    "general_information",
]

IncidentType = Literal[
    "vehicle_collision",
    "windscreen_damage",
    "flood_damage",
    "theft_or_break_in",
]

ResponseStatus = Literal["success", "pending", "needs_clarification", "error"]


class _IntakeContract(BaseModel):
    """Common strict configuration for intake request and response models."""

    model_config = ConfigDict(extra="forbid")


class IntakeRequest(_IntakeContract):
    """A customer's free-text request submitted to the intake agent."""

    request_id: str
    text: str

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("request_id cannot be empty")
        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("text must contain at least 2 characters")
        if len(value) > 3000:
            raise ValueError("text must contain at most 3000 characters")
        return value


class IntentResult(_IntakeContract):
    """The intent predicted for a customer message."""

    label: IntentLabel | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedEntity(_IntakeContract):
    """A value extracted from the message, with optional source offsets."""

    entity_type: str
    value: str
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IncidentInformation(_IntakeContract):
    """Incident facts explicitly extracted from the customer's message."""

    type: IncidentType | None = None
    date_text: str | None = None
    normalized_date: str | None = None
    location: str | None = None


class DamageInformation(_IntakeContract):
    """Vehicle damage explicitly described by the customer."""

    areas: list[str] = Field(default_factory=list)
    description: str | None = None


class IntakeData(_IntakeContract):
    """Structured analysis passed from intake to the future orchestrator."""

    intent: IntentResult
    insurance_type: Literal["motor"] = "motor"
    incident: IncidentInformation = Field(default_factory=IncidentInformation)
    damage: DamageInformation = Field(default_factory=DamageInformation)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    requires_clarification: bool = False


class IntakeResponse(_IntakeContract):
    """Stable response envelope returned by the claim-intake agent."""

    request_id: str
    agent: Literal["claim_intake"] = "claim_intake"
    status: ResponseStatus
    data: IntakeData
    errors: list[str] = Field(default_factory=list)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("request_id cannot be empty")
        return value
