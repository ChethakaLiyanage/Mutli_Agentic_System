"""Persistence boundaries for authoritative human review decisions."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Protocol, runtime_checkable

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
        self._lock = asyncio.Lock()

    async def list_pending(self, *, limit: int, offset: int) -> list[WorkflowState]:
        return await self.workflows.list_by_status(
            WorkflowStatus.AWAITING_HUMAN_REVIEW.value,
            limit=limit,
            offset=offset,
        )

    async def get_workflow(self, workflow_id: str) -> WorkflowState | None:
        return await self.workflows.get(workflow_id)

    async def get_decision(self, workflow_id: str) -> HumanDecisionContext | None:
        decision = self.decisions.get(workflow_id)
        return decision.model_copy(deep=True) if decision else None

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
            if current.current_status is not WorkflowStatus.AWAITING_HUMAN_REVIEW:
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

    async def list_pending(self, *, limit: int, offset: int) -> list[WorkflowState]:
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
                        "p_expected_status": WorkflowStatus.AWAITING_HUMAN_REVIEW.value,
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
            message = str(error).lower()
            if "already" in message or "not_awaiting" in message or "23505" in message:
                raise ReviewDecisionConflictError(
                    "A human decision already exists or review is closed"
                ) from error
            raise ReviewRepositoryError("Human decision persistence failed") from error
