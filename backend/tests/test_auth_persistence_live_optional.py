"""Opt-in live Supabase registration persistence verification.

Run with RUN_SUPABASE_AUTH_PERSISTENCE=1. The test deletes only the synthetic
user that it creates.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.auth import router as auth_router
from backend.app.config import get_settings
from backend.app.security.password import verify_password
from backend.app.security.roles import UserRole
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.services.persistence import get_application_repositories
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_AUTH_PERSISTENCE") != "1",
    reason="live Supabase auth persistence test is opt-in",
)


def test_live_registration_persists_and_authenticates_after_reinitialization() -> None:
    settings = get_settings()
    assert settings.persistence_backend == "supabase"
    client = get_supabase_client(settings)
    email = f"codex-auth-{uuid4().hex}@example.com"
    password = "Live-test-password-2026"
    created_user_id: str | None = None
    application = FastAPI()
    application.include_router(auth_router)

    get_application_repositories.cache_clear()
    assert isinstance(
        get_application_repositories().users,
        SupabaseUserRepository,
    )

    try:
        with TestClient(application) as api:
            registered = api.post(
                "/auth/register",
                json={"email": email, "password": password},
            )
            assert registered.status_code == 201
            created_user_id = registered.json()["user_id"]

            duplicate = api.post(
                "/auth/register",
                json={"email": email.upper(), "password": password},
            )
            assert duplicate.status_code == 409

            stored_rows = (
                client.table("users")
                .select("user_id,email,password_hash,role,created_at")
                .eq("user_id", created_user_id)
                .limit(1)
                .execute()
                .data
            )
            assert len(stored_rows) == 1
            stored = stored_rows[0]
            assert stored["email"] == email
            assert stored["role"] == UserRole.CUSTOMER.value
            assert stored["password_hash"] != password
            assert verify_password(password, stored["password_hash"])

            # Rebuild the configured repository bundle to simulate a new
            # application process with no in-memory user state.
            get_application_repositories.cache_clear()
            assert isinstance(
                get_application_repositories().users,
                SupabaseUserRepository,
            )
            login = api.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200

            profile = api.get(
                "/auth/me",
                headers={
                    "Authorization": f"Bearer {login.json()['access_token']}"
                },
            )
            assert profile.status_code == 200
            assert profile.json()["user_id"] == created_user_id
            assert profile.json()["email"] == email
            assert profile.json()["role"] == UserRole.CUSTOMER.value
    finally:
        if created_user_id is not None:
            (
                client.table("users")
                .delete()
                .eq("user_id", created_user_id)
                .execute()
            )
        get_application_repositories.cache_clear()
