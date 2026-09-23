"""Registration, login, and current-profile HTTP endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.config import Settings, get_settings
from backend.app.schemas.auth import (
    AuthenticatedUser,
    TokenResponse,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
)
from backend.app.security.auth_service import (
    AuthenticationService,
    InvalidCredentialsError,
)
from backend.app.security.dependencies import (
    get_current_user,
    get_user_repository,
)
from backend.app.security.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
)
from backend.app.services.repository_errors import RepositoryError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


def get_authentication_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationService:
    return AuthenticationService(repository, settings)


@router.post(
    "/register",
    status_code=status.HTTP_403_FORBIDDEN,
    summary="Register a customer account (Disabled)",
)
async def register_user() -> None:
    """Public customer registration is disabled. Accounts must be created by an administrator."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public customer registration is disabled. Accounts must be created by an administrator.",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Create an access token",
)
async def login_user(
    request: UserLoginRequest,
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> TokenResponse:
    try:
        token = await service.login(request)
    except InvalidCredentialsError as error:
        logger.info("Authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except RepositoryError as error:
        logger.exception("Login persistence failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistence service failed",
        ) from error
    logger.info("Login succeeded")
    return token


@router.get(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user profile",
)
async def get_authenticated_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> UserPublic:
    return UserPublic.model_validate(current_user.model_dump())
