"""Persistence abstraction for serializable Orchestrator workflow state."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from backend.app.graph.state import WorkflowState


@runtime_checkable
class WorkflowRepository(Protocol):
    """Async storage boundary for long-lived workflow state."""

    async def save(self, state: WorkflowState) -> None:
        """Create or replace a workflow snapshot."""

        ...

    async def get(self, workflow_id: str) -> WorkflowState | None:
        """Return an isolated workflow snapshot when it exists."""

        ...

    async def delete(self, workflow_id: str) -> None:
        """Delete a workflow when it exists."""

        ...

    async def list_by_status(
        self, status: str, *, limit: int = 20, offset: int = 0
    ) -> list[WorkflowState]: ...


class InMemoryWorkflowRepository:
    """Process-local prototype storage that is lost when the process restarts."""

    def __init__(self) -> None:
        self._serialized_states: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def save(self, state: WorkflowState) -> None:
        serialized = state.model_dump_json()
        async with self._lock:
            self._serialized_states[state.workflow_id] = serialized

    async def get(self, workflow_id: str) -> WorkflowState | None:
        async with self._lock:
            serialized = self._serialized_states.get(workflow_id)
        if serialized is None:
            return None
        return WorkflowState.model_validate_json(serialized)

    async def delete(self, workflow_id: str) -> None:
        async with self._lock:
            self._serialized_states.pop(workflow_id, None)

    async def list_by_status(
        self, status: str, *, limit: int = 20, offset: int = 0
    ) -> list[WorkflowState]:
        async with self._lock:
            states = [
                WorkflowState.model_validate_json(item)
                for item in self._serialized_states.values()
            ]
        matching = sorted(
            (item for item in states if item.current_status.value == status),
            key=lambda item: (item.created_at, item.workflow_id),
        )
        return matching[offset:offset + limit]
