"""Pydantic schemas for customer-facing and internal claim queries."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.document import ClaimDocumentResponse


class ClaimSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim_id: str
    claim_reference: str | None = None
    workflow_id: str | None = None
    policy_id: str | None = None
    policy_number: str | None = None
    incident_type: str | None = None
    incident_date: date | None = None
    incident_location: str | None = None
    incident_description: str | None = None
    claimed_amount: float | None = None
    claim_status: str | None = None
    workflow_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ClaimDetailCustomerResponse(BaseModel):
    """Customer-safe detailed claim view.

    PRIVACY INVARIANT: This schema strictly excludes any internal staff summaries,
    risk scores, risk levels, fraud triage details, or machine learning indicators.
    """

    model_config = ConfigDict(extra="ignore")

    claim_id: str
    claim_reference: str | None = None
    workflow_id: str | None = None
    policy_id: str | None = None
    policy_number: str | None = None
    incident_type: str | None = None
    incident_date: date | None = None
    incident_location: str | None = None
    incident_description: str | None = None
    claimed_amount: float | None = None
    claim_status: str | None = None
    workflow_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    documents: list[ClaimDocumentResponse] = Field(default_factory=list)
    decision: str | None = None
    rejection_reason: str | None = None
    decided_at: datetime | None = None
    customer_explanation: str | None = None


class MyClaimsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claims: list[ClaimSummaryResponse]
    total: int
