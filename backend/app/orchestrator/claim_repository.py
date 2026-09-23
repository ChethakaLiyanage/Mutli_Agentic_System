"""Idempotent canonical claim persistence for orchestrated submissions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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

    def create_customer_policy(
        self,
        *,
        customer_id: str,
        policy_type: str,
        status: str = "active",
        start_date: str = "2026-01-01",
        end_date: str = "2027-01-01",
    ) -> dict[str, Any]: ...

    def list_all_policies(self) -> list[dict[str, Any]]: ...


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
            _normalize_policy_record(deepcopy(policy))
            for policy in self.policies
            if policy.get("customer_id") == customer_id
        ]

    def list_all_policies(self) -> list[dict[str, Any]]:
        return [_normalize_policy_record(deepcopy(p)) for p in self.policies]

    def create_customer_policy(
        self,
        *,
        customer_id: str,
        policy_type: str,
        status: str = "active",
        start_date: str = "2026-01-01",
        end_date: str = "2027-01-01",
    ) -> dict[str, Any]:
        payload = _build_policy_payload(
            customer_id=customer_id,
            policy_type=policy_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        self.policies.append(deepcopy(payload))
        return _normalize_policy_record(payload)

    def ensure_default_policy(self, customer_id: str) -> dict[str, Any]:
        policies = self.list_policies_for_customer(customer_id)
        if policies:
            return policies[0]
        return self.create_customer_policy(
            customer_id=customer_id,
            policy_type="full_comprehensive",
            status="active",
        )


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
                .select("*")
                .eq("customer_id", customer_id)
                .order("created_at", desc=True)
                .execute()
            )
            return [_normalize_policy_record(dict(row)) for row in (response.data or [])]
        except Exception as error:
            raise ClaimPersistenceError("Failed to list policies for customer") from error

    def list_all_policies(self) -> list[dict[str, Any]]:
        try:
            response = (
                self._client.table("policies")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return [_normalize_policy_record(dict(row)) for row in (response.data or [])]
        except Exception as error:
            raise ClaimPersistenceError("Failed to list all policies") from error

    def create_customer_policy(
        self,
        *,
        customer_id: str,
        policy_type: str,
        status: str = "active",
        start_date: str = "2026-01-01",
        end_date: str = "2027-01-01",
    ) -> dict[str, Any]:
        payload = _build_policy_payload(
            customer_id=customer_id,
            policy_type=policy_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            response = self._client.table("policies").insert(payload).execute()
            persisted = dict(response.data[0]) if response.data else payload
            return _normalize_policy_record(persisted)
        except Exception as error:
            err_str = str(error)
            if "column policies.policy_type does not exist" in err_str or "42703" in err_str:
                fallback = {k: v for k, v in payload.items() if k != "policy_type"}
                response = self._client.table("policies").insert(fallback).execute()
                persisted = dict(response.data[0]) if response.data else payload
                return _normalize_policy_record(persisted)
            raise ClaimPersistenceError("Failed to create customer policy") from error

    def ensure_default_policy(self, customer_id: str) -> dict[str, Any]:
        policies = self.list_policies_for_customer(customer_id)
        if policies:
            return policies[0]
        return self.create_customer_policy(
            customer_id=customer_id,
            policy_type="full_comprehensive",
            status="active",
        )


def _normalize_policy_record(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    cov_type = str(data.get("coverage_type") or "full")
    pol_type = data.get("policy_type")
    if not pol_type:
        meta = data.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("policy_type"):
            pol_type = str(meta["policy_type"])
        else:
            mapping = {
                "full": "full_comprehensive",
                "partial": "partial_comprehensive",
                "third_party": "third_party",
            }
            pol_type = mapping.get(cov_type, "full_comprehensive")
    data["policy_type"] = pol_type
    return data


def _build_policy_payload(
    *,
    customer_id: str,
    policy_type: str,
    policy_id: str | None = None,
    policy_number: str | None = None,
    status: str = "active",
    start_date: str = "2026-01-01",
    end_date: str = "2027-01-01",
) -> dict[str, Any]:
    norm_policy_type = policy_type.strip().lower()
    cov_mapping = {
        "full_comprehensive": "full",
        "partial_comprehensive": "partial",
        "third_party": "third_party",
    }
    cov_type = cov_mapping.get(norm_policy_type, "full")
    if norm_policy_type == "third_party":
        coverage_details = {
            "type": "third_party",
            "deductible": 0,
            "own_damage": False,
            "third_party_liability": True,
            "theft": False,
            "fire": False,
            "flood": False,
            "windscreen": False,
            "coverage_limit": 5000000,
        }
        exclusions = [
            "damage to the insured vehicle",
            "theft of own vehicle",
            "fire damage to own vehicle",
            "flood damage to own vehicle",
            "windscreen damage to own vehicle",
        ]
    elif norm_policy_type == "partial_comprehensive":
        coverage_details = {
            "type": "partial_comprehensive",
            "deductible": 200,
            "own_damage": False,
            "third_party_liability": True,
            "theft": True,
            "fire": True,
            "flood": True,
            "windscreen": True,
            "coverage_limit": 300000,
        }
        exclusions = [
            "accidental own-vehicle collision damage",
            "racing",
            "intentional damage",
        ]
    else:
        norm_policy_type = "full_comprehensive"
        cov_type = "full"
        coverage_details = {
            "type": "full_comprehensive",
            "deductible": 250,
            "own_damage": True,
            "third_party_liability": True,
            "theft": True,
            "fire": True,
            "flood": True,
            "windscreen": True,
            "coverage_limit": 500000,
        }
        exclusions = [
            "racing",
            "intentional damage",
            "driving without a valid licence",
        ]

    p_id = policy_id or f"POL-{uuid5(NAMESPACE_URL, f'{customer_id}:{datetime.now(timezone.utc).isoformat()}:id').hex[:10].upper()}"
    p_num = policy_number or f"POL-{uuid5(NAMESPACE_URL, f'{customer_id}:{datetime.now(timezone.utc).isoformat()}:num').hex[:8].upper()}"

    return {
        "policy_id": p_id,
        "policy_number": p_num,
        "customer_id": customer_id,
        "insurance_type": "motor",
        "coverage_type": cov_type,
        "policy_type": norm_policy_type,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
        "coverage_details": coverage_details,
        "exclusions": exclusions,
        "metadata": {"policy_type": norm_policy_type},
    }


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

