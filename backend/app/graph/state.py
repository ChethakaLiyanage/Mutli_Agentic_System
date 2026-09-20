"""Durable structured state shared across Orchestrator and multi-agent workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.schemas.intake import IntakeResponse
from backend.app.schemas.orchestrator import AuditEvent, OrchestratorError
from backend.app.schemas.domain import ClaimContext


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowState(BaseModel):
    """Serializable state that can survive across multiple workflow steps."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    workflow_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(max_length=200)
    last_request_id: str = Field(max_length=200)
    raw_text: str = Field(max_length=3000)
    original_text: str = Field(max_length=3000)
    accumulated_text: str = Field(max_length=12000)
    clarification_count: int = Field(default=0, ge=0)

    authenticated_user_id: str | None = None
    authenticated_user_role: str | None = None

    intake_result: IntakeResponse | None = None
    claim_context: ClaimContext | None = None
    retrieval_result: dict[str, Any] | None = None
    fraud_result: dict[str, Any] | None = None
    human_review_result: dict[str, Any] | None = None
    guidance_result: dict[str, Any] | None = None
    reviewer_guidance_result: dict[str, Any] | None = None

    workflow_type: WorkflowType = WorkflowType.UNKNOWN
    current_status: WorkflowStatus = WorkflowStatus.RECEIVED

    missing_fields: list[str] = Field(default_factory=list)
    requires_clarification: bool = False

    errors: list[OrchestratorError] = Field(default_factory=list)
    audit_trail: list[AuditEvent] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator(
        "workflow_id",
        "request_id",
        "last_request_id",
        "raw_text",
        "original_text",
        "accumulated_text",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be empty")
        return value


class ClaimsState(TypedDict, total=False):
    """Shared state for the multi-agent insurance claims workflow."""

    # Identifiers
    request_id: str
    user_id: str

    # Intent information from Claim Intake Agent
    intent: str
    intent_confidence: float

    # Claim context
    incident_type: Optional[str]
    incident_date: Optional[str]
    incident_location: Optional[str]
    damage_areas: List[str]

    # Policy identifiers
    policy_id: Optional[str]
    policy_number: Optional[str]

    # Claim identifiers
    claim_id: Optional[str]
    claim_reference: Optional[str]

    # Document references
    document_references: List[dict[str, Any]]

    # Retrieval results
    retrieval_response: Optional[dict[str, Any]]
    retrieval_status: Optional[str]

    # Fraud detection results
    fraud_assessment: Optional[dict[str, Any]]

    # Additional fields for future agents
    reviewer_notes: Optional[str]
    final_decision: Optional[str]
    guidance_response: Optional[dict[str, Any]]
    next_step: Optional[str]

