"""FastAPI authentication and role-authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import Settings, get_settings
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.jwt import InvalidAccessTokenError, decode_access_token
from backend.app.security.roles import UserRole, role_is_allowed
from backend.app.security.user_repository import UserRepository
from backend.app.services.persistence import get_application_repositories
from backend.app.services.repository_errors import RepositoryError


bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository() -> UserRepository:
    """Resolve auth storage from the application's configured repository pair."""

    return get_application_repositories().users


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """Authenticate a bearer token against authoritative stored user data."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()
    try:
        claims = decode_access_token(credentials.credentials, settings)
    except InvalidAccessTokenError as error:
        raise _authentication_error() from error

    try:
        user = await repository.get_by_id(claims["sub"])
    except RepositoryError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from error
    if user is None or claims["role"] != user.role.value:
        raise _authentication_error()
    return AuthenticatedUser(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[..., AuthenticatedUser]:
    """Create a dependency that permits only explicitly listed roles."""

    async def role_dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not role_is_allowed(current_user.role, allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to perform this action",
            )
        return current_user

    return role_dependency


get_current_customer = require_roles(UserRole.CUSTOMER)
get_current_reviewer = require_roles(UserRole.CLAIMS_OFFICER, UserRole.ADMIN)
get_current_admin = require_roles(UserRole.ADMIN)

