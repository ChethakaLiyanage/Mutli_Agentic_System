"""JWT access-token creation and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import PyJWTError

from backend.app.config import Settings
from backend.app.security.roles import UserRole


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def create_access_token(
    user_id: str,
    role: UserRole,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access token containing identity, role, and expiry."""

    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    return jwt.encode(
        {
            "sub": user_id,
            "role": role.value,
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a token and return its required trusted claims."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp"]},
        )
    except PyJWTError as error:
        raise InvalidAccessTokenError("Invalid access token") from error

    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise InvalidAccessTokenError("Invalid access token")
    try:
        UserRole(payload.get("role"))
    except (TypeError, ValueError) as error:
        raise InvalidAccessTokenError("Invalid access token") from error
    return payload
