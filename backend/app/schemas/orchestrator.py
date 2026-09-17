"""Request, response, error, and audit contracts for the Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.orchestrator.constants import (
    AuditEventStatus,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.schemas.intake import IntakeResponse


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _OrchestratorContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrchestratorRequest(_OrchestratorContract):
    """Untrusted user input accepted before authentication is introduced."""

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


class OrchestratorError(_OrchestratorContract):
    """A controlled workflow error safe to pass between internal steps."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    step: str | None = None


class AuditEvent(_OrchestratorContract):
    """A non-sensitive record of one workflow lifecycle event."""

    step: str = Field(min_length=1)
    status: AuditEventStatus
    message: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=_utc_now)


class ClarificationResponse(_OrchestratorContract):
    """A structured pause indicating that additional user input is required."""

    request_id: str
    status: WorkflowStatus = WorkflowStatus.AWAITING_CLARIFICATION
    workflow_type: WorkflowType = WorkflowType.CLARIFICATION
    intake_result: IntakeResponse | None = None
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    reason: str | None = None
    requires_clarification: Literal[True] = True
    audit_trail: list[AuditEvent] = Field(default_factory=list)


class OrchestratorResponse(_OrchestratorContract):
    """Current structured result returned by the central workflow controller."""

    request_id: str
    status: WorkflowStatus
    workflow_type: WorkflowType
    intake_result: IntakeResponse | None = None
    retrieval_result: dict[str, Any] | None = None
    fraud_result: dict[str, Any] | None = None
    human_review_result: dict[str, Any] | None = None
    guidance_result: dict[str, Any] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    errors: list[OrchestratorError] = Field(default_factory=list)
    audit_trail: list[AuditEvent] = Field(default_factory=list)
