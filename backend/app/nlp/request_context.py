"""Deterministic semantic features used after intent classification."""

from __future__ import annotations

import re

from backend.app.policy_types import extract_requested_policy_type


_FIRST_PERSON_POLICY = re.compile(
    r"\b(?:my|mine|our)\s+(?:motor\s+)?(?:policy|insurance|cover|coverage)\b"
    r"|\b(?:am|are)\s+i\s+covered\b"
    r"|\bdo\s+i\s+have\s+(?:cover|coverage|insurance)\b"
    r"|\b(?:cover|coverage|insurance)\s+do\s+i\s+have\b"
    r"|\bcovered\s+under\s+my\b",
    re.IGNORECASE,
)

_COVERAGE_WORDS = re.compile(r"\b(?:cover|covered|coverage)\b", re.IGNORECASE)
_COVERAGE_SUBJECT_WORDS = {
    "accident",
    "collision",
    "damage",
    "fire",
    "flood",
    "glass",
    "liability",
    "storm",
    "theft",
    "vandalism",
    "windscreen",
}


def is_personal_policy_query(text: str) -> bool:
    """Return whether wording refers to the authenticated user's policy."""

    return bool(_FIRST_PERSON_POLICY.search(" ".join(text.split())))


def coverage_search_query(text: str) -> str:
    """Build a retrieval-oriented query without embedding coverage answers."""

    normalized = " ".join(text.casefold().split())
    tokens = set(re.findall(r"[a-z]{3,}", normalized))
    subjects = sorted(tokens.intersection(_COVERAGE_SUBJECT_WORDS))
    if subjects:
        return " ".join(subjects + ["coverage", "covered", "exclusions", "benefits"])
    if _COVERAGE_WORDS.search(normalized):
        return "policy coverage covered risks benefits coverage summary exclusions"
    return text
