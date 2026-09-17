"""Offline tests for the Supabase user repository adapter."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.security.roles import UserRole
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.security.user_repository import UserAlreadyExistsError
from backend.app.services.repository_errors import UserPersistenceError
from backend.tests._supabase_fake import FakePostgrestError, FakeSupabaseClient


def test_create_and_lookup_user_with_normalized_email_and_exact_hash() -> None:
    async def scenario() -> None:
        client = FakeSupabaseClient()
        repository = SupabaseUserRepository(client)
        password_hash = "$argon2id$exact-persisted-hash"

        created = await repository.create_user(
            email="Customer@Example.COM",
            password_hash=password_hash,
            role=UserRole.CUSTOMER,
        )
        by_email = await repository.get_by_email("CUSTOMER@example.com")
        by_id = await repository.get_by_id(created.user_id)

        assert created.email == "customer@example.com"
        assert created.password_hash == password_hash
        assert created.role is UserRole.CUSTOMER
        assert by_email == created
        assert by_id == created
        assert by_email is not created
        assert await repository.get_by_id("USR-MISSING") is None

    asyncio.run(scenario())


def test_duplicate_email_maps_to_existing_domain_exception() -> None:
    async def scenario() -> None:
        repository = SupabaseUserRepository(FakeSupabaseClient())
        await repository.create_user(
            email="duplicate@example.com",
            password_hash="hash-one",
            role=UserRole.CUSTOMER,
        )
        with pytest.raises(UserAlreadyExistsError):
            await repository.create_user(
                email="DUPLICATE@example.com",
                password_hash="hash-two",
                role=UserRole.CUSTOMER,
            )

    asyncio.run(scenario())


def test_user_database_and_invalid_row_failures_are_controlled() -> None:
    async def scenario() -> None:
        client = FakeSupabaseClient()
        repository = SupabaseUserRepository(client)
        client.fail_next = FakePostgrestError("private database failure")
        with pytest.raises(UserPersistenceError, match="User lookup failed"):
            await repository.get_by_email("customer@example.com")

        client.rows["users"]["USR-BAD"] = {
            "user_id": "USR-BAD",
            "email": "not-an-email",
        }
        with pytest.raises(UserPersistenceError, match="Stored user data is invalid"):
            await repository.get_by_id("USR-BAD")

    asyncio.run(scenario())
