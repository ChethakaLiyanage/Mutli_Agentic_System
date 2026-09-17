from typing import TypedDict, Any, List, Optional


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