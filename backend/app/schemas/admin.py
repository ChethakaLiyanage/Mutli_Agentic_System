"""Schemas for admin-side customer management and policy assignment."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PolicyCategory(str, Enum):
    FULL_COMPREHENSIVE = "full_comprehensive"
    PARTIAL_COMPREHENSIVE = "partial_comprehensive"
    THIRD_PARTY = "third_party"


class AdminCustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    email: EmailStr
    password: str = Field(min_length=8, description="Temporary password for customer")
    policy_type: PolicyCategory


class AdminCustomerResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    email: str
    name: str | None = None
    role: Literal["customer"] = "customer"
    policy_id: str
    policy_number: str
    policy_type: PolicyCategory
    created_at: datetime


class AdminCustomerListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customers: list[AdminCustomerResponse]
    total: int
