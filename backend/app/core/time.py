"""Centralized time and timezone utilities."""

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.config import get_settings


def get_current_time(timezone_name: str | None = None) -> datetime:
    """Return the current time in the configured application timezone."""
    tz = timezone_name or get_settings().app_timezone
    return datetime.now(ZoneInfo(tz))


def get_time_aware_greeting(
    user_text: str | None = None,
    timezone_name: str | None = None,
) -> str:
    """Return a natural greeting aligned to the configured timezone."""
    now = get_current_time(timezone_name)
    hour = now.hour
    if 5 <= hour < 12:
        salutation = "Good morning"
    elif 12 <= hour < 17:
        salutation = "Good afternoon"
    elif 17 <= hour < 21:
        salutation = "Good evening"
    else:
        salutation = "Hello"

    if user_text and user_text.strip() and user_text.strip().lower().startswith("hi"):
        return "Hi there"
    return salutation
