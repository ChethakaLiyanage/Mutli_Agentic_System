"""Centralized time and timezone utilities."""

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.config import get_settings


def get_current_time(timezone_name: str | None = None) -> datetime:
    """Return the current time in the configured application timezone."""
    tz = timezone_name or get_settings().app_timezone
    return datetime.now(ZoneInfo(tz))
