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
    context_workflow_id: str | None = Field(default=None, max_length=100)

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

    @field_validator("context_workflow_id")
    @classmethod
    def validate_context_workflow_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ClarificationRequest(OrchestratorRequest):
    """A follow-up message for an existing clarification workflow."""


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
    workflow_id: str
    claim_id: str | None = None
    status: WorkflowStatus = WorkflowStatus.AWAITING_CLARIFICATION
    workflow_type: WorkflowType = WorkflowType.CLARIFICATION
    intake_result: IntakeResponse | None = None
    missing_fields: list[str] = Field(default_factory=list)
    pending_field: str | None = None
    pending_question: str | None = None
    questions: list[str] = Field(default_factory=list)
    reason: str | None = None
    message: str | None = None
    guidance_result: dict[str, Any] | None = None
    requires_clarification: Literal[True] = True
    audit_trail: list[AuditEvent] = Field(default_factory=list)


class OrchestratorResponse(_OrchestratorContract):
    """Current structured result returned by the central workflow controller."""

    request_id: str
    workflow_id: str
    claim_id: str | None = None
    status: WorkflowStatus
    workflow_type: WorkflowType
    intake_result: IntakeResponse | None = None
    retrieval_result: dict[str, Any] | None = None
    retrieval_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
    fraud_result: dict[str, Any] | None = None
    fraud_risk_level: str | None = None
    recommended_next_action: str | None = None
    risk_indicator_count: int = 0
    missing_document_summary: list[str] = Field(default_factory=list)
    human_review_result: dict[str, Any] | None = None
    guidance_result: dict[str, Any] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    pending_field: str | None = None
    pending_question: str | None = None
    missing_required_documents: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    errors: list[OrchestratorError] = Field(default_factory=list)
    pending_claim_workflow_id: str | None = None
    audit_trail: list[AuditEvent] = Field(default_factory=list)
