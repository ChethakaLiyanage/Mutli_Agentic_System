"""Supabase-backed implementation of the user repository contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.security.roles import UserRole
from backend.app.security.user_repository import (
    UserAlreadyExistsError,
    UserRecord,
)
from backend.app.services.repository_errors import UserPersistenceError


def _response_data(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    return data if isinstance(data, list) else []


def _is_unique_violation(error: Exception) -> bool:
    code = getattr(error, "code", None)
    text = str(error).lower()
    return code == "23505" or "duplicate key" in text or "unique" in text


class SupabaseUserRepository:
    """Persist application-managed Argon2 user records in Supabase Postgres."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> UserRecord:
        normalized_email = email.strip().lower()
        user = UserRecord(
            user_id=f"USR-{uuid4().hex.upper()}",
            email=normalized_email,
            password_hash=password_hash,
            role=role,
            created_at=datetime.now(timezone.utc),
        )
        row = user.model_dump(mode="json")
        try:
            response = await asyncio.to_thread(
                lambda: self._client.table("users").insert(row).execute()
            )
            rows = _response_data(response)
            return self._from_row(rows[0] if rows else row)
        except UserAlreadyExistsError:
            raise
        except Exception as error:
            if _is_unique_violation(error):
                raise UserAlreadyExistsError(
                    "Email is already registered"
                ) from error
            raise UserPersistenceError("User persistence failed") from error

    async def get_by_email(self, email: str) -> UserRecord | None:
        return await self._get_one("email", email.strip().lower())

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        return await self._get_one("user_id", user_id)

    async def _get_one(self, column: str, value: str) -> UserRecord | None:
        try:
            response = await asyncio.to_thread(
                lambda: (
                    self._client.table("users")
                    .select("*")
                    .eq(column, value)
                    .limit(1)
                    .execute()
                )
            )
            rows = _response_data(response)
            return self._from_row(rows[0]) if rows else None
        except UserPersistenceError:
            raise
        except Exception as error:
            raise UserPersistenceError("User lookup failed") from error

    @staticmethod
    def _from_row(row: dict[str, Any]) -> UserRecord:
        try:
            return UserRecord.model_validate(row)
        except Exception as error:
            raise UserPersistenceError("Stored user data is invalid") from error
