"""Idempotent canonical claim persistence for orchestrated submissions."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid5

from backend.app.config import get_settings
from backend.app.schemas.domain import ClaimContext
from backend.app.services.domain_row_mappers import claim_from_row, claim_to_row
from backend.app.services.supabase_service import get_supabase_client


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

    def get_by_id(self, claim_id: str) -> ClaimContext | None: ...

    def get_by_workflow_id(self, workflow_id: str) -> ClaimContext | None: ...

    def list_for_customer(self, customer_id: str) -> list[ClaimContext]: ...

    def list_policies_for_customer(self, customer_id: str) -> list[dict[str, Any]]: ...

    def ensure_default_policy(self, customer_id: str) -> dict[str, Any]: ...


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
        if policy is None and claim.customer_id:
            policy = {
                "policy_id": f"POL-{uuid5(NAMESPACE_URL, claim.customer_id).hex[:10].upper()}",
                "policy_number": f"POL-{uuid5(NAMESPACE_URL, claim.customer_id).hex[:8].upper()}",
                "customer_id": claim.customer_id,
                "insurance_type": "motor",
                "coverage_type": "full",
                "status": "active",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
                "coverage_details": {"type": "comprehensive", "deductible": 250},
                "exclusions": [],
            }
            if not any(
                item.get("policy_id") == policy.get("policy_id")
                for item in self.policies
            ):
                self.policies.append(deepcopy(policy))
        stored = _claim_with_persistence_identity(workflow_id, claim, policy)
        self.claims_by_workflow[workflow_id] = stored.model_copy(deep=True)
        return stored

    def get_by_id(self, claim_id: str) -> ClaimContext | None:
        for claim in self.claims_by_workflow.values():
            if claim.claim_id == claim_id:
                return claim.model_copy(deep=True)
        return None

    def get_by_workflow_id(self, workflow_id: str) -> ClaimContext | None:
        claim = self.claims_by_workflow.get(workflow_id)
        return claim.model_copy(deep=True) if claim else None

    def list_for_customer(self, customer_id: str) -> list[ClaimContext]:
        return [
            claim.model_copy(deep=True)
            for claim in self.claims_by_workflow.values()
            if claim.customer_id == customer_id
        ]

    def list_policies_for_customer(self, customer_id: str) -> list[dict[str, Any]]:
        return [
            deepcopy(policy)
            for policy in self.policies
            if policy.get("customer_id") == customer_id
        ]

    def ensure_default_policy(self, customer_id: str) -> dict[str, Any]:
        policies = self.list_policies_for_customer(customer_id)
        if policies:
            return policies[0]
        policy = {
            "policy_id": f"POL-{uuid5(NAMESPACE_URL, customer_id).hex[:10].upper()}",
            "policy_number": f"POL-{uuid5(NAMESPACE_URL, customer_id).hex[:8].upper()}",
            "customer_id": customer_id,
            "insurance_type": "motor",
            "coverage_type": "full",
            "status": "active",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
            "coverage_details": {"type": "comprehensive", "deductible": 250},
            "exclusions": [],
        }
        self.policies.append(deepcopy(policy))
        return policy


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
                .select(
                    "policy_id,policy_number,customer_id,status,coverage_type,"
                    "start_date,end_date"
                )
                .eq("customer_id", claim.customer_id)
                .execute()
            )
            policy = _select_owned_policy(policies.data or [], claim.customer_id)
            if policy is None and claim.customer_id:
                policy_id = f"POL-{uuid5(NAMESPACE_URL, claim.customer_id).hex[:10].upper()}"
                policy_num = f"POL-{uuid5(NAMESPACE_URL, claim.customer_id).hex[:8].upper()}"
                new_policy = {
                    "policy_id": policy_id,
                    "policy_number": policy_num,
                    "customer_id": claim.customer_id,
                    "insurance_type": "motor",
                    "coverage_type": "full",
                    "status": "active",
                    "start_date": "2026-01-01",
                    "end_date": "2027-01-01",
                    "coverage_details": {"type": "comprehensive", "deductible": 250},
                    "exclusions": [],
                }
                try:
                    self._client.table("policies").insert(new_policy).execute()
                    policy = new_policy
                except Exception:
                    policy = new_policy

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

    def get_by_id(self, claim_id: str) -> ClaimContext | None:
        try:
            response = (
                self._client.table("claims")
                .select("*")
                .eq("claim_id", claim_id)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return claim_from_row(dict(response.data[0]))
        except Exception as error:
            raise ClaimPersistenceError("Failed to fetch claim") from error

    def get_by_workflow_id(self, workflow_id: str) -> ClaimContext | None:
        try:
            response = (
                self._client.table("claims")
                .select("*")
                .eq("workflow_id", workflow_id)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return claim_from_row(dict(response.data[0]))
        except Exception as error:
            raise ClaimPersistenceError("Failed to fetch claim by workflow") from error

    def list_for_customer(self, customer_id: str) -> list[ClaimContext]:
        try:
            response = (
                self._client.table("claims")
                .select("*")
                .eq("customer_id", customer_id)
                .order("created_at", desc=True)
                .execute()
            )
            return [claim_from_row(dict(row)) for row in (response.data or [])]
        except Exception as error:
            raise ClaimPersistenceError("Failed to list claims for customer") from error

    def list_policies_for_customer(self, customer_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                self._client.table("policies")
                .select(
                    "policy_id,policy_number,insurance_type,status,start_date,end_date,"
                    "coverage_type,coverage_details,exclusions"
                )
                .eq("customer_id", customer_id)
                .order("created_at", desc=True)
                .execute()
            )
            return [dict(row) for row in (response.data or [])]
        except Exception as error:
            raise ClaimPersistenceError("Failed to list policies for customer") from error

    def ensure_default_policy(self, customer_id: str) -> dict[str, Any]:
        policies = self.list_policies_for_customer(customer_id)
        if policies:
            return policies[0]
        policy = {
            "policy_id": f"POL-{uuid5(NAMESPACE_URL, customer_id).hex[:10].upper()}",
            "policy_number": f"POL-{uuid5(NAMESPACE_URL, customer_id).hex[:8].upper()}",
            "customer_id": customer_id,
            "insurance_type": "motor",
            "coverage_type": "full",
            "status": "active",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
            "coverage_details": {"type": "comprehensive", "deductible": 250},
            "exclusions": [],
        }
        try:
            response = self._client.table("policies").insert(policy).execute()
            return dict(response.data[0]) if response.data else policy
        except Exception as error:
            raise ClaimPersistenceError("Failed to create default policy") from error


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
            "workflow_id": workflow_id,
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


@lru_cache(maxsize=1)
def get_claim_repository() -> ClaimRepository:
    settings = get_settings()
    if settings.persistence_backend == "supabase":
        return SupabaseClaimRepository(get_supabase_client(settings))
    return InMemoryClaimRepository()

