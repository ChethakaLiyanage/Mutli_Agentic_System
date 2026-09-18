"""Offline end-to-end authentication tests using the Supabase repository."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.auth import router as auth_router
from backend.app.config import Settings, get_settings
from backend.app.security.dependencies import get_user_repository
from backend.app.security.password import verify_password
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.tests._supabase_fake import FakeSupabaseClient


TEST_SETTINGS = Settings(
    jwt_secret="test-only-secret-that-is-long-and-not-for-production",
    persistence_backend="supabase",
    supabase_url="https://example.supabase.co",
    supabase_service_role_key="test-service-role-key",
)


def _auth_app(repository: SupabaseUserRepository) -> FastAPI:
    application = FastAPI()
    application.include_router(auth_router)
    application.dependency_overrides[get_user_repository] = lambda: repository
    application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    return application


def test_registered_user_survives_repository_and_service_reinitialization() -> None:
    database = FakeSupabaseClient()
    first_repository = SupabaseUserRepository(database)
    registration_app = _auth_app(first_repository)

    with TestClient(registration_app) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "Persistent.Customer@Example.com",
                "password": "securepass123",
            },
        )
        duplicate = client.post(
            "/auth/register",
            json={
                "email": "PERSISTENT.CUSTOMER@example.com",
                "password": "anotherpass123",
            },
        )

    assert registered.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Email is already registered"}

    user_id = registered.json()["user_id"]
    stored = database.rows["users"][user_id]
    assert set(stored) == {
        "user_id",
        "email",
        "password_hash",
        "role",
        "created_at",
    }
    assert stored["email"] == "persistent.customer@example.com"
    assert stored["role"] == "customer"
    assert stored["password_hash"] != "securepass123"
    assert stored["password_hash"].startswith("$argon2id$")
    assert verify_password("securepass123", stored["password_hash"])

    # A new repository and a new request-scoped AuthenticationService can use
    # only the persisted row; no state from the registering service is reused.
    restarted_repository = SupabaseUserRepository(database)
    restarted_app = _auth_app(restarted_repository)
    with TestClient(restarted_app) as client:
        login = client.post(
            "/auth/login",
            json={
                "email": "persistent.customer@example.com",
                "password": "securepass123",
            },
        )
        assert login.status_code == 200

        profile = client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {login.json()['access_token']}"
            },
        )

    assert profile.status_code == 200
    assert profile.json()["user_id"] == user_id
    assert profile.json()["email"] == "persistent.customer@example.com"
    assert profile.json()["role"] == "customer"
