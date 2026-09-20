"""Create an administrator account in the configured persistent backend."""

from __future__ import annotations

import argparse
import asyncio
import getpass

from backend.app.config import get_settings
from backend.app.security.password import hash_password
from backend.app.security.roles import UserRole
from backend.app.security.user_repository import UserAlreadyExistsError
from backend.app.services.persistence import get_application_repositories


async def create_admin(email: str, password: str) -> None:
    settings = get_settings()
    if settings.persistence_backend != "supabase":
        raise RuntimeError(
            "Creating an admin requires PERSISTENCE_BACKEND=supabase. "
            "The in-memory backend loses users when the server stops."
        )

    repository = get_application_repositories().users
    try:
        user = await repository.create_user(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
    except UserAlreadyExistsError as error:
        raise RuntimeError("An account with this email already exists") from error

    print(f"Created admin account: {user.email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin account")
    parser.add_argument("email", help="Admin email address")
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ")
    if len(password) < 8:
        parser.error("Admin password must be at least 8 characters")
    asyncio.run(create_admin(args.email, password))


if __name__ == "__main__":
    main()
