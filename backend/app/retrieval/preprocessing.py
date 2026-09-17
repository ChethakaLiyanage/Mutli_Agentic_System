"""Deterministic preprocessing for classical information retrieval."""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*", re.IGNORECASE)
_DOMAIN_TERMS = {
    "claim", "claims", "cover", "covered", "coverage", "damage",
    "document", "documents", "exclusion", "exclusions", "insurance",
    "motor", "policy", "policies", "report", "required", "vehicle",
}
_STOP_WORDS = frozenset(ENGLISH_STOP_WORDS) - _DOMAIN_TERMS
_NORMAL_FORMS = {
    "claims": "claim",
    "covered": "cover",
    "covers": "cover",
    "damages": "damage",
    "documents": "document",
    "policies": "policy",
    "required": "require",
    "requires": "require",
    "stolen": "theft",
}


def tokenize_for_retrieval(text: str) -> list[str]:
    """Return normalized tokens while retaining identifiers and section numbers."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    tokens = [
        _NORMAL_FORMS.get(match.group(0).lower(), match.group(0).lower())
        for match in _TOKEN_PATTERN.finditer(text)
    ]
    return [token for token in tokens if token not in _STOP_WORDS]


def preprocess_for_retrieval(text: str) -> str:
    """Return the stable representation stored/indexed for lexical retrieval."""
    return " ".join(tokenize_for_retrieval(text))
