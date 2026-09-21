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
    "dmg": "damage",
    "documents": "document",
    "docs": "document",
    "doc": "document",
    "papers": "document",
    "paper": "document",
    "policies": "policy",
    "required": "require",
    "requires": "require",
    "stolen": "theft",
    "stole": "theft",
}


def tokenize_for_retrieval(text: str) -> list[str]:
    """Return normalized tokens while retaining identifiers and section numbers."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    raw_tokens: list[str] = []
    for match in _TOKEN_PATTERN.finditer(text):
        token = match.group(0).lower()
        norm = _NORMAL_FORMS.get(token, token)
        raw_tokens.append(norm)
        if "/" in token and not any(char.isdigit() for char in token):
            for part in token.split("/"):
                if part:
                    raw_tokens.append(_NORMAL_FORMS.get(part, part))
    return [token for token in raw_tokens if token not in _STOP_WORDS]


def preprocess_for_retrieval(text: str) -> str:
    """Return the stable representation stored/indexed for lexical retrieval."""
    return " ".join(tokenize_for_retrieval(text))
