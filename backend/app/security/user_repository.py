"""Repository abstraction and process-local storage for authentication users."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr

from backend.app.security.roles import UserRole


class UserAlreadyExistsError(ValueError):
    """Raised when a normalized email address is already registered."""


class UserRecord(BaseModel):
    """Internal persisted user model; never use it as an API response."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: EmailStr
    password_hash: str
    role: UserRole
    created_at: datetime


@runtime_checkable
class UserRepository(Protocol):
    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> UserRecord:
        ...

    async def get_by_email(self, email: str) -> UserRecord | None:
        ...

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        ...

    async def list_users(self, role: UserRole | None = None) -> list[UserRecord]:
        ...


class InMemoryUserRepository:
    """Prototype user storage that disappears when the process restarts."""

    def __init__(self) -> None:
        self._users_by_id: dict[str, str] = {}
        self._user_ids_by_email: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> UserRecord:
        normalized_email = email.strip().lower()
        async with self._lock:
            if normalized_email in self._user_ids_by_email:
                raise UserAlreadyExistsError("Email is already registered")
            user = UserRecord(
                user_id=f"USR-{uuid4().hex.upper()}",
                email=normalized_email,
                password_hash=password_hash,
                role=role,
                created_at=datetime.now(timezone.utc),
            )
            self._users_by_id[user.user_id] = user.model_dump_json()
            self._user_ids_by_email[normalized_email] = user.user_id
        return user.model_copy(deep=True)

    async def get_by_email(self, email: str) -> UserRecord | None:
        normalized_email = email.strip().lower()
        async with self._lock:
            user_id = self._user_ids_by_email.get(normalized_email)
            serialized = self._users_by_id.get(user_id) if user_id else None
        return self._restore(serialized)

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        async with self._lock:
            serialized = self._users_by_id.get(user_id)
        return self._restore(serialized)

    async def list_users(self, role: UserRole | None = None) -> list[UserRecord]:
        async with self._lock:
            users = [self._restore(s) for s in self._users_by_id.values()]
        valid_users = [u for u in users if u is not None]
        if role is not None:
            return [u for u in valid_users if u.role == role]
        return valid_users

    @staticmethod
    def _restore(serialized: str | None) -> UserRecord | None:
        if serialized is None:
            return None
        return UserRecord.model_validate_json(serialized)
