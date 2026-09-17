"""Tests for Prompts and Prompt Builder (Section 4, 8, Phase 5)."""

from __future__ import annotations

import pytest
from backend.app.guidance.prompt_builder import (
    build_prompt,
    format_claim_context,
    format_evidence_block,
)
from backend.app.guidance.schemas import (
    EvidenceItem,
    GuidanceRequest,
    RiskIndicatorContext,
    FraudAssessmentContext,
)


def test_format_evidence_block_creates_xml_tags():
    """Evidence items are formatted into tagged, sandboxed XML blocks."""
    request = GuidanceRequest(
        request_id="REQ-PROMPT-01",
        audience="customer",
        task_type="coverage_explanation",
        retrieved_evidence=[
            EvidenceItem(
                document_id="DOC-WINDSCREEN",
                document_name="MotorPolicy2026.pdf",
                section="Section 4 - Windscreen",
                content="Windscreen replacement is covered up to Rs. 50000 per policy year.",
            )
        ],
    )
    block = format_evidence_block(request)
    assert '<document id="DOC-WINDSCREEN" name="MotorPolicy2026.pdf" section="Section 4 - Windscreen">' in block
    assert "Windscreen replacement is covered up to Rs. 50000" in block
    assert "</retrieved_evidence>" in block


def test_build_prompt_includes_system_guardrails():
    """System instruction enforces core principles in prompt text."""
    request = GuidanceRequest(
        request_id="REQ-PROMPT-02",
        audience="customer",
        task_type="coverage_explanation",
    )
    built = build_prompt(request)
    assert "IR retrieves first -> LLM explains second" in built.system_instruction
    assert "NEVER invent policy facts" in built.system_instruction
    assert "AUDIENCE: CUSTOMER" in built.system_instruction
    assert "raw JSON object" in built.user_prompt


def test_reviewer_prompt_includes_fraud_assessment_details():
    """Reviewer prompt includes structured fraud indicators for officer assistance."""
    fraud_ctx = FraudAssessmentContext(
        risk_level="medium",
        risk_score=0.45,
        risk_indicators=[
            RiskIndicatorContext(
                rule_id="RULE_DATE_CONFLICT",
                severity="medium",
                title="Date Discrepancy",
                explanation="Claim date does not match police report date.",
            )
        ],
    )
    request = GuidanceRequest(
        request_id="REQ-PROMPT-03",
        audience="reviewer",
        task_type="reviewer_summary",
        fraud_assessment=fraud_ctx,
    )
    built = build_prompt(request)
    assert "AUDIENCE: CLAIMS OFFICER / REVIEWER" in built.system_instruction
    assert "Fraud Triage Assessment (INTERNAL REVIEWER ONLY)" in built.user_prompt
    assert "Date Discrepancy" in built.user_prompt
