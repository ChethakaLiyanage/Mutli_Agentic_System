"""Safety rules and boundary enforcement for Agent 4.

Implements Section 7 (Responsible AI, Security, and Safety Rules) of the design guide.
Enforces non-negotiable boundaries: AI = assistance, Human = authority.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from .schemas import Audience, GuidanceRequest, GuidanceResponseData, HumanDecisionContext


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
        msg = (
            "I could not find sufficient information in the available insurance policy documents "
            "to answer your question with complete confidence. "
            "To ensure accuracy, a claims officer will review your request, or you may contact our customer support."
        )
        steps = [
            "Wait for claims officer follow-up",
            "Contact customer support if you require immediate clarification",
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
        requires_human_review=True,
        insufficient_evidence=True,
        automated_decision=False,
    )
