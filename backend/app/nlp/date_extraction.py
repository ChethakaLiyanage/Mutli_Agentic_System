"""Deterministic extraction and normalization of supported date expressions."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta


_DATE_PATTERNS = (
    re.compile(r"\b(?:just\s+now|right\s+now)\b", re.IGNORECASE),
    re.compile(r"\b(?:a\s+)?few\s+(?:mins?|minutes?)\s+ago\b", re.IGNORECASE),
    re.compile(r"\b(?:a\s+)?moment\s+ago\b", re.IGNORECASE),
    re.compile(r"\b(?:an?\s+)?hour\s+ago\b", re.IGNORECASE),
    re.compile(r"\bjust\s+(?:had|got\s+into)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+(?:morning|afternoon|evening)\b", re.IGNORECASE),
    re.compile(r"\bearlier\s+today\b", re.IGNORECASE),
    re.compile(r"\btwo\s+days\s+ago\b", re.IGNORECASE),
    re.compile(r"\blast\s+night\b", re.IGNORECASE),
    re.compile(r"\byesterday\b", re.IGNORECASE),
    re.compile(r"\btoday\b", re.IGNORECASE),
    re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
)


def _normalize_date(date_text: str, reference_date: date) -> str | None:
    lowered = date_text.casefold().strip()
    if (
        lowered in {
            "today",
            "this morning",
            "this afternoon",
            "this evening",
            "earlier today",
            "just now",
            "right now",
        }
        or "ago" in lowered
        or lowered.startswith("just ")
    ):
        if lowered == "two days ago":
            return (reference_date - timedelta(days=2)).isoformat()
        return reference_date.isoformat()
    if lowered in {"yesterday", "last night"}:
        return (reference_date - timedelta(days=1)).isoformat()

    date_format = "%d/%m/%Y" if "/" in date_text else "%Y-%m-%d"
    try:
        return datetime.strptime(date_text, date_format).date().isoformat()
    except ValueError:
        return None


def extract_date(
    text: str,
    reference_date: date | None = None,
) -> tuple[str | None, str | None]:
    """Return the earliest supported date wording and its ISO normalization."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    matches = [
        match
        for pattern in _DATE_PATTERNS
        if (match := pattern.search(text)) is not None
    ]
    if not matches:
        return None, None

    earliest_match = min(matches, key=lambda match: match.start())
    date_text = earliest_match.group(0)
    normalized_date = _normalize_date(date_text, reference_date or date.today())
    return date_text, normalized_date


class DateExtractor:
    """Extract supported date wording and normalize it when unambiguous."""

    def extract(
        self,
        text: str,
        reference_date: date | None = None,
    ) -> tuple[str | None, str | None]:
        return extract_date(text, reference_date)
