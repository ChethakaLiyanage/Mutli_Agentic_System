"""Reviewer Support Agent node for LangGraph workflow."""


def reviewer_support_agent(state: dict) -> dict:
    """
    Reviewer Support Agent node.

    Processes retrieval results and fraud assessments to produce
    actionable notes and recommendations for the human reviewer.
    """
    retrieval_status = state.get("retrieval_status", "unknown")
    retrieval_response = state.get("retrieval_response") or {}
    result = retrieval_response.get("result") or {}
    fraud_assessment = state.get("fraud_assessment") or {}

    notes = []
    if result.get("policy_data"):
        policy_num = result["policy_data"].get("policy_number")
        notes.append(f"Policy verified: {policy_num}")
    if result.get("claim_record"):
        claim_ref = result["claim_record"].get("claim_reference")
        notes.append(f"Claim record verified: {claim_ref}")
    if fraud_assessment:
        risk_level = fraud_assessment.get("risk_level", "low")
        notes.append(f"Fraud assessment risk level: {risk_level}")

    summary = "; ".join(notes) if notes else f"Retrieval status: {retrieval_status}"

    return {
        "reviewer_notes": summary,
        "final_decision": "under_review",
    }
"""Reviewer support agent wrapper.

Aliases the implementation in guidance_agent.py for compatibility.
"""

from .guidance_agent import GuidanceAgent, guidance_agent, reviewer_support_agent

__all__ = ["GuidanceAgent", "guidance_agent", "reviewer_support_agent"]
