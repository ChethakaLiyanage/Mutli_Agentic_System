"""Offline tests for Supabase workflow persistence and serialization."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import (
    AuditEventStatus,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.orchestrator.supabase_workflow_repository import (
    SupabaseWorkflowRepository,
)
from backend.app.schemas.intake import (
    IncidentInformation,
    IntakeData,
    IntakeResponse,
    IntentResult,
)
from backend.app.schemas.orchestrator import AuditEvent, OrchestratorError
from backend.app.services.repository_errors import WorkflowPersistenceError
from backend.tests._supabase_fake import FakePostgrestError, FakeSupabaseClient


def make_state() -> WorkflowState:
    now = datetime.now(timezone.utc)
    return WorkflowState(
        workflow_id="WF-SUPABASE-TEST",
        request_id="REQ001",
        last_request_id="REQ002",
        raw_text="My car was damaged.",
        original_text="My car was damaged.",
        accumulated_text=(
            "My car was damaged. A bus hit it yesterday in Kandy."
        ),
        clarification_count=1,
        authenticated_user_id="USR-OWNER",
        authenticated_user_role="customer",
        intake_result=IntakeResponse(
            request_id="REQ002",
            status="success",
            data=IntakeData(
                intent=IntentResult(label="claim_submission", confidence=0.82),
                incident=IncidentInformation(
                    type="vehicle_collision",
                    date_text="yesterday",
                    normalized_date="2026-09-16",
                    location="Kandy",
                ),
            ),
        ),
        retrieval_result={"documents": ["POL-1"]},
        workflow_type=WorkflowType.CLAIM_SUBMISSION,
        current_status=WorkflowStatus.INTAKE_COMPLETE,
        missing_fields=[],
        requires_clarification=False,
        errors=[
            OrchestratorError(
                code="PRIOR_WARNING",
                message="A controlled warning",
                step="test",
            )
        ],
        audit_trail=[
            AuditEvent(
                step="claim_intake",
                status=AuditEventStatus.SUCCESS,
                message="Claim intake completed",
                timestamp=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )


def test_state_row_round_trip_preserves_nested_models_enums_and_ownership() -> None:
    state = make_state()

    row = SupabaseWorkflowRepository.state_to_row(state)
    restored = SupabaseWorkflowRepository.row_to_state(row)

    assert restored == state
    assert restored.workflow_type is WorkflowType.CLAIM_SUBMISSION
    assert restored.current_status is WorkflowStatus.INTAKE_COMPLETE
    assert restored.intake_result is not None
    assert restored.intake_result.data.incident.location == "Kandy"
    assert restored.audit_trail[0].timestamp.tzinfo is not None
    assert restored.authenticated_user_id == "USR-OWNER"
    assert restored.clarification_count == 1


def test_first_save_update_get_and_delete_use_one_workflow_row() -> None:
    async def scenario() -> None:
        client = FakeSupabaseClient()
        repository = SupabaseWorkflowRepository(client)
        state = make_state()
        original_created_at = state.created_at
        original_updated_at = state.updated_at

        await repository.save(state)
        assert len(client.rows["workflows"]) == 1
        assert client.last_on_conflict == "workflow_id"
        assert state.updated_at >= original_updated_at

        restored = await repository.get(state.workflow_id)
        assert restored == state
        assert restored is not state
        assert restored.created_at == original_created_at

        state.current_status = WorkflowStatus.FAILED
        state.errors.append(
            OrchestratorError(code="TEST", message="Test error", step="test")
        )
        previous_updated_at = state.updated_at
        await repository.save(state)
        assert len(client.rows["workflows"]) == 1
        assert state.updated_at >= previous_updated_at
        updated = await repository.get(state.workflow_id)
        assert updated is not None
        assert updated.current_status is WorkflowStatus.FAILED
        assert updated.created_at == original_created_at

        await repository.delete(state.workflow_id)
        assert await repository.get(state.workflow_id) is None
        assert await repository.get("WF-UNKNOWN") is None

    asyncio.run(scenario())


def test_updates_cannot_transfer_owner_or_rewrite_creation_time() -> None:
    async def scenario() -> None:
        client = FakeSupabaseClient()
        repository = SupabaseWorkflowRepository(client)
        state = make_state()
        await repository.save(state)

        transferred = state.model_copy(deep=True)
        transferred.authenticated_user_id = "USR-OTHER"
        with pytest.raises(WorkflowPersistenceError, match="ownership"):
            await repository.save(transferred)

        rewritten = state.model_copy(deep=True)
        rewritten.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(WorkflowPersistenceError, match="creation time"):
            await repository.save(rewritten)

        stored = await repository.get(state.workflow_id)
        assert stored is not None
        assert stored.authenticated_user_id == "USR-OWNER"
        assert stored.created_at == state.created_at

    asyncio.run(scenario())


def test_workflow_database_and_invalid_row_failures_are_controlled() -> None:
    async def scenario() -> None:
        client = FakeSupabaseClient()
        repository = SupabaseWorkflowRepository(client)
        client.fail_next = FakePostgrestError("private query failure")
        with pytest.raises(WorkflowPersistenceError, match="lookup"):
            await repository.get("WF-TEST")

        client.rows["workflows"]["WF-BAD"] = {
            "workflow_id": "WF-BAD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with pytest.raises(WorkflowPersistenceError, match="Stored workflow data"):
            await repository.get("WF-BAD")

        client.fail_next = FakePostgrestError("private delete failure")
        with pytest.raises(WorkflowPersistenceError, match="delete"):
            await repository.delete("WF-BAD")

    asyncio.run(scenario())
