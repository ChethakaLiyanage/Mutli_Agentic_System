"""Controlled rule-based vehicle damage-area extraction."""

from __future__ import annotations

import re

from backend.app.schemas.intake import DamageInformation


_DAMAGE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("front bumper", re.compile(r"\bfront\s+bumper\b", re.IGNORECASE)),
    ("rear bumper", re.compile(r"\brear\s+bumper\b", re.IGNORECASE)),
    ("left door", re.compile(r"\bleft(?:[\s-]+hand)?\s+door\b", re.IGNORECASE)),
    ("right door", re.compile(r"\bright(?:[\s-]+hand)?\s+door\b", re.IGNORECASE)),
    ("windscreen", re.compile(r"\bwindscreen\b", re.IGNORECASE)),
    ("windshield", re.compile(r"\bwindshield\b", re.IGNORECASE)),
    ("bonnet", re.compile(r"\bbonnet\b", re.IGNORECASE)),
    ("boot", re.compile(r"\bboot\b", re.IGNORECASE)),
    ("headlight", re.compile(r"\bhead[\s-]?lights?\b", re.IGNORECASE)),
    ("tail light", re.compile(r"\btail[\s-]?lights?\b", re.IGNORECASE)),
    ("mirror", re.compile(r"\b(?:side|rear[\s-]?view)?\s*mirrors?\b", re.IGNORECASE)),
    ("roof", re.compile(r"\broof\b", re.IGNORECASE)),
    ("wheel", re.compile(r"\bwheels?\b", re.IGNORECASE)),
    ("tyre", re.compile(r"\b(?:tyres?|tires?)\b", re.IGNORECASE)),
)


def extract_damage_areas(text: str) -> list[str]:
    """Return unique controlled damage areas in their source-text order."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    matches: list[tuple[int, str]] = []
    for area, pattern in _DAMAGE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            matches.append((match.start(), area))
    return [area for _, area in sorted(matches)]


class DamageExtractor:
    """Extract stated vehicle areas without inferring unseen damage."""

    def extract(self, text: str) -> DamageInformation:
        return DamageInformation(areas=extract_damage_areas(text))
