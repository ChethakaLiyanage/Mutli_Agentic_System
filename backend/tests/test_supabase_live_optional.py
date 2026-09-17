"""Opt-in live Supabase smoke test; skipped unless explicitly enabled."""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from backend.app.config import get_settings
from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.supabase_workflow_repository import (
    SupabaseWorkflowRepository,
)
from backend.app.security.password import hash_password
from backend.app.security.roles import UserRole
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_INTEGRATION_TESTS") != "1",
    reason="Set RUN_SUPABASE_INTEGRATION_TESTS=1 for live Supabase tests",
)


def test_live_user_and_workflow_round_trip() -> None:
    async def scenario() -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            pytest.skip("Supabase credentials are not configured")

        client = get_supabase_client(settings)
        users = SupabaseUserRepository(client)
        workflows = SupabaseWorkflowRepository(client)
        suffix = uuid4().hex
        user = await users.create_user(
            email=f"codex-test-{suffix}@example.com",
            password_hash=hash_password("temporary-test-password"),
            role=UserRole.CUSTOMER,
        )
        state = WorkflowState(
            workflow_id=f"WF-TEST-{suffix.upper()}",
            request_id=f"REQ-{suffix}",
            last_request_id=f"REQ-{suffix}",
            raw_text="Temporary integration test workflow",
            original_text="Temporary integration test workflow",
            accumulated_text="Temporary integration test workflow",
            authenticated_user_id=user.user_id,
            authenticated_user_role=user.role.value,
        )
        try:
            await workflows.save(state)
            restored = await workflows.get(state.workflow_id)
            assert restored == state
            restored.clarification_count = 1
            await workflows.save(restored)
            updated = await workflows.get(state.workflow_id)
            assert updated is not None
            assert updated.clarification_count == 1
        finally:
            await workflows.delete(state.workflow_id)
            await asyncio.to_thread(
                lambda: (
                    client.table("users")
                    .delete()
                    .eq("user_id", user.user_id)
                    .execute()
                )
            )

    asyncio.run(scenario())
