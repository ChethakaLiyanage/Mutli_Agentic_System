"""Controlled values and transition rules for Orchestrator workflows."""

from __future__ import annotations

from enum import Enum


class WorkflowStatus(str, Enum):
    RECEIVED = "received"
    INTAKE_PROCESSING = "intake_processing"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    INFORMATION_RETRIEVAL = "information_retrieval"
    FRAUD_TRIAGE = "fraud_triage"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    GUIDANCE_PROCESSING = "guidance_processing"
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


ALLOWED_STATUS_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.RECEIVED: frozenset(
        {WorkflowStatus.INTAKE_PROCESSING, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.INTAKE_PROCESSING: frozenset(
        {
            WorkflowStatus.AWAITING_CLARIFICATION,
            WorkflowStatus.INFORMATION_RETRIEVAL,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_CLARIFICATION: frozenset(
        {WorkflowStatus.INTAKE_PROCESSING, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.INFORMATION_RETRIEVAL: frozenset(
        {
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.FRAUD_TRIAGE: frozenset(
        {
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.AWAITING_HUMAN_REVIEW: frozenset(
        {
            WorkflowStatus.GUIDANCE_PROCESSING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.GUIDANCE_PROCESSING: frozenset(
        {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
}
