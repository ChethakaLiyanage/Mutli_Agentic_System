"""Deterministic extraction and normalization of supported date expressions."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_DATE_PATTERNS = (
    re.compile(r"\bthis\s+(?:morning|afternoon|evening)\b", re.IGNORECASE),
    re.compile(r"\bearlier\s+today\b", re.IGNORECASE),
    re.compile(r"\btwo\s+days\s+ago\b", re.IGNORECASE),
    re.compile(r"\blast\s+night\b", re.IGNORECASE),
    re.compile(r"\byesterday\b", re.IGNORECASE),
    re.compile(r"\btoday\b", re.IGNORECASE),
    re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{4}\.\d{2}\.\d{2}\b"),
    re.compile(r"\b\d{2}[.-]\d{2}[.-]\d{4}\b"),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z,]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z,]+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}\b", re.IGNORECASE)
)

def _clean_date_string(date_str: str) -> str:
    cleaned = date_str.lower()
    cleaned = re.sub(r",", " ", cleaned)
    cleaned = re.sub(r"(st|nd|rd|th)\b", "", cleaned)
    cleaned = re.sub(r"\bof\b", "", cleaned)
    cleaned = re.sub(r"\bsepte\s*ber\b", "september", cleaned)
    return " ".join(cleaned.split())

def _normalize_date(date_text: str, reference_date: date) -> str | None:
    lowered = date_text.casefold()
    if lowered in {"today", "this morning", "this afternoon", "this evening", "earlier today"}:
        return reference_date.isoformat()
    if lowered in {"yesterday", "last night"}:
        return (reference_date - timedelta(days=1)).isoformat()
    if lowered == "two days ago":
        return (reference_date - timedelta(days=2)).isoformat()

    cleaned = _clean_date_string(date_text)
    
    date_formats = [
        "%d/%m/%Y", "%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%d-%m-%Y",
        "%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y"
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def extract_date(text: str, reference_date: date | None = None) -> tuple[str | None, str | None]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    matches = [
        match for pattern in _DATE_PATTERNS
        if (match := pattern.search(text)) is not None
    ]
    if not matches:
        return None, None

    earliest_match = min(matches, key=lambda match: match.start())
    date_text = earliest_match.group(0)
    normalized_date = _normalize_date(date_text, reference_date or date.today())
    return date_text, normalized_date

class DateExtractor:
    def extract(self, text: str, reference_date: date | None = None) -> tuple[str | None, str | None]:
        return extract_date(text, reference_date)
