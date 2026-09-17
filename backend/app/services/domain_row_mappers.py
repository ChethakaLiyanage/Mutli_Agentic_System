"""Pure mappings between canonical domain contracts and database rows.

These functions keep persistence details out of agents and are intentionally
independent of Supabase so they can be tested with ordinary dictionaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.schemas.domain import (
    ClaimContext,
    DocumentFact,
    DocumentReference,
    EvidenceItem,
    HumanDecisionContext,
    PolicyContext,
)


def policy_to_row(policy: PolicyContext) -> dict[str, Any]:
    return policy.model_dump(mode="json")


def policy_from_row(row: dict[str, Any]) -> PolicyContext:
    return PolicyContext.model_validate(row)


def claim_to_row(claim: ClaimContext) -> dict[str, Any]:
    row = claim.model_dump(mode="json", exclude={"document_references"})
    return row


def claim_from_row(
    row: dict[str, Any],
    document_references: list[DocumentReference] | None = None,
) -> ClaimContext:
    allowed = set(ClaimContext.model_fields)
    data = {key: value for key, value in row.items() if key in allowed}
    data["document_references"] = document_references or []
    return ClaimContext.model_validate(data)


def document_fact_to_row(
    fact: DocumentFact,
    *,
    claim_id: str,
    customer_id: str,
) -> dict[str, Any]:
    row = fact.model_dump(mode="json")
    row.update({"claim_id": claim_id, "customer_id": customer_id})
    return row


def document_fact_from_row(row: dict[str, Any]) -> DocumentFact:
    allowed = set(DocumentFact.model_fields)
    return DocumentFact.model_validate(
        {key: value for key, value in row.items() if key in allowed}
    )


def evidence_from_knowledge_row(row: dict[str, Any]) -> EvidenceItem:
    """Translate a knowledge chunk row into agent-neutral evidence."""
    return EvidenceItem(
        evidence_id=row["chunk_id"],
        source_title=row["source_title"],
        section=row.get("section"),
        content=row["content"],
        score=row.get("score"),
        metadata=row.get("metadata") or {},
    )


def human_decision_to_row(
    decision: HumanDecisionContext,
    *,
    decision_id: str,
    workflow_id: str | None = None,
    claim_id: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    if not workflow_id and not claim_id:
        raise ValueError("A human decision requires a workflow_id or claim_id")
    if decision.decided_at is not None and decision.decided_at.tzinfo is None:
        raise ValueError("decided_at must include timezone information")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("created_at must include timezone information")
    row = decision.model_dump(mode="json")
    row.update(
        {
            "decision_id": decision_id,
            "workflow_id": workflow_id,
            "claim_id": claim_id,
            "created_at": timestamp.isoformat(),
        }
    )
    return row


def human_decision_from_row(row: dict[str, Any]) -> HumanDecisionContext:
    allowed = set(HumanDecisionContext.model_fields)
    return HumanDecisionContext.model_validate(
        {key: value for key, value in row.items() if key in allowed}
    )
