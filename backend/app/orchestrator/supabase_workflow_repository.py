"""Supabase-backed implementation of durable workflow persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.graph.state import WorkflowState
from backend.app.services.repository_errors import WorkflowPersistenceError


class SupabaseWorkflowRepository:
    """Store workflow columns and nested JSON state in Supabase Postgres."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def save(self, state: WorkflowState) -> None:
        try:
            existing = await self._get_row(state.workflow_id)
            if existing is not None:
                self._validate_immutable_fields(state, existing)
            state.updated_at = datetime.now(timezone.utc)
            row = self.state_to_row(state)
            await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .upsert(row, on_conflict="workflow_id")
                    .execute()
                )
            )
        except WorkflowPersistenceError:
            raise
        except Exception as error:
            raise WorkflowPersistenceError("Workflow save failed") from error

    async def get(self, workflow_id: str) -> WorkflowState | None:
        row = await self._get_row(workflow_id)
        return self.row_to_state(row) if row is not None else None

    async def delete(self, workflow_id: str) -> None:
        try:
            await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .delete()
                    .eq("workflow_id", workflow_id)
                    .execute()
                )
            )
        except Exception as error:
            raise WorkflowPersistenceError("Workflow delete failed") from error

    async def list_by_status(
        self, status: str, *, limit: int = 20, offset: int = 0
    ) -> list[WorkflowState]:
        try:
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .select("*")
                    .eq("current_status", status)
                    .order("created_at")
                    .order("workflow_id")
                    .range(offset, offset + limit - 1)
                    .execute()
                )
            )
            return [self.row_to_state(row) for row in (response.data or [])]
        except Exception as error:
            raise WorkflowPersistenceError("Workflow listing failed") from error

    async def _get_row(self, workflow_id: str) -> dict[str, Any] | None:
        try:
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .select("*")
                    .eq("workflow_id", workflow_id)
                    .limit(1)
                    .execute()
                )
            )
            data = getattr(response, "data", None)
            if data is None and isinstance(response, dict):
                data = response.get("data")
            return data[0] if isinstance(data, list) and data else None
        except Exception as error:
            raise WorkflowPersistenceError("Workflow lookup failed") from error

    @staticmethod
    def state_to_row(state: WorkflowState) -> dict[str, Any]:
        data = state.model_dump(mode="json")
        return {
            "workflow_id": data["workflow_id"],
            "request_id": data["request_id"],
            "last_request_id": data["last_request_id"],
            "raw_text": data["raw_text"],
            "original_text": data["original_text"],
            "accumulated_text": data["accumulated_text"],
            "clarification_count": data["clarification_count"],
            "authenticated_user_id": data["authenticated_user_id"],
            "authenticated_user_role": data["authenticated_user_role"],
            "intake_result": data["intake_result"],
            "claim_context": data["claim_context"],
            "retrieval_result": data["retrieval_result"],
            "fraud_result": data["fraud_result"],
            "human_review_result": data["human_review_result"],
            "guidance_result": data["guidance_result"],
            "reviewer_guidance_result": data["reviewer_guidance_result"],
            "workflow_type": data["workflow_type"],
            "current_status": data["current_status"],
            "missing_fields": data["missing_fields"],
            "requires_clarification": data["requires_clarification"],
            "errors": data["errors"],
            "audit_trail": data["audit_trail"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }

    @staticmethod
    def row_to_state(row: dict[str, Any]) -> WorkflowState:
        try:
            return WorkflowState.model_validate(row)
        except Exception as error:
            raise WorkflowPersistenceError(
                "Stored workflow data is invalid"
            ) from error

    @staticmethod
    def _validate_immutable_fields(
        state: WorkflowState,
        existing: dict[str, Any],
    ) -> None:
        try:
            existing_created_at = datetime.fromisoformat(
                str(existing["created_at"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError) as error:
            raise WorkflowPersistenceError(
                "Stored workflow identity data is invalid"
            ) from error
        if existing.get("authenticated_user_id") != state.authenticated_user_id:
            raise WorkflowPersistenceError("Workflow ownership cannot change")
        if existing_created_at != state.created_at:
            raise WorkflowPersistenceError("Workflow creation time cannot change")
