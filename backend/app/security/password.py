"""Argon2 password hashing and verification helpers."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a validated plaintext password with Argon2id."""

    if len(password) < 8:
        raise ValueError("password must contain at least 8 characters")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Safely verify plaintext against an Argon2 password hash."""

    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
