"""Environment-backed application settings."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()

_DEVELOPMENT_JWT_SECRET = (
    "development-only-jwt-secret-change-before-production-32-chars"
)


@dataclass(frozen=True)
class Settings:
    """Small immutable configuration used by authentication components."""

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    def __post_init__(self) -> None:
        if not self.jwt_secret:
            raise ValueError("JWT secret cannot be empty")
        if self.jwt_algorithm != "HS256":
            raise ValueError("Only HS256 is supported by this prototype")
        if self.jwt_access_token_expire_minutes <= 0:
            raise ValueError("JWT expiry must be positive")


def get_settings() -> Settings:
    """Load settings; the fallback secret is for local development only."""

    return Settings(
        jwt_secret=os.getenv("JWT_SECRET", _DEVELOPMENT_JWT_SECRET),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_access_token_expire_minutes=int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        ),
    )
