"""Authentication, token, repository, and role-authorization tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.config import Settings, get_settings
from backend.app.main import app
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.dependencies import (
    get_current_user,
    get_user_repository,
    require_roles,
)
from backend.app.security.jwt import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
)
from backend.app.security.password import hash_password, verify_password
from backend.app.security.roles import UserRole, role_is_allowed
from backend.app.security.user_repository import InMemoryUserRepository


TEST_SETTINGS = Settings(
    jwt_secret="test-only-secret-that-is-long-and-not-for-production",
    jwt_access_token_expire_minutes=15,
)


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, InMemoryUserRepository]]:
    repository = InMemoryUserRepository()
    app.dependency_overrides[get_user_repository] = lambda: repository
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def seed_user(
    repository: InMemoryUserRepository,
    email: str = "customer@example.com",
    password: str = "securepass123",
    role: UserRole = UserRole.CUSTOMER,
):
    return asyncio.run(
        repository.create_user(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
    )


def login(client: TestClient, email: str = "customer@example.com"):
    return client.post(
        "/auth/login",
        json={"email": email, "password": "securepass123"},
    )


def test_public_registration_is_strictly_disabled_and_returns_403(
    auth_client: tuple[TestClient, InMemoryUserRepository],
) -> None:
    client, repository = auth_client

    response = client.post(
        "/auth/register",
        json={"email": "customer@example.com", "password": "securepass123"},
    )

    assert response.status_code == 403
    assert "Public customer registration is disabled" in response.json()["detail"]


def test_login_uses_generic_failures_and_returns_bearer_token(
    auth_client: tuple[TestClient, InMemoryUserRepository],
) -> None:
    client, repository = auth_client
    seed_user(repository, "customer@example.com", "securepass123")

    success = login(client)
    wrong_password = client.post(
        "/auth/login",
        json={"email": "customer@example.com", "password": "wrong"},
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "wrong"},
    )

    assert success.status_code == 200
    assert success.json()["token_type"] == "bearer"
    assert success.json()["access_token"]
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {
        "detail": "Invalid email or password"
    }


def test_jwt_validation_rejects_bad_signature_malformed_and_expired_tokens() -> None:
    valid = create_access_token(
        "USR-ONE",
        UserRole.CUSTOMER,
        TEST_SETTINGS,
    )
    claims = decode_access_token(valid, TEST_SETTINGS)
    assert claims["sub"] == "USR-ONE"
    assert claims["role"] == "customer"

    wrong_settings = Settings(jwt_secret="different-test-secret-long-enough")
    expired = create_access_token(
        "USR-ONE",
        UserRole.CUSTOMER,
        TEST_SETTINGS,
        expires_delta=timedelta(seconds=-1),
    )
    for token, settings in [
        (valid, wrong_settings),
        ("not-a-jwt", TEST_SETTINGS),
        (expired, TEST_SETTINGS),
    ]:
        with pytest.raises(InvalidAccessTokenError):
            decode_access_token(token, settings)


def test_auth_me_requires_valid_token_and_uses_stored_role(
    auth_client: tuple[TestClient, InMemoryUserRepository],
) -> None:
    client, repository = auth_client
    user = seed_user(repository, "customer@example.com", "securepass123")
    token = login(client).json()["access_token"]

    valid = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    missing = client.get("/auth/me")
    malformed = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    wrong_role_token = create_access_token(
        user.user_id,
        UserRole.ADMIN,
        TEST_SETTINGS,
    )
    role_mismatch = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {wrong_role_token}"},
    )

    assert valid.status_code == 200
    assert valid.json()["user_id"] == user.user_id
    assert valid.json()["role"] == "customer"
    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert role_mismatch.status_code == 401
    assert asyncio.run(repository.get_by_id(user.user_id)) is not None


def test_role_helpers_enforce_only_declared_roles() -> None:
    assert role_is_allowed(UserRole.CUSTOMER, [UserRole.CUSTOMER])
    assert not role_is_allowed(UserRole.ADMIN, [UserRole.CUSTOMER])

    role_app = FastAPI()
    officer_only = require_roles(UserRole.CLAIMS_OFFICER)

    @role_app.get("/officer")
    async def officer_route(
        _user: AuthenticatedUser = Depends(officer_only),
    ) -> dict[str, bool]:
        return {"allowed": True}

    role_client = TestClient(role_app)

    def user(role: UserRole) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="USR-ROLE",
            email="role@example.com",
            role=role,
            created_at=datetime.now(timezone.utc),
        )

    role_app.dependency_overrides[get_current_user] = lambda: user(
        UserRole.CLAIMS_OFFICER
    )
    assert role_client.get("/officer").status_code == 200
    role_app.dependency_overrides[get_current_user] = lambda: user(UserRole.CUSTOMER)
    assert role_client.get("/officer").status_code == 403
    role_app.dependency_overrides[get_current_user] = lambda: user(UserRole.ADMIN)
    assert role_client.get("/officer").status_code == 403


def test_auth_routes_and_bearer_security_appear_in_openapi(
    auth_client: tuple[TestClient, InMemoryUserRepository],
) -> None:
    client, _ = auth_client
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert paths["/orchestrator/process"]["post"]["security"]
