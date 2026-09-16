from datetime import date
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field


class ClaimData(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str

    policy_number: str
    claim_type: str
    incident_date: date
    incident_time: str | None = None
    incident_location: str | None = None
    claimed_amount: Decimal
    incident_description: str

    police_report_number: str | None = None


class PolicyData(BaseModel):
    policy_id: str
    policy_number: str
    customer_id: str
    status: Literal["active", "expired", "cancelled"]
    start_date: date
    end_date: date
    coverage_details: dict[str, Any] = {}


class DocumentFacts(BaseModel):
    document_id: str
    document_type: Literal[
        "police_report",
        "repair_estimate",
        "invoice",
        "photo",
        "other"
    ]

    incident_date: date | None = None
    claim_amount: Decimal | None = None
    incident_type: str | None = None
    police_report_number: str | None = None
    extracted_text: str | None = None


class RiskIndicator(BaseModel):
    rule_id: str
    severity: Literal["low", "medium", "high"]
    weight: int = Field(ge=0, le=100)

    title: str
    explanation: str
    evidence: dict[str, Any] = {}


class FraudAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_score: float = Field(ge=0.0, le=1.0)

    rule_score: float = Field(ge=0.0, le=1.0)
    ml_anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)

    risk_indicators: list[RiskIndicator]
    missing_documents: list[str]

    recommended_action: Literal[
        "continue_processing",
        "request_documents",
        "manual_review",
        "escalate"
    ]

    automated_decision: bool = False
    rules_version: str = "1.0.0"
    model_version: str | None = None