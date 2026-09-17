"""Registration, credential verification, and token issuance."""

from __future__ import annotations

from backend.app.config import Settings
from backend.app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
)
from backend.app.security.jwt import create_access_token
from backend.app.security.password import hash_password, verify_password
from backend.app.security.roles import UserRole
from backend.app.security.user_repository import UserRecord, UserRepository


class InvalidCredentialsError(ValueError):
    """Generic login failure that does not reveal which credential failed."""


_DUMMY_PASSWORD_HASH = hash_password("invalid-credential-placeholder")


class AuthenticationService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def register(self, request: UserRegisterRequest) -> UserPublic:
        user = await self.repository.create_user(
            email=str(request.email),
            password_hash=hash_password(request.password),
            role=UserRole.CUSTOMER,
        )
        return self._to_public(user)

    async def login(self, request: UserLoginRequest) -> TokenResponse:
        user = await self.repository.get_by_email(str(request.email))
        password_hash = (
            user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
        )
        password_matches = verify_password(request.password, password_hash)
        if user is None or not password_matches:
            raise InvalidCredentialsError("Invalid email or password")
        return TokenResponse(
            access_token=create_access_token(
                user.user_id,
                user.role,
                self.settings,
            )
        )

    @staticmethod
    def _to_public(user: UserRecord) -> UserPublic:
        return UserPublic(
            user_id=user.user_id,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
        )
