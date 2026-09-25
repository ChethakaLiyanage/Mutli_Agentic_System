"""Customer-safe semantic view of authoritative workflow statuses.

The mapping contains facts rather than display prose. Agent 4 owns normal
customer wording; deterministic guidance consumes the same facts only when the
configured provider is unavailable.
"""

from __future__ import annotations

from typing import Any

from backend.app.orchestrator.constants import WorkflowStatus


_STATUS_SEMANTICS: dict[WorkflowStatus, dict[str, Any]] = {
    WorkflowStatus.AWAITING_DOCUMENTS: {
        "customer_safe_status": "documents_required",
        "submitted": False,
        "customer_action_required": True,
        "action": "upload_required_documents",
        "next_step": "submit_claim",
    },
    WorkflowStatus.DOCUMENTS_SUBMITTED: {
        "customer_safe_status": "submitted",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "processing",
    },
    WorkflowStatus.FRAUD_TRIAGE: {
        "customer_safe_status": "processing",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_assignment",
    },
    WorkflowStatus.FRAUD_TRIAGE_COMPLETE: {
        "customer_safe_status": "processing",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_assignment",
    },
    WorkflowStatus.REVIEW_SUMMARY_GENERATION: {
        "customer_safe_status": "processing",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_assignment",
    },
    WorkflowStatus.AWAITING_ASSIGNMENT: {
        "customer_safe_status": "awaiting_officer_assignment",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_assignment",
    },
    WorkflowStatus.AWAITING_HUMAN_REVIEW: {
        "customer_safe_status": "awaiting_officer_review",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_review",
    },
    WorkflowStatus.UNDER_HUMAN_REVIEW: {
        "customer_safe_status": "under_officer_review",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "officer_decision",
    },
    WorkflowStatus.MORE_INFORMATION_REQUIRED: {
        "customer_safe_status": "more_information_required",
        "submitted": True,
        "customer_action_required": True,
        "action": "provide_requested_information",
        "next_step": "submit_requested_information",
    },
    WorkflowStatus.ESCALATED: {
        "customer_safe_status": "additional_review",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "specialist_review",
    },
    WorkflowStatus.APPROVED: {
        "customer_safe_status": "approved",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "follow_officer_instructions",
    },
    WorkflowStatus.REJECTED: {
        "customer_safe_status": "rejected",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": "review_officer_reason",
    },
    WorkflowStatus.COMPLETED: {
        "customer_safe_status": "completed",
        "submitted": True,
        "customer_action_required": False,
        "action": None,
        "next_step": None,
    },
}


def customer_status_context(
    status: WorkflowStatus,
    *,
    workflow_id: str,
    claim_id: str | None,
    event: str,
) -> dict[str, Any]:
    """Return the single customer-safe semantic representation of a status."""

    semantics = _STATUS_SEMANTICS.get(
        status,
        {
            "customer_safe_status": "processing",
            "submitted": False,
            "customer_action_required": False,
            "action": None,
            "next_step": "processing",
        },
    )
    return {
        "event": event,
        "workflow_id": workflow_id,
        "claim_id": claim_id,
        "workflow_status": status.value,
        **semantics,
    }
