"""Customer-facing policy and coverage response schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PolicySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    policy_id: str
    policy_number: str
    insurance_type: str = "motor"
    coverage_type: str = "full"
    status: str
    start_date: date
    end_date: date
    coverage_details: dict[str, Any] = Field(default_factory=dict)
    exclusions: list[Any] = Field(default_factory=list)


class MyPoliciesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    policies: list[PolicySummaryResponse]
    total: int