"""
Example Pydantic schema for Retrieval Agent input contract.
This is for illustration only - NOT to be implemented as functional code yet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class IncidentType(str, Enum):
    VEHICLE_COLLISION = "vehicle_collision"
    WINDSCREEN_DAMAGE = "windscreen_damage"
    FLOOD_DAMAGE = "flood_damage"
    THEFT_OR_BREAK_IN = "theft_or_break_in"


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RetrievalPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RequestMetadata(BaseModel):
    """System-generated tracking information"""
    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(..., description="Request timestamp")
    agent_version: Optional[str] = Field(None, description="Agent version")
    correlation_id: Optional[str] = Field(None, description="Distributed tracing ID")


class UserContext(BaseModel):
    """Authenticated user information"""
    user_id: str = Field(..., description="Authenticated user ID")
    session_id: Optional[str] = Field(None, description="Session identifier")
    authentication_method: Optional[str] = Field(None, description="Auth method used")
    permissions: List[str] = Field(default_factory=list, description="User permissions")


class IntentContext(BaseModel):
    """Intent information from Claim Intake Agent"""
    primary_intent: str = Field(..., description="Primary customer intent")
    intent_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    secondary_intents: List[str] = Field(default_factory=list, description="Additional intents")
    requires_clarification: bool = Field(..., description="Whether clarification needed")
    missing_fields: List[str] = Field(default_factory=list, description="Missing required fields")


class ClaimContext(BaseModel):
    """Claim details extracted from customer message"""
    incident_type: Optional[IncidentType] = Field(None, description="Type of incident")
    incident_date_text: Optional[str] = Field(None, description="Original date wording")
    normalized_incident_date: Optional[str] = Field(None, description="ISO normalized date")
    incident_location: Optional[str] = Field(None, description="Location of incident")
    damage_areas: List[str] = Field(default_factory=list, description="Damaged vehicle areas")
    extracted_entities: List[dict] = Field(default_factory=list, description="DATE/TIME/LOCATION entities")
    insurance_type: str = Field(default="motor", description="Line of business")


class PolicyContext(BaseModel):
    """Policy information"""
    policy_id: Optional[str] = Field(None, description="Internal policy identifier")
    policy_number: Optional[str] = Field(None, description="Human-readable policy number")
    policy_status: Optional[PolicyStatus] = Field(None, description="Policy status")
    coverage_details: Optional[dict] = Field(None, description="Current coverage information")
    policy_start_date: Optional[str] = Field(None, description="Policy effective date")
    policy_end_date: Optional[str] = Field(None, description="Policy expiration date")


class ClaimLookupContext(BaseModel):
    """Identifiers for looking up specific claims"""
    claim_id: Optional[str] = Field(None, description="Internal claim identifier")
    claim_reference: Optional[str] = Field(None, description="Human-readable claim reference")
    vehicle_id: Optional[str] = Field(None, description="Vehicle identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")


class DocumentReferences(BaseModel):
    """References to uploaded documents"""
    uploaded_document_ids: List[str] = Field(default_factory=list, description="Document IDs")
    document_types_present: List[str] = Field(default_factory=list, description="Types of documents uploaded")
    pending_document_verification: List[str] = Field(default_factory=list, description="Documents awaiting verification")


class RetrievalOptions(BaseModel):
    """Configuration for retrieval behavior"""
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    include_historical: bool = Field(default=False, description="Include historical records")
    historical_days_limit: int = Field(default=0, ge=0, description="Days back to look for history")
    priority: RetrievalPriority = Field(default=RetrievalPriority.NORMAL, description="Retrieval priority")
    timeout_seconds: int = Field(default=5, ge=1, le=30, description="Retrieval timeout in seconds")


class RetrievalRequest(BaseModel):
    """
    Complete input contract for the Retrieval Agent.

    This represents what the Retrieval Agent should receive from the Orchestrator.
    """
    request_metadata: RequestMetadata
    user_context: UserContext
    intent_context: IntentContext
    claim_context: ClaimContext
    policy_context: PolicyContext
    claim_lookup_context: ClaimLookupContext
    document_references: DocumentReferences
    retrieval_options: RetrievalOptions

    class Config:
        # Ensure extra fields are forbidden for strict contract adherence
        extra = "forbid"

    # Example validation methods would go here in actual implementation
    # but are omitted for this step as we're only defining the contract

    # def validate_authorization(self):
    #     """Verify user has permission to access requested resources"""
    #     pass

    # def validate_intent_requirements(self):
    #     """Check intent-specific minimum requirements"""
    #     pass