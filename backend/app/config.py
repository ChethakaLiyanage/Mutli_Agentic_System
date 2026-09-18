"""Environment-backed application settings."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Resolve the backend environment from the repository root instead of relying on
# the process working directory. Existing operating-system variables still win.
load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)

_DEVELOPMENT_JWT_SECRET = (
    "development-only-jwt-secret-change-before-production-32-chars"
)


@dataclass(frozen=True)
class Settings:
    """Small immutable configuration used by authentication components."""

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    persistence_backend: str = "memory"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    def __post_init__(self) -> None:
        if not self.jwt_secret:
            raise ValueError("JWT secret cannot be empty")
        if self.jwt_algorithm != "HS256":
            raise ValueError("Only HS256 is supported by this prototype")
        if self.jwt_access_token_expire_minutes <= 0:
            raise ValueError("JWT expiry must be positive")
        if self.persistence_backend not in {"memory", "supabase"}:
            raise ValueError("PERSISTENCE_BACKEND must be memory or supabase")
        if self.persistence_backend == "supabase" and not self.supabase_url:
            raise ValueError(
                "Supabase persistence selected but SUPABASE_URL is not configured"
            )
        if (
            self.persistence_backend == "supabase"
            and not self.supabase_service_role_key
        ):
            raise ValueError(
                "Supabase persistence selected but "
                "SUPABASE_SERVICE_ROLE_KEY is not configured"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings; the fallback secret is for local development only."""

    return Settings(
        jwt_secret=os.getenv("JWT_SECRET", _DEVELOPMENT_JWT_SECRET),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_access_token_expire_minutes=int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        ),
        persistence_backend=os.getenv("PERSISTENCE_BACKEND", "memory").lower(),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
