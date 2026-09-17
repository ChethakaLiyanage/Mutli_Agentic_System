"""Tests for explicit memory/Supabase backend selection."""

from __future__ import annotations

import pytest

from backend.app.config import Settings
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.supabase_workflow_repository import (
    SupabaseWorkflowRepository,
)
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.security.user_repository import InMemoryUserRepository
from backend.app.services import persistence


def test_supabase_configuration_requires_url_and_service_role_key() -> None:
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        Settings(jwt_secret="test-secret", persistence_backend="supabase")
    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY"):
        Settings(
            jwt_secret="test-secret",
            persistence_backend="supabase",
            supabase_url="https://example.supabase.co",
        )


def test_memory_backend_builds_shared_in_memory_repositories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence.get_application_repositories.cache_clear()
    monkeypatch.setattr(
        persistence,
        "get_settings",
        lambda: Settings(jwt_secret="test-secret", persistence_backend="memory"),
    )

    first = persistence.get_application_repositories()
    second = persistence.get_application_repositories()

    assert first is second
    assert isinstance(first.users, InMemoryUserRepository)
    assert isinstance(first.workflows, InMemoryWorkflowRepository)
    persistence.get_application_repositories.cache_clear()


def test_supabase_backend_reuses_one_client_for_both_repositories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence.get_application_repositories.cache_clear()
    fake_client = object()
    settings = Settings(
        jwt_secret="test-secret",
        persistence_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
    )
    monkeypatch.setattr(persistence, "get_settings", lambda: settings)
    monkeypatch.setattr(
        persistence,
        "get_supabase_client",
        lambda _settings: fake_client,
    )

    repositories = persistence.get_application_repositories()

    assert isinstance(repositories.users, SupabaseUserRepository)
    assert isinstance(repositories.workflows, SupabaseWorkflowRepository)
    assert repositories.users._client is fake_client
    assert repositories.workflows._client is fake_client
    persistence.get_application_repositories.cache_clear()
