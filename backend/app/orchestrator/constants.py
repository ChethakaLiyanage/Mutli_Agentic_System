"""Controlled values and transition rules for Orchestrator workflows."""

from __future__ import annotations

from enum import Enum


class WorkflowStatus(str, Enum):
    RECEIVED = "received"
    INTAKE_PROCESSING = "intake_processing"
    INTAKE_COMPLETE = "intake_complete"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    MANUAL_ASSISTANCE_REQUIRED = "manual_assistance_required"
    INFORMATION_RETRIEVAL = "information_retrieval"
    CLAIM_INFORMATION_RETRIEVAL = "claim_information_retrieval"
    RETRIEVAL_COMPLETE = "retrieval_complete"
    FRAUD_TRIAGE = "fraud_triage"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFORMATION_REQUIRED = "more_information_required"
    ESCALATED = "escalated"
    GUIDANCE_PROCESSING = "guidance_processing"
    GUIDANCE_GENERATION = "guidance_generation"
    AWAITING_DOCUMENTS = "awaiting_documents"
    DOCUMENTS_SUBMITTED = "documents_submitted"
    FRAUD_TRIAGE_COMPLETE = "fraud_triage_complete"
    REVIEW_SUMMARY_GENERATION = "review_summary_generation"
    AWAITING_ASSIGNMENT = "awaiting_assignment"
    UNDER_HUMAN_REVIEW = "under_human_review"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowType(str, Enum):
    INFORMATION_REQUEST = "information_request"
    CLAIM_SUBMISSION = "claim_submission"
    CLAIM_STATUS = "claim_status"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class AuditEventStatus(str, Enum):
    STARTED = "started"
    SUCCESS = "success"
    AWAITING_INPUT = "awaiting_input"
    FAILED = "failed"


INTENT_TO_WORKFLOW_TYPE: dict[str, WorkflowType] = {
    "claim_submission": WorkflowType.CLAIM_SUBMISSION,
    "policy_question": WorkflowType.INFORMATION_REQUEST,
    "coverage_question": WorkflowType.INFORMATION_REQUEST,
    "required_documents_question": WorkflowType.INFORMATION_REQUEST,
    "general_information": WorkflowType.INFORMATION_REQUEST,
    "claim_status": WorkflowType.CLAIM_STATUS,
}

CLARIFICATION_QUESTIONS: dict[str, str] = {
    "incident_type": "What happened to your vehicle?",
    "incident_date": "When did the incident happen?",
    "location": "Where did the incident happen?",
}

LOW_CONFIDENCE_CLARIFICATION_MESSAGE = (
    "I'm not fully certain what you want to do. Please clarify whether you want "
    "to submit a claim, ask about coverage, check required documents, or check "
    "a claim status."
)

MAX_CLARIFICATION_ATTEMPTS = 3
CLARIFICATION_LIMIT_MESSAGE = (
    "We still need additional information to continue. Please contact a claims "
    "officer or restart the request with more detail."
)


ALLOWED_STATUS_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.RECEIVED: frozenset(
        {WorkflowStatus.INTAKE_PROCESSING, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.INTAKE_PROCESSING: frozenset(
        {
            WorkflowStatus.INTAKE_COMPLETE,
            WorkflowStatus.AWAITING_CLARIFICATION,
            WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
            WorkflowStatus.INFORMATION_RETRIEVAL,
            WorkflowStatus.CLAIM_INFORMATION_RETRIEVAL,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.INTAKE_COMPLETE: frozenset(
        {
            WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
            WorkflowStatus.INFORMATION_RETRIEVAL,
            WorkflowStatus.CLAIM_INFORMATION_RETRIEVAL,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.AWAITING_DOCUMENTS,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_CLARIFICATION: frozenset(
        {WorkflowStatus.INTAKE_PROCESSING, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED: frozenset(),
    WorkflowStatus.INFORMATION_RETRIEVAL: frozenset(
        {
            WorkflowStatus.RETRIEVAL_COMPLETE,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.CLAIM_INFORMATION_RETRIEVAL: frozenset(
        {
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.AWAITING_DOCUMENTS,
            WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.RETRIEVAL_COMPLETE: frozenset(
        {
            WorkflowStatus.GUIDANCE_GENERATION,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.FRAUD_TRIAGE: frozenset(
        {
            WorkflowStatus.FRAUD_TRIAGE_COMPLETE,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_DOCUMENTS,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.FRAUD_TRIAGE_COMPLETE: frozenset(
        {
            WorkflowStatus.REVIEW_SUMMARY_GENERATION,
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.REVIEW_SUMMARY_GENERATION: frozenset(
        {
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_DOCUMENTS: frozenset(
        {
            WorkflowStatus.DOCUMENTS_SUBMITTED,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.DOCUMENTS_SUBMITTED: frozenset(
        {
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_ASSIGNMENT: frozenset(
        {
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.UNDER_HUMAN_REVIEW: frozenset(
        {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_HUMAN_REVIEW: frozenset(
        {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.APPROVED: frozenset(),
    WorkflowStatus.REJECTED: frozenset(),
    WorkflowStatus.MORE_INFORMATION_REQUIRED: frozenset(),
    WorkflowStatus.ESCALATED: frozenset(),
    WorkflowStatus.GUIDANCE_PROCESSING: frozenset(
        {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.GUIDANCE_GENERATION: frozenset(
        {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
}
