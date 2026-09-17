"""Central application-level persistence backend selection."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from backend.app.config import Settings, get_settings
from backend.app.orchestrator.repository import (
    InMemoryWorkflowRepository,
    WorkflowRepository,
)
from backend.app.orchestrator.supabase_workflow_repository import (
    SupabaseWorkflowRepository,
)
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.security.user_repository import (
    InMemoryUserRepository,
    UserRepository,
)
from backend.app.services.supabase_service import get_supabase_client


@dataclass(frozen=True)
class ApplicationRepositories:
    users: UserRepository
    workflows: WorkflowRepository


@lru_cache(maxsize=1)
def get_application_repositories() -> ApplicationRepositories:
    """Build one shared repository pair for the configured backend."""

    settings: Settings = get_settings()
    if settings.persistence_backend == "memory":
        return ApplicationRepositories(
            users=InMemoryUserRepository(),
            workflows=InMemoryWorkflowRepository(),
        )

    client = get_supabase_client(settings)
    return ApplicationRepositories(
        users=SupabaseUserRepository(client),
        workflows=SupabaseWorkflowRepository(client),
    )
