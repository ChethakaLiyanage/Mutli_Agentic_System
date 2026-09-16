"""Deterministic preprocessing for customer motor-insurance messages."""

from __future__ import annotations

import re


_UNNECESSARY_PUNCTUATION = re.compile(r"[^\w\s/:'\-.]", flags=re.UNICODE)
_UNATTACHED_USEFUL_PUNCTUATION = re.compile(
    r"(?<!\w)[/:'\-.]+|[/:'\-.]+(?!\w)",
    flags=re.UNICODE,
)
_REPEATED_WHITESPACE = re.compile(r"\s+")


def preprocess_text(text: str) -> str:
    """Return a deterministic cleaned copy for intent classification.

    The original string is never modified. Internal punctuation used by common
    dates, times, registrations, policy numbers, decimals, and names is kept;
    decorative or unattached punctuation is converted to token boundaries.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    cleaned = text.strip().lower()
    cleaned = _UNNECESSARY_PUNCTUATION.sub(" ", cleaned)
    cleaned = _UNATTACHED_USEFUL_PUNCTUATION.sub(" ", cleaned)
    return _REPEATED_WHITESPACE.sub(" ", cleaned).strip()
