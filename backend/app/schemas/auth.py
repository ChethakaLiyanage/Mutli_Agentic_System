"""Strict public authentication and user contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.app.security.roles import UserRole


class _AuthContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRegisterRequest(_AuthContract):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserLoginRequest(_AuthContract):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserPublic(_AuthContract):
    user_id: str
    email: EmailStr
    role: UserRole
    created_at: datetime


class AuthenticatedUser(UserPublic):
    """Trusted user context produced by the authentication dependency."""


class TokenResponse(_AuthContract):
    access_token: str
    token_type: str = "bearer"
