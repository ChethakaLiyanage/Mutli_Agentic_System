"""Canonical motor-policy category normalization and query extraction."""

from __future__ import annotations

import re
from typing import Literal, TypeAlias


PolicyType: TypeAlias = Literal[
    "full_comprehensive",
    "partial_comprehensive",
    "third_party",
]

CANONICAL_POLICY_TYPES = frozenset(
    {"full_comprehensive", "partial_comprehensive", "third_party"}
)

_ALIASES: dict[str, PolicyType] = {
    "full": "full_comprehensive",
    "comprehensive": "full_comprehensive",
    "full_comprehensive": "full_comprehensive",
    "partial": "partial_comprehensive",
    "partial_comprehensive": "partial_comprehensive",
    "third_party": "third_party",
    "thirdparty": "third_party",
}

_EXPLICIT_POLICY_PATTERNS: tuple[tuple[re.Pattern[str], PolicyType], ...] = (
    (
        re.compile(r"\b(?:full[\s_-]+comprehensive|full[\s_-]+policy)\b", re.I),
        "full_comprehensive",
    ),
    (
        re.compile(
            r"\b(?:partial[\s_-]+comprehensive|partial[\s_-]+policy|"
            r"partial[\s_-]+insurance)\b",
            re.I,
        ),
        "partial_comprehensive",
    ),
    (
        re.compile(r"\bthird[\s_-]*party(?:[\s_-]+policy|[\s_-]+insurance)?\b", re.I),
        "third_party",
    ),
)


def normalize_policy_type(value: object, *, strict: bool = False) -> PolicyType | None:
    """Normalize boundary values while keeping one internal representation."""

    if value is None:
        return None
    normalized = re.sub(r"[\s-]+", "_", str(value).strip().casefold())
    normalized = re.sub(r"_+", "_", normalized)
    result = _ALIASES.get(normalized)
    if result is None and strict:
        raise ValueError(f"Unsupported policy type: {value}")
    return result


def extract_requested_policy_type(text: str) -> PolicyType | None:
    """Extract a category explicitly named in a query, independent of ownership."""

    normalized = " ".join(text.split())
    for pattern, policy_type in _EXPLICIT_POLICY_PATTERNS:
        if pattern.search(normalized):
            return policy_type
    return None
