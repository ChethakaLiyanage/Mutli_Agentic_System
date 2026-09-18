"""Idempotent canonical claim persistence for orchestrated submissions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid5

from backend.app.schemas.domain import ClaimContext
from backend.app.services.domain_row_mappers import claim_from_row, claim_to_row


class ClaimPersistenceError(RuntimeError):
    """Raised when a grounded claim cannot be persisted safely."""


@runtime_checkable
class ClaimRepository(Protocol):
    def save_for_workflow(
        self,
        *,
        workflow_id: str,
        claim: ClaimContext,
    ) -> ClaimContext: ...


class InMemoryClaimRepository:
    """Deterministic test/local repository with optional trusted policies."""

    def __init__(self, policies: list[dict[str, Any]] | None = None) -> None:
        self.policies = list(policies or [])
        self.claims_by_workflow: dict[str, ClaimContext] = {}

    def save_for_workflow(
        self,
        *,
        workflow_id: str,
        claim: ClaimContext,
    ) -> ClaimContext:
        existing = self.claims_by_workflow.get(workflow_id)
        if existing is not None:
            return existing.model_copy(deep=True)
        policy = _select_owned_policy(self.policies, claim.customer_id)
        stored = _claim_with_persistence_identity(workflow_id, claim, policy)
        self.claims_by_workflow[workflow_id] = stored.model_copy(deep=True)
        return stored


class SupabaseClaimRepository:
    """Persist one canonical claim per workflow using trusted policy ownership."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def save_for_workflow(
        self,
        *,
        workflow_id: str,
        claim: ClaimContext,
    ) -> ClaimContext:
        try:
            existing = (
                self._client.table("claims")
                .select("*")
                .eq("workflow_id", workflow_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                row = dict(existing.data[0])
                if row.get("customer_id") != claim.customer_id:
                    raise ClaimPersistenceError("Stored claim ownership mismatch")
                return claim_from_row(row)

            policies = (
                self._client.table("policies")
                .select("policy_id,policy_number,customer_id,status,start_date,end_date")
                .eq("customer_id", claim.customer_id)
                .execute()
            )
            policy = _select_owned_policy(policies.data or [], claim.customer_id)
            stored = _claim_with_persistence_identity(workflow_id, claim, policy)
            row = claim_to_row(stored)
            row["workflow_id"] = workflow_id
            payload = {key: value for key, value in row.items() if value is not None}
            response = (
                self._client.table("claims")
                # The deterministic claim_id and the lookup above provide
                # idempotency without requiring legacy databases to already
                # have the canonical unique workflow_id constraint.
                .insert(payload)
                .execute()
            )
            persisted = dict(response.data[0]) if response.data else payload
            return claim_from_row(persisted)
        except ClaimPersistenceError:
            raise
        except Exception as error:
            raise ClaimPersistenceError("Claim persistence failed") from error


def _select_owned_policy(
    policies: list[dict[str, Any]],
    customer_id: str | None,
) -> dict[str, Any] | None:
    if customer_id is None:
        raise ClaimPersistenceError("Authenticated customer identity is required")
    owned = [row for row in policies if row.get("customer_id") == customer_id]
    active = [row for row in owned if row.get("status") == "active"]
    candidates = active if len(active) == 1 else owned
    if len(candidates) != 1:
        return None
    return deepcopy(candidates[0])


def _claim_with_persistence_identity(
    workflow_id: str,
    claim: ClaimContext,
    policy: dict[str, Any] | None,
) -> ClaimContext:
    if policy is not None and policy.get("customer_id") != claim.customer_id:
        raise ClaimPersistenceError("Policy ownership mismatch")
    claim_id = claim.claim_id or f"CLM-{uuid5(NAMESPACE_URL, workflow_id).hex.upper()}"
    claim_reference = claim.claim_reference or f"REF-{claim_id[4:20]}"
    return claim.model_copy(
        update={
            "claim_id": claim_id,
            "claim_reference": claim_reference,
            "policy_id": policy.get("policy_id") if policy else None,
            "policy_number": policy.get("policy_number") if policy else None,
            "claim_status": claim.claim_status or (
                "awaiting_human_review" if policy else "policy_link_required"
            ),
        },
        deep=True,
    )
