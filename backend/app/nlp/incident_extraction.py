"""Deterministic motor-incident type extraction."""

from __future__ import annotations

import re

from backend.app.schemas.intake import IncidentInformation, IncidentType


_INCIDENT_PATTERNS: tuple[tuple[IncidentType, re.Pattern[str]], ...] = (
    (
        "theft_or_break_in",
        re.compile(
            r"\b(?:stolen|theft|burglar(?:y|ized)?|broken\s+into|"
            r"break[\s-]?in|broke\s+into)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "flood_damage",
        re.compile(
            r"\b(?:flood(?:ed|ing)?|submerged|water\s+damage|"
            r"water\s+(?:entered|got\s+into)|underwater)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "windscreen_damage",
        re.compile(
            r"\b(?:windscreen|windshield|cracked\s+(?:front\s+)?glass)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "vehicle_collision",
        re.compile(
            r"\b(?:collision|collided|crash(?:ed)?|rear[\s-]?ended|"
            r"hit\s+(?:my|our|the|a)\s+(?:car|vehicle|van|motorcycle)|"
            r"(?:was|got)\s+hit|hit\s+by|"
            r"sideswiped)\b",
            flags=re.IGNORECASE,
        ),
    ),
)


def extract_incident_type(text: str) -> IncidentType | None:
    """Return the first supported type with explicit evidence in the text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    matches: list[tuple[int, IncidentType]] = []
    for incident_type, pattern in _INCIDENT_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            matches.append((match.start(), incident_type))
    return min(matches, default=(0, None), key=lambda item: item[0])[1]


class IncidentExtractor:
    """Extract only a supported incident type from explicit wording."""

    def extract(self, text: str) -> IncidentInformation:
        return IncidentInformation(type=extract_incident_type(text))
