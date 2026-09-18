"""Deterministic handling for messages that contain only a greeting."""

from __future__ import annotations

import re


GREETING_RESPONSE_MESSAGE = (
    "Hi! How can I help with your motor insurance today? You can ask about "
    "your policy, coverage, required documents, claim status, or submit a new claim."
)

_PURE_GREETINGS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "hello there",
        "good morning",
        "good afternoon",
        "good evening",
    }
)


def _edit_distance(left: str, right: str) -> int:
    """Return deterministic Levenshtein distance for two short greeting words."""

    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def _is_minor_greeting_typo(normalized: str, greeting: str) -> bool:
    """Match small omissions/transpositions only across a complete greeting."""

    words = normalized.split()
    greeting_words = greeting.split()
    if len(words) != len(greeting_words):
        return False

    total_distance = 0
    for word, expected in zip(words, greeting_words, strict=True):
        if word == expected:
            continue
        # Short forms such as ``hi`` and ``hey`` are too ambiguous for fuzzy
        # matching. Longer greeting words tolerate one edit only.
        if len(expected) < 4:
            return False
        distance = _edit_distance(word, expected)
        if distance > 2:
            return False
        total_distance += distance
    return 0 < total_distance <= 2


def is_pure_greeting(text: str) -> bool:
    """Return true only when the complete normalized message is a greeting."""

    if not isinstance(text, str):
        return False
    normalized = re.sub(r"[^\w\s]", " ", text.casefold())
    normalized = " ".join(normalized.split())
    return normalized in _PURE_GREETINGS or any(
        _is_minor_greeting_typo(normalized, greeting)
        for greeting in _PURE_GREETINGS
    )
