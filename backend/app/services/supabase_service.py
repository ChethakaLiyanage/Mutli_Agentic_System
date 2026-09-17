"""Shared construction of the server-side Supabase client."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from ..config import Settings, get_settings


@lru_cache(maxsize=1)
def _create_cached_client(url: str, service_role_key: str) -> Client:
    return create_client(url, service_role_key)


def get_supabase_client(settings: Settings | None = None) -> Client:
    """Return one cached client without logging server-side credentials."""

    resolved = settings or get_settings()
    if not resolved.supabase_url:
        raise ValueError("SUPABASE_URL is not configured")
    if not resolved.supabase_service_role_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is not configured")
    return _create_cached_client(
        resolved.supabase_url,
        resolved.supabase_service_role_key,
    )
