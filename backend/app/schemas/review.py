"""Reviewer-only request and response contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.schemas.domain import (
    ClaimContext,
    FraudAssessmentContext,
    HumanDecision,
    HumanDecisionContext,
    PolicyContext,
)
from backend.app.schemas.orchestrator import AuditEvent


class _ReviewContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HumanDecisionRequest(_ReviewContract):
    decision: HumanDecision
    reason: str = Field(min_length=3, max_length=1000)
    notes: str | None = Field(default=None, max_length=3000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("reason must contain at least 3 characters")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewQueueItem(_ReviewContract):
    workflow_id: str
    claim_id: str
    created_at: datetime
    updated_at: datetime
    claim_status: str | None = None
    incident_type: str | None = None
    incident_date: date | None = None
    location: str | None = None
    risk_level: str | None = None
    risk_score: float | None = Field(default=None, ge=0, le=1)
    recommended_action: str | None = None
    risk_indicator_count: int = 0
    missing_documents: list[str] = Field(default_factory=list)


class ReviewQueueResponse(_ReviewContract):
    items: list[ReviewQueueItem]
    limit: int
    offset: int
    returned: int


class ReviewDetailResponse(_ReviewContract):
    workflow_id: str
    status: WorkflowStatus
    claim: ClaimContext
    policy: PolicyContext | None = None
    retrieval_context: dict[str, Any] | None = None
    fraud_assessment: FraudAssessmentContext
    audit_timeline: list[AuditEvent] = Field(default_factory=list)
    human_decision: HumanDecisionContext | None = None


class HumanDecisionResponse(_ReviewContract):
    workflow_id: str
    claim_id: str
    status: WorkflowStatus
    decision: HumanDecisionContext
    message: str
