"""Canonical domain contracts shared across backend agents.

These models define the integration boundary only. Existing agent-specific
schemas remain in place until their services are connected to the live
Orchestrator in later integration steps.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _DomainContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class IncidentType(str, Enum):
    VEHICLE_COLLISION = "vehicle_collision"
    WINDSCREEN_DAMAGE = "windscreen_damage"
    FLOOD_DAMAGE = "flood_damage"
    THEFT_OR_BREAK_IN = "theft_or_break_in"


_INCIDENT_TYPE_ALIASES: dict[str, IncidentType] = {
    incident.value: incident for incident in IncidentType
}
_INCIDENT_TYPE_ALIASES.update(
    {
        "motor_accident": IncidentType.VEHICLE_COLLISION,
        "vehicle_theft": IncidentType.THEFT_OR_BREAK_IN,
    }
)


def normalize_incident_type(
    value: str | IncidentType | None,
) -> IncidentType | None:
    """Convert a supported current or legacy incident label to the canonical enum."""

    if value is None or isinstance(value, IncidentType):
        return value
    try:
        return _INCIDENT_TYPE_ALIASES[value]
    except KeyError as error:
        raise ValueError(f"Unsupported incident type: {value}") from error


def to_legacy_fraud_claim_type(value: IncidentType) -> str:
    """Map canonical incident types to legacy fraud labels where they exist."""

    return {
        IncidentType.VEHICLE_COLLISION: "motor_accident",
        IncidentType.THEFT_OR_BREAK_IN: "vehicle_theft",
    }.get(value, value.value)


class DocumentType(str, Enum):
    POLICE_REPORT = "police_report"
    REPAIR_ESTIMATE = "repair_estimate"
    CLAIM_FORM = "claim_form"
    VEHICLE_REGISTRATION = "vehicle_registration"
    DAMAGE_PHOTO = "damage_photo"
    IDENTITY_DOCUMENT = "identity_document"
    POLICY_DOCUMENT = "policy_document"
    INVOICE = "invoice"
    PHOTO = "photo"
    POLICY_MANUAL = "policy_manual"
    PROCEDURE_GUIDE = "procedure_guide"
    GUIDELINE = "guideline"
    MANUAL = "manual"
    OTHER = "other"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedAction(str, Enum):
    CONTINUE_PROCESSING = "continue_processing"
    REQUEST_DOCUMENTS = "request_documents"
    MANUAL_REVIEW = "manual_review"
    ESCALATE = "escalate"


class HumanDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_MORE_INFORMATION = "request_more_information"
    ESCALATE = "escalate"


class IncidentContext(_DomainContract):
    incident_type: IncidentType | None = None
    incident_date: date | None = None
    incident_location: str | None = None
    incident_description: str | None = None


class DamageContext(_DomainContract):
    damage_areas: list[str] = Field(default_factory=list)
    damage_description: str | None = None


class DocumentReference(_DomainContract):
    document_id: str
    document_type: DocumentType | None = None


class ClaimContext(_DomainContract):
    """Canonical claim handoff; unavailable facts deliberately remain ``None``."""

    claim_id: str | None = None
    claim_reference: str | None = None
    workflow_id: str | None = None
    customer_id: str | None = None
    policy_id: str | None = None
    policy_number: str | None = None
    vehicle_registration: str | None = None
    incident_type: IncidentType | None = None
    incident_date: date | None = None
    incident_location: str | None = None
    incident_description: str | None = None
    damage_areas: list[str] = Field(default_factory=list)
    claimed_amount: Decimal | None = None
    police_report_number: str | None = None
    claim_status: str | None = None
    document_references: list[DocumentReference] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicyContext(_DomainContract):
    policy_id: str | None = None
    policy_number: str | None = None
    customer_id: str | None = None
    status: str | None = None
    coverage_type: str = "full"
    start_date: date | None = None
    end_date: date | None = None
    coverage_details: dict[str, Any] = Field(default_factory=dict)


class DocumentFact(_DomainContract):
    document_id: str
    document_type: DocumentType
    file_name: str | None = None
    incident_date: date | None = None
    claim_amount: Decimal | None = None
    incident_type: IncidentType | None = None
    police_report_number: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(_DomainContract):
    evidence_id: str
    source_title: str
    section: str | None = None
    content: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskIndicator(_DomainContract):
    rule_id: str
    severity: RiskSeverity
    weight: int = Field(ge=0, le=100)
    title: str
    explanation: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class FraudAssessmentContext(_DomainContract):
    """Risk-triage output; this model never represents proven fraud."""

    assessment_id: str | None = None
    claim_id: str | None = None
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    indicators: list[RiskIndicator] = Field(default_factory=list)
    recommended_action: RecommendedAction
    missing_documents: list[DocumentType] = Field(default_factory=list)
    rule_score: float = Field(default=0.0, ge=0.0, le=1.0)
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    automated_decision: Literal[False] = False
    rules_version: str | None = None
    model_version: str | None = None
    warnings: list[str] = Field(default_factory=list)


class HumanDecisionContext(_DomainContract):
    decision_id: str | None = None
    workflow_id: str | None = None
    claim_id: str | None = None
    decision: HumanDecision
    reviewer_id: str
    reviewer_role: str | None = None
    reason: str | None = None
    notes: str | None = None
    decided_at: datetime | None = None
    requested_information: list[str] = Field(default_factory=list)
    settlement_amount: Decimal | None = None
