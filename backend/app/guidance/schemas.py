"""Data contracts and schemas for Agent 4: Guidance Agent / Reviewer Support Agent.

Follows the specifications from Section 5 of the Agent 4 Design & Implementation Guide.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


Audience = Literal["customer", "reviewer"]

GuidanceTaskType = Literal[
    "coverage_explanation",
    "policy_explanation",
    "required_documents",
    "claim_status",
    "next_steps",
    "clarification_question",
    "reviewer_summary",
    "fraud_indicator_explanation",
    "final_decision_explanation",
]

ResponseStatus = Literal["success", "insufficient_evidence", "error"]


class _GuidanceContract(BaseModel):
    """Base contract enforcing strict configuration."""

    model_config = ConfigDict(extra="forbid")


class EvidenceItem(_GuidanceContract):
    """Structured policy or guideline evidence retrieved upstream by Agent 2."""

    document_id: str
    document_name: str
    section: str
    content: str
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Evidence content cannot be empty")
        return value


class HumanDecisionContext(_GuidanceContract):
    """Verified decision made by an authorized human claims officer."""

    decision: Literal["approved", "rejected", "info_requested", "escalated"]
    officer_id: str
    officer_notes: str | None = None
    decision_date: date = Field(default_factory=date.today)
    settlement_amount: Decimal | None = None


class RiskIndicatorContext(_GuidanceContract):
    """Explainable risk indicator produced upstream by Agent 3."""

    rule_id: str
    severity: Literal["low", "medium", "high"]
    weight: int = Field(default=0, ge=0, le=100)
    title: str
    explanation: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class FraudAssessmentContext(_GuidanceContract):
    """Fraud assessment context supplied by Agent 3 for human reviewer support."""

    risk_level: Literal["low", "medium", "high"]
    risk_score: float = Field(ge=0.0, le=1.0)
    rule_score: float = Field(default=0.0, ge=0.0, le=1.0)
    ml_anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_indicators: list[RiskIndicatorContext] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    recommended_action: Literal[
        "continue_processing",
        "request_documents",
        "manual_review",
        "escalate",
    ] = "manual_review"


class GuidanceRequest(_GuidanceContract):
    """Structured input received by Agent 4."""

    request_id: str
    audience: Audience
    task_type: GuidanceTaskType
    intent: str | None = None
    claim_data: dict[str, Any] | None = None
    retrieved_evidence: list[EvidenceItem] = Field(default_factory=list)
    fraud_assessment: FraudAssessmentContext | None = None
    missing_documents: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    claim_status: str | None = None
    human_decision: HumanDecisionContext | None = None
    authorized_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("request_id cannot be empty")
        return value


class ReviewerSummarySection(_GuidanceContract):
    """Structured components of an executive summary for human claims officers."""

    claim_overview: str
    policy_findings: list[str] = Field(default_factory=list)
    risk_observations: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    reviewer_action_points: list[str] = Field(default_factory=list)


class GuidanceResponseData(_GuidanceContract):
    """Core payload data returned by Agent 4."""

    message: str
    next_steps: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    insufficient_evidence: bool = False
    automated_decision: bool = False
    reviewer_summary: ReviewerSummarySection | None = None


class GuidanceResponse(_GuidanceContract):
    """Standardized response envelope returned by Agent 4."""

    status: ResponseStatus
    response_type: GuidanceTaskType
    agent: Literal["guidance_agent"] = "guidance_agent"
    data: GuidanceResponseData
    created_at: datetime = Field(default_factory=datetime.utcnow)
    warnings: list[str] = Field(default_factory=list)
