"""Extraction helpers for canonical claim identifiers."""

from __future__ import annotations

import re


# Persisted claims use ``CLM-`` followed by an uppercase UUID hex value. Tests
# and imported records may use multiple uppercase alphanumeric segments, so the
# parser accepts that same namespace without encoding any individual ID.
CLAIM_ID_PATTERN = re.compile(
    r"(?<![A-Z0-9])CLM-[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Z0-9-])",
    re.IGNORECASE,
)


def extract_claim_id(text: str) -> str | None:
    """Return one explicitly supplied claim ID in canonical uppercase form."""

    match = CLAIM_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None

