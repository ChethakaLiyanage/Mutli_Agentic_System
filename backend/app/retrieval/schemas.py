from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: str


class IntentContext(BaseModel):
    intent: Literal[
        "claim_submission",
        "policy_question",
        "coverage_question",
        "required_documents_question",
        "claim_status",
        "general_information",
    ]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ClaimContext(BaseModel):
    incident_type: str | None = None
    incident_date: str | None = None
    incident_location: str | None = None
    damage_areas: list[str] = Field(default_factory=list)


class PolicyLookupContext(BaseModel):
    policy_id: str | None = None
    policy_number: str | None = None


class ClaimLookupContext(BaseModel):
    claim_id: str | None = None
    claim_reference: str | None = None


class DocumentReference(BaseModel):
    document_id: str
    document_type: str | None = None


class RetrievalRequest(BaseModel):
    request_id: str
    query: str | None = None

    user_context: UserContext
    intent_context: IntentContext

    claim_context: ClaimContext | None = None
    policy_context: PolicyLookupContext | None = None
    claim_lookup: ClaimLookupContext | None = None

    document_references: list[DocumentReference] = Field(
        default_factory=list
    )


class PolicyRecord(BaseModel):
    policy_id: str
    policy_number: str
    customer_id: str

    status: str
    start_date: str
    end_date: str

    coverage_details: dict[str, Any] = Field(
        default_factory=dict
    )


class ClaimRecord(BaseModel):
    claim_id: str
    claim_reference: str

    customer_id: str
    policy_id: str

    claim_type: str
    incident_date: str
    incident_location: str | None = None

    claimed_amount: float | None = None
    status: str | None = None


class HistoricalClaim(BaseModel):
    claim_id: str
    claim_reference: str

    claim_type: str
    incident_date: str

    claimed_amount: float | None = None
    status: str | None = None


class DocumentEvidence(BaseModel):
    document_id: str
    document_type: str

    file_name: str | None = None

    incident_date: str | None = None
    claim_amount: float | None = None
    incident_type: str | None = None
    police_report_number: str | None = None

    extracted_text: str | None = None


class KnowledgeEvidence(BaseModel):
    evidence_id: str

    source_id: str
    source_title: str

    section: str | None = None
    document_type: str | None = None

    content: str

    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


KnowledgeDocumentType = Literal[
    "policy_document",
    "policy_manual",
    "procedure_guide",
    "guideline",
    "manual",
]


class KnowledgeChunk(BaseModel):
    """Typed durable representation of one controlled-corpus chunk."""

    chunk_id: str
    source_document_id: str
    source_title: str
    insurance_type: str = "motor"
    document_type: KnowledgeDocumentType
    section: str | None = None
    content: str
    normalized_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RetrievalError(BaseModel):
    error_code: str
    message: str
    source: str
    retryable: bool = False


class RetrievalResult(BaseModel):
    policy_data: PolicyRecord | None = None
    claim_record: ClaimRecord | None = None

    historical_claims: list[HistoricalClaim] = Field(
        default_factory=list
    )

    document_facts: list[DocumentEvidence] = Field(
        default_factory=list
    )

    knowledge_evidence: list[KnowledgeEvidence] = Field(
        default_factory=list
    )

    missing_evidence: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    component_errors: list[RetrievalError] = Field(
        default_factory=list,
        exclude=True,
    )


class RetrievalResponse(BaseModel):
    request_id: str

    status: Literal[
        "success",
        "partial_success",
        "no_results",
        "failed",
    ]

    result: RetrievalResult

    errors: list[RetrievalError] = Field(
        default_factory=list
    )
