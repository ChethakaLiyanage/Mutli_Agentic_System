"""Tests for admin customer creation, role enforcement, and policy binding."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings, get_settings
from backend.app.main import app
from backend.app.orchestrator.claim_repository import (
    ClaimRepository,
    InMemoryClaimRepository,
    get_claim_repository,
)
from backend.app.schemas.admin import PolicyCategory
from backend.app.security.dependencies import get_user_repository
from backend.app.security.jwt import create_access_token
from backend.app.security.password import hash_password, verify_password
from backend.app.security.roles import UserRole
from backend.app.security.user_repository import (
    InMemoryUserRepository,
    UserRepository,
)


TEST_SETTINGS = Settings(
    jwt_secret="test-only-secret-that-is-long-and-not-for-production",
    jwt_access_token_expire_minutes=15,
)


@pytest.fixture
def test_setup() -> Iterator[tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository]]:
    user_repo = InMemoryUserRepository()
    claim_repo = InMemoryClaimRepository()

    app.dependency_overrides[get_user_repository] = lambda: user_repo
    app.dependency_overrides[get_claim_repository] = lambda: claim_repo
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS

    with TestClient(app) as client:
        yield client, user_repo, claim_repo

    app.dependency_overrides.clear()


def make_auth_headers(user_id: str, role: UserRole) -> dict[str, str]:
    token = create_access_token(user_id, role, TEST_SETTINGS)
    return {"Authorization": f"Bearer {token}"}


def test_public_registration_is_strictly_forbidden(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, _, _ = test_setup
    response = client.post(
        "/auth/register",
        json={"email": "attacker@example.com", "password": "password123"},
    )
    assert response.status_code == 403
    assert "Public customer registration is disabled" in response.json()["detail"]


def test_admin_customer_creation_requires_authentication(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, _, _ = test_setup
    response = client.post(
        "/admin/customers",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "securepass123",
            "policy_type": "full_comprehensive",
        },
    )
    assert response.status_code == 401


def test_admin_customer_creation_rejects_non_admin_users(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, _ = test_setup

    customer_user = asyncio.run(
        user_repo.create_user(
            email="cust@example.com",
            password_hash=hash_password("pass12345"),
            role=UserRole.CUSTOMER,
        )
    )

    headers = make_auth_headers(customer_user.user_id, UserRole.CUSTOMER)
    response = client.post(
        "/admin/customers",
        json={
            "name": "Another Customer",
            "email": "another@example.com",
            "password": "securepass123",
            "policy_type": "full_comprehensive",
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_admin_can_create_customer_with_policy_category(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, claim_repo = test_setup

    admin_user = asyncio.run(
        user_repo.create_user(
            email="admin@example.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
    )
    headers = make_auth_headers(admin_user.user_id, UserRole.ADMIN)

    payload = {
        "name": "Alice Smith",
        "email": "alice.smith@example.com",
        "password": "SecureCustomerPass123",
        "policy_type": "partial_comprehensive",
    }

    response = client.post("/admin/customers", json=payload, headers=headers)
    assert response.status_code == 201

    body = response.json()
    assert body["user_id"].startswith("USR-")
    assert body["email"] == "alice.smith@example.com"
    assert body["name"] == "Alice Smith"
    assert body["role"] == "customer"
    assert body["policy_type"] == "partial_comprehensive"
    assert body["policy_number"].startswith("POL-")
    assert "password" not in body
    assert "password_hash" not in body

    # Verify password was stored with Argon2id hash, not plaintext
    stored_user = asyncio.run(user_repo.get_by_email("alice.smith@example.com"))
    assert stored_user is not None
    assert stored_user.password_hash != "SecureCustomerPass123"
    assert stored_user.password_hash.startswith("$argon2")
    assert verify_password("SecureCustomerPass123", stored_user.password_hash)

    # Verify policy record in claim repository
    user_policies = claim_repo.list_policies_for_customer(stored_user.user_id)
    assert len(user_policies) == 1
    assert user_policies[0]["policy_type"] == "partial_comprehensive"
    assert user_policies[0]["status"] == "active"


def test_duplicate_email_rejected_with_409(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, _ = test_setup

    admin = asyncio.run(
        user_repo.create_user(
            email="admin@example.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
    )
    headers = make_auth_headers(admin.user_id, UserRole.ADMIN)

    payload = {
        "name": "Bob Jones",
        "email": "bob@example.com",
        "password": "Password12345",
        "policy_type": "third_party",
    }

    res1 = client.post("/admin/customers", json=payload, headers=headers)
    assert res1.status_code == 201

    res2 = client.post("/admin/customers", json=payload, headers=headers)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_invalid_policy_type_rejected_with_422(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, _ = test_setup

    admin = asyncio.run(
        user_repo.create_user(
            email="admin@example.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
    )
    headers = make_auth_headers(admin.user_id, UserRole.ADMIN)

    payload = {
        "name": "Charlie",
        "email": "charlie@example.com",
        "password": "Password12345",
        "policy_type": "mega_super_comprehensive",
    }

    response = client.post("/admin/customers", json=payload, headers=headers)
    assert response.status_code == 422


def test_created_customer_can_login_and_access_auth_me(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, _ = test_setup

    admin = asyncio.run(
        user_repo.create_user(
            email="admin@example.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
    )
    headers = make_auth_headers(admin.user_id, UserRole.ADMIN)

    create_res = client.post(
        "/admin/customers",
        json={
            "name": "David Miller",
            "email": "david@example.com",
            "password": "DavidSecretPassword2026",
            "policy_type": "full_comprehensive",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    created = create_res.json()

    # Customer logs in
    login_res = client.post(
        "/auth/login",
        json={
            "email": "david@example.com",
            "password": "DavidSecretPassword2026",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["token_type"] == "bearer"
    access_token = login_data["access_token"]

    # Customer calls /auth/me
    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user_id"] == created["user_id"]
    assert me_data["email"] == "david@example.com"
    assert me_data["role"] == "customer"


def test_admin_can_list_customers_with_assigned_policies(
    test_setup: tuple[TestClient, InMemoryUserRepository, InMemoryClaimRepository],
) -> None:
    client, user_repo, claim_repo = test_setup

    admin = asyncio.run(
        user_repo.create_user(
            email="admin@example.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
    )
    headers = make_auth_headers(admin.user_id, UserRole.ADMIN)

    # Create 3 customers with different policy types
    categories: list[PolicyCategory] = [
        "full_comprehensive",
        "partial_comprehensive",
        "third_party",
    ]
    for i, cat in enumerate(categories):
        client.post(
            "/admin/customers",
            json={
                "name": f"Customer {i}",
                "email": f"cust{i}@example.com",
                "password": f"Pass{i}Secure123",
                "policy_type": cat,
            },
            headers=headers,
        )

    # Admin lists customers
    list_res = client.get("/admin/customers", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 3
    customers = list_data["customers"]
    assert len(customers) == 3

    policy_types = {c["policy_type"] for c in customers}
    assert policy_types == {"full_comprehensive", "partial_comprehensive", "third_party"}
