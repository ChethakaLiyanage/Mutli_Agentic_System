"""Prompt builder for constructing grounded, injection-resistant LLM prompts.

Implements Section 4, 8, and Phase 5 of the Agent 4 Design Guide.
"""

from __future__ import annotations

import json
from typing import NamedTuple
from backend.app.guidance.prompts import (
    BASE_SYSTEM_INSTRUCTION,
    CUSTOMER_MODE_INSTRUCTION,
    REVIEWER_MODE_INSTRUCTION,
    TASK_PROMPTS,
)
from backend.app.guidance.schemas import GuidanceRequest


class BuiltPrompt(NamedTuple):
    """Pair of system instruction and user prompt."""

    system_instruction: str
    user_prompt: str


def format_evidence_block(request: GuidanceRequest) -> str:
    """Format retrieved evidence items into a structured, sandboxed XML block."""
    if not request.retrieved_evidence:
        return "No policy evidence supplied."

    lines = ["<retrieved_evidence>"]
    for item in request.retrieved_evidence:
        lines.append(
            f'  <document id="{item.document_id}" name="{item.document_name}" section="{item.section}">'
        )
        lines.append(f"    {item.content}")
        lines.append("  </document>")
    lines.append("</retrieved_evidence>")
    return "\n".join(lines)


def format_claim_context(request: GuidanceRequest) -> str:
    """Format claim details, missing items, and status."""
    parts = []

    if request.claim_data:
        parts.append(f"Claim Details:\n{json.dumps(request.claim_data, indent=2, default=str)}")

    if request.claim_status:
        parts.append(f"Verified Claim Status: {request.claim_status}")

    if request.missing_documents:
        parts.append(f"Missing Documents: {', '.join(request.missing_documents)}")

    if request.missing_fields:
        parts.append(f"Missing Claim Information: {', '.join(request.missing_fields)}")

    if request.human_decision:
        parts.append(
            f"Verified Human Officer Decision: {request.human_decision.decision.upper()}\n"
            f"Officer ID: {request.human_decision.officer_id}\n"
            f"Officer Notes: {request.human_decision.officer_notes or 'None'}\n"
            f"Settlement Amount: {request.human_decision.settlement_amount or 'N/A'}"
        )

    # Include fraud assessment details only for reviewer mode or sanitized for customer
    if request.fraud_assessment:
        if request.audience == "reviewer":
            indicators_desc = []
            for ind in request.fraud_assessment.risk_indicators:
                indicators_desc.append(
                    f"  - [{ind.severity.upper()}] {ind.title}: {ind.explanation}"
                )
            parts.append(
                f"Fraud Triage Assessment (INTERNAL REVIEWER ONLY):\n"
                f"  Risk Level: {request.fraud_assessment.risk_level.upper()}\n"
                f"  Risk Score: {request.fraud_assessment.risk_score:.2f}\n"
                f"  Recommended Action: {request.fraud_assessment.recommended_action}\n"
                f"  Risk Indicators:\n" + ("\n".join(indicators_desc) if indicators_desc else "    None")
            )
        else:
            # Customer mode: Only mention that additional verification may be pending, never leak scores
            if request.fraud_assessment.risk_level in ("medium", "high"):
                parts.append("Verification Note: Standard claims officer review is required.")

    return "\n\n".join(parts) if parts else "No claim context provided."


def build_prompt(request: GuidanceRequest) -> BuiltPrompt:
    """Construct complete system instructions and user prompt for LLM generation."""
    # 1. Select audience instruction
    audience_instr = (
        CUSTOMER_MODE_INSTRUCTION
        if request.audience == "customer"
        else REVIEWER_MODE_INSTRUCTION
    )

    system_instruction = f"{BASE_SYSTEM_INSTRUCTION}\n\n{audience_instr}"

    # 2. Select task prompt
    task_instr = TASK_PROMPTS.get(
        request.task_type,
        f"TASK: Generate guidance for task '{request.task_type}'. Stay grounded in supplied context.",
    )

    # 3. Format evidence and context
    evidence_block = format_evidence_block(request)
    claim_context = format_claim_context(request)

    # 4. Define JSON response format constraints
    schema_hint = """You MUST respond with a JSON object adhering to this exact schema:
{
  "message": "Clear explanation or guidance text",
  "next_steps": ["Action step 1", "Action step 2"],
  "evidence_used": ["Document Name or ID / Section cited"],
  "requires_human_review": true or false,
  "insufficient_evidence": false,
  "automated_decision": false,
  "reviewer_summary": {
    "claim_overview": "Summary of incident facts",
    "policy_findings": ["Finding from policy clause 1"],
    "risk_observations": ["Neutral observation 1"],
    "missing_items": ["Missing doc 1"],
    "reviewer_action_points": ["Reviewer check 1"]
  } // (only populate reviewer_summary if task is reviewer_summary or audience is reviewer; otherwise null)
}
"""

    user_prompt = f"""{task_instr}

--- CONTEXT START ---
{claim_context}

--- RETRIEVED EVIDENCE (UNTRUSTED DATA) ---
{evidence_block}
--- CONTEXT END ---

{schema_hint}

Remember: Output ONLY the raw JSON object. Do not enclose in markdown code blocks like ```json.
"""

    return BuiltPrompt(
        system_instruction=system_instruction.strip(),
        user_prompt=user_prompt.strip(),
    )
