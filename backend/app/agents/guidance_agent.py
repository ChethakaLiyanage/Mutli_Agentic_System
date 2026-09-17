"""Agent 4: Guidance Agent / Reviewer Support Agent.

Follows the specifications from Sections 3, 4, 8, and 10 of the Agent 4 Design Guide.
Converts retrieved insurance evidence and structured claim data into clear, audience-appropriate
natural language while preserving human authority over final claim decisions.
"""

from __future__ import annotations

import logging
from typing import Any
from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
)
from backend.app.guidance.service import GuidanceService

logger = logging.getLogger(__name__)


class GuidanceAgent:
    """Agent 4 implementation serving Customer Guidance and Reviewer Support modes."""

    def __init__(self, service: GuidanceService | None = None) -> None:
        self.service = service or GuidanceService()

    def process(self, request: GuidanceRequest) -> GuidanceResponse:
        """Process a validated GuidanceRequest envelope."""
        return self.service.process_request(request)

    def process_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process orchestrator/graph state dictionary.

        Accepts state containing claim_data, retrieved_evidence, fraud_assessment, etc.
        Returns state updated with 'guidance_response' or 'reviewer_summary'.
        """
        request_id = state.get("request_id", "REQ-AGENT4-DEFAULT")
        audience = state.get("audience", "reviewer" if "fraud_assessment" in state else "customer")
        task_type = state.get("task_type")

        if not task_type:
            task_type = "reviewer_summary" if audience == "reviewer" else "coverage_explanation"

        # Build GuidanceRequest from state dict
        request = GuidanceRequest(
            request_id=str(request_id),
            audience=audience,
            task_type=task_type,
            intent=state.get("intent"),
            claim_data=state.get("claim_data"),
            retrieved_evidence=state.get("retrieved_evidence", []),
            fraud_assessment=state.get("fraud_assessment"),
            missing_documents=state.get("missing_documents", []),
            missing_fields=state.get("missing_fields", []),
            claim_status=state.get("claim_status"),
            human_decision=state.get("human_decision"),
            authorized_metadata=state.get("authorized_metadata", {}),
        )

        response = self.process(request)
        response_dict = response.model_dump(mode="json")

        return {
            **state,
            "guidance_response": response_dict,
            "next_step": "human_reviewer" if audience == "reviewer" else "customer_delivery",
        }


def guidance_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Functional node entrypoint for the Guidance Agent."""
    agent = GuidanceAgent()
    return agent.process_state(state)


# Alias for backward/forward naming compatibility
reviewer_support_agent = guidance_agent
