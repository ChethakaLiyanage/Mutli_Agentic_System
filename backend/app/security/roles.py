"""Controlled application roles and reusable role checks."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class UserRole(str, Enum):
    CUSTOMER = "customer"
    CLAIMS_OFFICER = "claims_officer"
    ADMIN = "admin"


def role_is_allowed(role: UserRole, allowed_roles: Iterable[UserRole]) -> bool:
    """Return whether a controlled role belongs to the allowed set."""

    return role in frozenset(allowed_roles)
