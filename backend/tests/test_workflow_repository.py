"""Tests for process-local workflow persistence."""

from __future__ import annotations

import asyncio

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.repository import InMemoryWorkflowRepository


def make_state(workflow_id: str, request_id: str = "REQ001") -> WorkflowState:
    return WorkflowState(
        workflow_id=workflow_id,
        request_id=request_id,
        last_request_id=request_id,
        raw_text="A valid request",
        original_text="A valid request",
        accumulated_text="A valid request",
    )


def test_save_and_get_return_isolated_snapshots() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        original = make_state("WF-ONE")
        await repository.save(original)

        first = await repository.get("WF-ONE")
        assert first == original
        assert first is not original

        assert first is not None
        first.missing_fields.append("location")
        second = await repository.get("WF-ONE")
        assert second is not None
        assert second.missing_fields == []

    asyncio.run(scenario())


def test_unknown_update_delete_and_workflow_isolation() -> None:
    async def scenario() -> None:
        repository = InMemoryWorkflowRepository()
        assert await repository.get("WF-MISSING") is None

        first = make_state("WF-ONE")
        second = make_state("WF-TWO", request_id="REQ002")
        await repository.save(first)
        await repository.save(second)

        first.clarification_count = 2
        await repository.save(first)
        saved_first = await repository.get("WF-ONE")
        saved_second = await repository.get("WF-TWO")
        assert saved_first is not None
        assert saved_first.clarification_count == 2
        assert saved_second is not None
        assert saved_second.clarification_count == 0

        await repository.delete("WF-ONE")
        assert await repository.get("WF-ONE") is None
        assert await repository.get("WF-TWO") is not None
        await repository.delete("WF-MISSING")

    asyncio.run(scenario())
