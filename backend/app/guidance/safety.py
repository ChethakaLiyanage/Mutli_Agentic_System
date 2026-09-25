"""Safety rules and boundary enforcement for Agent 4.

Implements Section 7 (Responsible AI, Security, and Safety Rules) of the design guide.
Enforces non-negotiable boundaries: AI = assistance, Human = authority.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from backend.app.guidance.schemas import (
    Audience,
    GuidanceRequest,
    GuidanceResponseData,
    HumanDecisionContext,
)


# Forbidden phrases when no verified human decision is present
_FORBIDDEN_APPROVAL_PATTERNS = [
    re.compile(r"(?:your|the)\s+claim\s+is\s+(?:officially\s+)?approved", re.IGNORECASE),
    re.compile(r"(?:we|i)\s+have\s+approved\s+(?:your|this)\s+claim", re.IGNORECASE),
    re.compile(r"(?:the\s+insurer|company)\s+will\s+(?:definitely\s+)?pay\s+rs", re.IGNORECASE),
    re.compile(r"coverage\s+is\s+guaranteed", re.IGNORECASE),
    re.compile(r"definitely\s+covered", re.IGNORECASE),
]

_FORBIDDEN_REJECTION_PATTERNS = [
    re.compile(r"(?:your|the)\s+claim\s+is\s+(?:officially\s+)?rejected", re.IGNORECASE),
    re.compile(r"(?:your|the)\s+claim\s+has\s+been\s+(?:denied|rejected)", re.IGNORECASE),
    re.compile(r"(?:we|i)\s+have\s+rejected\s+(?:your|this)\s+claim", re.IGNORECASE),
]

# Defamatory or definitive fraud accusations that must NEVER be produced
_FORBIDDEN_FRAUD_ACCUSATIONS = [
    re.compile(r"you\s+committed\s+fraud", re.IGNORECASE),
    re.compile(r"claim\s+is\s+fraudulent", re.IGNORECASE),
    re.compile(r"fraud\s+confirmed", re.IGNORECASE),
    re.compile(r"fraudulent\s+claimant", re.IGNORECASE),
    re.compile(r"guilty\s+of\s+fraud", re.IGNORECASE),
    re.compile(r"intentionally\s+defrauding", re.IGNORECASE),
]

# Internal technical phrases that must not leak to customers
_CUSTOMER_LEAKAGE_PATTERNS = [
    re.compile(r"rule_score\s*[:=]", re.IGNORECASE),
    re.compile(r"ml_anomaly_score\s*[:=]", re.IGNORECASE),
    re.compile(r"fraud\s+weight\s*[:=]?\s*\d+", re.IGNORECASE),
    re.compile(r"internal\s+investigator\s+notes?", re.IGNORECASE),
]

_PERSONAL_IDENTIFIER_PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)(?:\+?94|0)?7\d{8}(?!\d)"),
    re.compile(
        r"\b(?:vehicle\s+(?:registration|number)|registration\s+number|"
        r"policy\s+number|claim\s+number)\s*(?:is|:|=)\s*"
        r"[A-Z0-9][A-Z0-9-]{2,}\b",
        re.IGNORECASE,
    ),
]


class SafetyCheckResult(NamedTuple):
    """Result of post-generation safety verification."""

    is_safe: bool
    violations: list[str]
    sanitized_message: str | None = None


def check_decision_boundaries(
    text: str,
    human_decision: HumanDecisionContext | None,
) -> list[str]:
    """Check whether generated text violates the human decision boundary."""
    violations: list[str] = []

    # If no verified human decision exists, Agent 4 cannot approve
    if not human_decision or human_decision.decision != "approved":
        for pattern in _FORBIDDEN_APPROVAL_PATTERNS:
            if pattern.search(text):
                violations.append(
                    f"Decision boundary violation: Generated unauthorized approval statement matching '{pattern.pattern}'"
                )

    # If no verified human decision exists, Agent 4 cannot reject
    if not human_decision or human_decision.decision != "rejected":
        for pattern in _FORBIDDEN_REJECTION_PATTERNS:
            if pattern.search(text):
                violations.append(
                    f"Decision boundary violation: Generated unauthorized rejection statement matching '{pattern.pattern}'"
                )

    # Agent 4 must NEVER make definitive fraud accusations under any circumstance
    for pattern in _FORBIDDEN_FRAUD_ACCUSATIONS:
        if pattern.search(text):
            violations.append(
                f"Fraud language violation: Generated definitive fraud accusation matching '{pattern.pattern}'. "
                "Agent 4 must describe indicators neutrally for reviewer inspection."
            )

    return violations


def check_customer_role_leakage(text: str, audience: Audience) -> list[str]:
    """Ensure internal fraud weights and scoring parameters do not leak to customers."""
    violations: list[str] = []

    if audience == "customer":
        for pattern in _CUSTOMER_LEAKAGE_PATTERNS:
            if pattern.search(text):
                violations.append(
                    f"Role leakage violation: Customer message contains internal scoring/weights matching '{pattern.pattern}'"
                )

    return violations


def check_sensitive_context_disclosure(
    text: str,
    request: GuidanceRequest,
) -> list[str]:
    """Reject identifier-shaped output for privacy-minimization tasks."""

    if request.task_type not in {
        "sensitive_context_recall",
        "sensitive_context_notice",
    }:
        return []
    return [
        "Privacy minimization violation: guidance contained an identifying value."
        for pattern in _PERSONAL_IDENTIFIER_PATTERNS
        if pattern.search(text)
    ]


def enforce_safety(
    data: GuidanceResponseData,
    request: GuidanceRequest,
) -> SafetyCheckResult:
    """Run comprehensive safety checks on the generated guidance response data."""
    all_violations: list[str] = []

    # Check the main message
    decision_violations = check_decision_boundaries(
        text=data.message,
        human_decision=request.human_decision,
    )
    all_violations.extend(decision_violations)

    # Check for customer data leakage
    leakage_violations = check_customer_role_leakage(
        text=data.message,
        audience=request.audience,
    )
    all_violations.extend(leakage_violations)
    all_violations.extend(check_sensitive_context_disclosure(data.message, request))

    # If reviewer summary exists, check that as well
    if data.reviewer_summary:
        summary_text = " ".join([
            data.reviewer_summary.claim_overview,
            *data.reviewer_summary.risk_observations,
            *data.reviewer_summary.reviewer_action_points,
        ])
        summary_violations = check_decision_boundaries(
            text=summary_text,
            human_decision=request.human_decision,
        )
        all_violations.extend(summary_violations)

    if all_violations:
        return SafetyCheckResult(
            is_safe=False,
            violations=all_violations,
            sanitized_message=None,
        )

    return SafetyCheckResult(
        is_safe=True,
        violations=[],
        sanitized_message=data.message,
    )


def build_insufficient_evidence_fallback(
    request: GuidanceRequest,
    custom_reason: str | None = None,
) -> GuidanceResponseData:
    """Standard, safe fallback response when retrieval finds insufficient evidence.

    Follows Section 6.1 and 11.4 of the design guide.
    """
    if request.audience == "customer":
        warning_codes = set(request.retrieval_warnings)
        if "matching_active_policy_document_not_found" in warning_codes:
            msg = (
                "I found your active policy assignment, but there is no active "
                "customer policy document for its category in the knowledge base."
            )
            steps = ["Ask an administrator to verify the active policy document"]
        elif "requested_policy_document_not_found" in warning_codes:
            msg = (
                "There is no active customer document for the requested policy "
                "category in the knowledge base."
            )
            steps = ["Ask an administrator to verify that policy category's document"]
        elif "requested_policy_evidence_not_found" in warning_codes:
            msg = (
                "I found the active document for the requested policy category, "
                "but it did not contain relevant evidence for this question."
            )
            steps = ["Ask a more specific question about that policy category"]
        elif "relevant_policy_evidence_not_found" in warning_codes:
            msg = (
                "I found the active document for your policy category, but it did "
                "not contain relevant evidence for this question."
            )
            steps = ["Ask a more specific coverage question or review your policy schedule"]
        elif "policy_not_found" in warning_codes:
            msg = "I couldn't find an active motor policy linked to your account."
            steps = ["Ask a claims officer to verify your policy assignment"]
        else:
            msg = (
                "I couldn't find enough information in the available policy documents "
                "to confirm the answer reliably."
            )
            steps = [
                "Try asking another motor insurance question",
                "Check your policy documents for more details",
            ]
    else:
        reason_detail = f" ({custom_reason})" if custom_reason else ""
        msg = (
            f"Reviewer notice: Insufficient authoritative policy evidence was retrieved for this inquiry{reason_detail}. "
            "Manual review of the policy documentation and claim files is required."
        )
        steps = [
            "Review full policy terms in the underwriting database",
            "Verify coverage clauses directly with underwriting department",
        ]

    return GuidanceResponseData(
        message=msg,
        next_steps=steps,
        evidence_used=[],
        requires_human_review=request.audience != "customer",
        insufficient_evidence=True,
        automated_decision=False,
    )
