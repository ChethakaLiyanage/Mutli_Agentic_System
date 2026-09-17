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


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


def get_authentication_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationService:
    return AuthenticationService(repository, settings)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
)
async def register_user(
    request: UserRegisterRequest,
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> UserPublic:
    try:
        user = await service.register(request)
    except UserAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from error
    logger.info("User registered: %s", user.user_id)
    return user


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
