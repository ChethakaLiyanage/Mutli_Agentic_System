"""Formatting utilities for customer guidance and claims officer summaries.

Implements Sections 4, 8, and Mode A/B formatting of the design guide.
"""

from __future__ import annotations

from typing import Any
from .schemas import GuidanceResponse, ReviewerSummarySection


def format_markdown_customer_response(response: GuidanceResponse) -> str:
    """Format customer guidance into clean, readable Markdown."""
    lines = [
        f"### {response.response_type.replace('_', ' ').title()}",
        "",
        response.data.message,
        "",
    ]

    if response.data.next_steps:
        lines.append("#### Recommended Next Steps:")
        for idx, step in enumerate(response.data.next_steps, 1):
            lines.append(f"{idx}. {step}")
        lines.append("")

    if response.data.evidence_used:
        lines.append("#### Reference Guidelines:")
        for ref in response.data.evidence_used:
            lines.append(f"- *{ref}*")
        lines.append("")

    return "\n".join(lines)


def format_markdown_reviewer_summary(summary: ReviewerSummarySection) -> str:
    """Format reviewer summary into a structured dashboard briefing."""
    lines = [
        "## Claim Assessment Dossier (Officer Review Only)",
        "",
        "### 1. Claim Overview",
        summary.claim_overview,
        "",
        "### 2. Relevant Policy Findings",
    ]

    for finding in summary.policy_findings or ["No specific policy clauses flagged."]:
        lines.append(f"- {finding}")
    lines.append("")

    lines.append("### 3. Triage & Risk Observations")
    for obs in summary.risk_observations or ["No risk indicators detected."]:
        lines.append(f"- {obs}")
    lines.append("")

    lines.append("### 4. Missing Documents / Verification Items")
    for item in summary.missing_items or ["All standard documents submitted."]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### 5. Recommended Reviewer Action Points")
    for action in summary.reviewer_action_points or ["Proceed with standard assessment."]:
        lines.append(f"- [ ] {action}")
    lines.append("")

    return "\n".join(lines)
