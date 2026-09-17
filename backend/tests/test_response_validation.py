"""Tests for Safety Rules, Decision Boundaries, and Response Validation (Section 7, 11.1, 11.6, 11.7)."""

from __future__ import annotations

import pytest
from backend.app.guidance.response_validator import validate_guidance_response
from backend.app.guidance.safety import (
    check_customer_role_leakage,
    check_decision_boundaries,
    enforce_safety,
)
from backend.app.guidance.schemas import (
    EvidenceItem,
    GuidanceRequest,
    GuidanceResponseData,
    HumanDecisionContext,
)


def test_automated_decision_true_is_rejected():
    """automated_decision must never be True (Section 5.2, 7)."""
    request = GuidanceRequest(
        request_id="REQ-SAFETY-01",
        audience="customer",
        task_type="claim_status",
    )
    data = GuidanceResponseData(
        message="Your claim is being processed.",
        automated_decision=True,  # VIOLATION
    )
    result = validate_guidance_response(data, request)
    assert not result.is_valid
    assert any("automated_decision must strictly be False" in err for err in result.errors)


def test_unauthorized_claim_approval_is_caught():
    """Agent 4 cannot claim approval without verified human decision (Section 7.1, 7.2, 11.6)."""
    text = "Great news! Your claim is approved and we will pay Rs. 150000."
    violations = check_decision_boundaries(text=text, human_decision=None)
    assert len(violations) > 0
    assert any("Decision boundary violation" in v for v in violations)


def test_authorized_human_decision_approval_is_permitted():
    """When a verified human approval exists, reporting it is allowed (Section 7.2, 11.8)."""
    human_dec = HumanDecisionContext(
        decision="approved",
        officer_id="OFFICER-789",
        officer_notes="All documents verified and coverage applies.",
    )
    text = "The claims officer has approved your claim for accidental bodywork repair."
    violations = check_decision_boundaries(text=text, human_decision=human_dec)
    assert len(violations) == 0


def test_fraud_accusation_is_strictly_forbidden():
    """Definitive fraud accusations are forbidden under all circumstances (Section 7.1, 7.2)."""
    text = "You committed fraud by inflating the repair estimate."
    violations = check_decision_boundaries(text=text, human_decision=None)
    assert any("Fraud language violation" in v for v in violations)


def test_customer_role_leakage_of_fraud_weights_is_prevented():
    """Customer output must never expose internal scoring formulas or weights (Section 7.3, 11.7)."""
    text = "Your claim was flagged with rule_score: 0.85 and fraud weight: 30."
    violations = check_customer_role_leakage(text=text, audience="customer")
    assert len(violations) > 0
    assert any("Role leakage violation" in v for v in violations)


def test_reviewer_mode_allows_internal_inspection_detail():
    """Reviewer mode is authorized to review technical details neutrally."""
    text = "Reviewer notice: Rule score 0.40 triggered by date discrepancy."
    violations = check_customer_role_leakage(text=text, audience="reviewer")
    assert len(violations) == 0
