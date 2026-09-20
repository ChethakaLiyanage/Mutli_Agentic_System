"""Persistence boundaries for authoritative human review decisions."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.orchestrator.repository import WorkflowRepository
from backend.app.schemas.domain import HumanDecisionContext
from backend.app.services.domain_row_mappers import human_decision_from_row


class ReviewRepositoryError(RuntimeError):
    pass


class ReviewDecisionConflictError(ReviewRepositoryError):
    pass


@runtime_checkable
class HumanReviewRepository(Protocol):
    async def list_pending(self, *, limit: int, offset: int) -> list[WorkflowState]: ...
    async def get_workflow(self, workflow_id: str) -> WorkflowState | None: ...
    async def get_decision(self, workflow_id: str) -> HumanDecisionContext | None: ...
    async def assign_claim(
        self,
        *,
        claim_id: str,
        workflow_id: str,
        assigned_to: str,
        assigned_by: str,
    ) -> dict[str, Any]: ...
    async def get_assignment(self, workflow_id: str) -> dict[str, Any] | None: ...
    async def commit_decision(
        self,
        *,
        state: WorkflowState,
        decision: HumanDecisionContext,
        claim_status: str,
    ) -> None: ...


class InMemoryHumanReviewRepository:
    """Concurrency-safe repository used by local development and unit tests."""

    def __init__(self, workflows: WorkflowRepository) -> None:
        self.workflows = workflows
        self.decisions: dict[str, HumanDecisionContext] = {}
        self.claim_statuses: dict[str, str] = {}
        self.assignments: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def list_pending(self, *, limit: int, offset: int) -> list[WorkflowState]:
        all_states: list[WorkflowState] = []
        for status_val in [
            WorkflowStatus.AWAITING_ASSIGNMENT.value,
            WorkflowStatus.UNDER_HUMAN_REVIEW.value,
            WorkflowStatus.AWAITING_HUMAN_REVIEW.value,
        ]:
            items = await self.workflows.list_by_status(
                status_val, limit=limit, offset=0
            )
            all_states.extend(items)

        seen: set[str] = set()
        unique: list[WorkflowState] = []
        for st in all_states:
            if st.workflow_id not in seen:
                seen.add(st.workflow_id)
                unique.append(st)
        return unique[offset:offset + limit]

    async def get_workflow(self, workflow_id: str) -> WorkflowState | None:
        return await self.workflows.get(workflow_id)

    async def get_decision(self, workflow_id: str) -> HumanDecisionContext | None:
        decision = self.decisions.get(workflow_id)
        return decision.model_copy(deep=True) if decision else None

    async def assign_claim(
        self,
        *,
        claim_id: str,
        workflow_id: str,
        assigned_to: str,
        assigned_by: str,
    ) -> dict[str, Any]:
        record = {
            "assignment_id": f"ASGN-{uuid4().hex.upper()}",
            "claim_id": claim_id,
            "workflow_id": workflow_id,
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "assigned_at": datetime.now(timezone.utc),
        }
        self.assignments[workflow_id] = record
        return record

    async def get_assignment(self, workflow_id: str) -> dict[str, Any] | None:
        record = self.assignments.get(workflow_id)
        return deepcopy(record) if record else None

    async def commit_decision(
        self,
        *,
        state: WorkflowState,
        decision: HumanDecisionContext,
        claim_status: str,
    ) -> None:
        async with self._lock:
            current = await self.workflows.get(state.workflow_id)
            if current is None:
                raise ReviewRepositoryError("Workflow not found")
            if current.current_status not in {
                WorkflowStatus.AWAITING_HUMAN_REVIEW,
                WorkflowStatus.UNDER_HUMAN_REVIEW,
                WorkflowStatus.AWAITING_ASSIGNMENT,
            }:
                raise ReviewDecisionConflictError("Workflow is not awaiting review")
            if state.workflow_id in self.decisions:
                raise ReviewDecisionConflictError("A human decision already exists")
            self.decisions[state.workflow_id] = decision.model_copy(deep=True)
            assert decision.claim_id is not None
            self.claim_statuses[decision.claim_id] = claim_status
            await self.workflows.save(state)


class SupabaseHumanReviewRepository:
    """Supabase adapter using the Step 6 atomic review-decision RPC."""

    def __init__(self, client: Any, workflows: WorkflowRepository) -> None:
        self._client = client
        self.workflows = workflows
        self._assignments_fallback: dict[str, dict[str, Any]] = {}

    async def list_pending(self, *, limit: int, offset: int) -> list[WorkflowState]:
        try:
            fetch_count = max(limit * 3, 100)
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .select("*")
                    .in_(
                        "current_status",
                        [
                            WorkflowStatus.AWAITING_ASSIGNMENT.value,
                            WorkflowStatus.UNDER_HUMAN_REVIEW.value,
                            WorkflowStatus.AWAITING_HUMAN_REVIEW.value,
                        ],
                    )
                    .order("created_at", desc=True)
                    .range(offset, offset + fetch_count - 1)
                    .execute()
                )
            )
            states: list[WorkflowState] = []
            for row in (response.data or []):
                try:
                    states.append(self.workflows.row_to_state(row))
                except Exception:
                    continue

            pending = [
                st for st in states
                if st.current_status in {
                    WorkflowStatus.AWAITING_ASSIGNMENT,
                    WorkflowStatus.UNDER_HUMAN_REVIEW,
                    WorkflowStatus.AWAITING_HUMAN_REVIEW,
                }
            ]
            return pending[:limit]
        except Exception:
            return await self.workflows.list_by_status(
                WorkflowStatus.AWAITING_HUMAN_REVIEW.value,
                limit=limit,
                offset=offset,
            )

    async def get_workflow(self, workflow_id: str) -> WorkflowState | None:
        return await self.workflows.get(workflow_id)

    async def get_decision(self, workflow_id: str) -> HumanDecisionContext | None:
        try:
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("human_decisions")
                    .select("*")
                    .eq("workflow_id", workflow_id)
                    .limit(1)
                    .execute()
                )
            )
            return human_decision_from_row(response.data[0]) if response.data else None
        except Exception as error:
            raise ReviewRepositoryError("Human decision lookup failed") from error

    async def assign_claim(
        self,
        *,
        claim_id: str,
        workflow_id: str,
        assigned_to: str,
        assigned_by: str,
    ) -> dict[str, Any]:
        record = {
            "assignment_id": f"ASGN-{uuid4().hex.upper()}",
            "claim_id": claim_id,
            "workflow_id": workflow_id,
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._assignments_fallback[workflow_id] = record
        try:
            await asyncio.to_thread(
                lambda: self._client.table("claim_assignments").insert(record).execute()
            )
        except Exception:
            pass
        return record

    async def get_assignment(self, workflow_id: str) -> dict[str, Any] | None:
        try:
            res = await asyncio.to_thread(
                lambda: self._client.table("claim_assignments")
                .select("*")
                .eq("workflow_id", workflow_id)
                .order("assigned_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                return dict(res.data[0])
        except Exception:
            pass
        return self._assignments_fallback.get(workflow_id)

    async def commit_decision(
        self,
        *,
        state: WorkflowState,
        decision: HumanDecisionContext,
        claim_status: str,
    ) -> None:
        if not decision.claim_id:
            raise ReviewRepositoryError("Claim identifier is required")
        payload = decision.model_dump(mode="json")
        try:
            await asyncio.to_thread(
                lambda: self._client.rpc(
                    "submit_human_review_decision",
                    {
                        "p_workflow_id": state.workflow_id,
                        "p_claim_id": decision.claim_id,
                        "p_expected_status": state.current_status.value,
                        "p_target_status": state.current_status.value,
                        "p_claim_status": claim_status,
                        "p_decision": payload,
                        "p_human_review_result": payload,
                        "p_audit_trail": [
                            item.model_dump(mode="json") for item in state.audit_trail
                        ],
                    },
                ).execute()
            )
        except Exception as error:
            # Fallback direct update if RPC fails
            try:
                await asyncio.to_thread(
                    lambda: self._client.table("human_decisions").insert({
                        "decision_id": decision.decision_id,
                        "workflow_id": state.workflow_id,
                        "claim_id": decision.claim_id,
                        "reviewer_id": decision.reviewer_id,
                        "reviewer_role": decision.reviewer_role,
                        "decision": decision.decision.value,
                        "reason": decision.reason,
                        "notes": decision.notes,
                        "requested_information": decision.requested_information,
                        "settlement_amount": float(decision.settlement_amount) if decision.settlement_amount else None,
                        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
                    }).execute()
                )
                await asyncio.to_thread(
                    lambda: self._client.table("claims")
                    .update({"claim_status": claim_status})
                    .eq("claim_id", decision.claim_id)
                    .execute()
                )
                await self.workflows.save(state)
                return
            except Exception as inner_error:
                message = str(inner_error).lower()
                if "already" in message or "not_awaiting" in message or "23505" in message:
                    raise ReviewDecisionConflictError(
                        "A human decision already exists or review is closed"
                    ) from inner_error
                raise ReviewRepositoryError("Human decision persistence failed") from inner_error
