"""Supabase-backed implementation of durable workflow persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.graph.state import WorkflowState
from backend.app.services.repository_errors import WorkflowPersistenceError


REMOTE_CHECK_CONSTRAINT_STATUSES = {
    "received",
    "intake_processing",
    "intake_complete",
    "awaiting_clarification",
    "manual_assistance_required",
    "information_retrieval",
    "retrieval_complete",
    "claim_information_retrieval",
    "fraud_triage",
    "awaiting_human_review",
    "approved",
    "rejected",
    "more_information_required",
    "escalated",
    "guidance_processing",
    "guidance_generation",
    "completed",
    "failed",
}


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
            db_row = dict(row)
            # The remote Supabase workflows table does not yet have reviewer_guidance_result.
            # Preserve it in guidance_result JSONB column so it is not lost, then pop it.
            rev_guidance = db_row.pop("reviewer_guidance_result", None)
            if rev_guidance is not None:
                g_res = dict(db_row.get("guidance_result") or {})
                g_res["_reviewer_guidance_result"] = rev_guidance
                db_row["guidance_result"] = g_res

            await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .upsert(db_row, on_conflict="workflow_id")
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
            is_mapped = status not in REMOTE_CHECK_CONSTRAINT_STATUSES
            query_status = "awaiting_human_review" if is_mapped else status
            fetch_limit = limit * 4 if is_mapped else limit
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("workflows")
                    .select("*")
                    .eq("current_status", query_status)
                    .order("created_at")
                    .order("workflow_id")
                    .range(offset, offset + fetch_limit - 1)
                    .execute()
                )
            )
            states = [self.row_to_state(row) for row in (response.data or [])]
            if is_mapped:
                matched = [st for st in states if st.current_status.value == status]
                return matched[:limit]
            return states[:limit]
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
        canonical_status = data["current_status"]
        db_status = canonical_status
        audit = list(data.get("audit_trail") or [])

        # Ensure compatibility with remote DB check constraint
        if canonical_status not in REMOTE_CHECK_CONSTRAINT_STATUSES:
            db_status = "awaiting_human_review"
            audit.append({
                "step": "_canonical_status",
                "status": "success",
                "message": f"CanonicalStatus:{canonical_status}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

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
            "current_status": db_status,
            "missing_fields": data["missing_fields"],
            "requires_clarification": data["requires_clarification"],
            "errors": data["errors"],
            "audit_trail": audit,
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }

    @staticmethod
    def row_to_state(row: dict[str, Any]) -> WorkflowState:
        try:
            state_dict = dict(row)
            audit = state_dict.get("audit_trail") or []

            if state_dict.get("current_status") == "awaiting_human_review":
                found_status = None
                for a in reversed(audit):
                    if isinstance(a, dict):
                        msg = a.get("message") or ""
                        if msg.startswith("CanonicalStatus:"):
                            found_status = msg.split("CanonicalStatus:", 1)[1].strip()
                            break
                        if a.get("step") == "_canonical_status" and a.get("status") not in {
                            "started", "success", "awaiting_input", "failed"
                        }:
                            found_status = a.get("status")
                            break

                if not found_status and isinstance(state_dict.get("claim_context"), dict):
                    found_status = state_dict["claim_context"].get("canonical_workflow_status")

                if found_status:
                    state_dict["current_status"] = found_status
                else:
                    if audit and any(isinstance(a, dict) and a.get("step") == "awaiting_documents" for a in audit):
                        state_dict["current_status"] = "awaiting_documents"

            # Clean audit_trail so Pydantic model_validate succeeds on legacy/corrupted entries
            cleaned_audit = []
            for a in audit:
                if isinstance(a, dict):
                    if a.get("step") == "_canonical_status":
                        continue
                    if a.get("status") not in {"started", "success", "awaiting_input", "failed"}:
                        a = dict(a)
                        a["status"] = "success"
                cleaned_audit.append(a)
            state_dict["audit_trail"] = cleaned_audit

            # Clean claim_context extra forbidden fields
            if isinstance(state_dict.get("claim_context"), dict):
                cc = dict(state_dict["claim_context"])
                cc.pop("canonical_workflow_status", None)
                state_dict["claim_context"] = cc

            if state_dict.get("reviewer_guidance_result") is None:
                g_res = state_dict.get("guidance_result")
                if isinstance(g_res, dict) and "_reviewer_guidance_result" in g_res:
                    state_dict["reviewer_guidance_result"] = g_res["_reviewer_guidance_result"]

            return WorkflowState.model_validate(state_dict)
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
