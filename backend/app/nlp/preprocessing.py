"""Deterministic preprocessing for customer motor-insurance messages."""

from __future__ import annotations

import re


_UNNECESSARY_PUNCTUATION = re.compile(r"[^\w\s/:'\-.]", flags=re.UNICODE)
_UNATTACHED_USEFUL_PUNCTUATION = re.compile(
    r"(?<!\w)[/:'\-.]+|[/:'\-.]+(?!\w)",
    flags=re.UNICODE,
)
_REPEATED_WHITESPACE = re.compile(r"\s+")
_ALPHABETIC_TOKEN = re.compile(r"^[^\W\d_]+$", flags=re.UNICODE)
_EXCESSIVE_REPEATED_CHARACTER = re.compile(r"(.)\1{2,}", flags=re.UNICODE)


def _normalize_excessive_repetition(text: str) -> str:
    """Reduce decorative character runs in alphabetic words only.

    Three or more identical characters are reduced to two. Keeping a pair
    avoids guessing the intended spelling (for example, ``cool`` remains
    ``cool``), while making inputs such as ``pleeeease`` less sparse. Tokens
    containing digits or identifier punctuation are deliberately untouched.
    """

    tokens = text.split()
    return " ".join(
        _EXCESSIVE_REPEATED_CHARACTER.sub(r"\1\1", token)
        if _ALPHABETIC_TOKEN.fullmatch(token)
        else token
        for token in tokens
    )


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
    cleaned = _REPEATED_WHITESPACE.sub(" ", cleaned).strip()
    return _normalize_excessive_repetition(cleaned)
