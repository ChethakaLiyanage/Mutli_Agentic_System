"""General entity extraction from original customer messages."""

from __future__ import annotations

import re
from functools import lru_cache

import spacy
from spacy.language import Language

from backend.app.schemas.intake import ExtractedEntity


_SPACY_LABEL_MAP = {
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "DATE": "DATE",
    "TIME": "TIME",
}

_FALLBACK_PATTERNS = {
    "DATE": re.compile(
        r"\b(?:today|yesterday|last\s+night|two\s+days\s+ago|"
        r"\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b",
        flags=re.IGNORECASE,
    ),
    "TIME": re.compile(r"\b\d{1,2}:\d{2}(?:\s*[ap]m)?\b", flags=re.IGNORECASE),
    "LOCATION": re.compile(
        r"\b(?:near|in|at|around|outside)\s+"
        r"(?P<location>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2})\b"
    ),
}


@lru_cache(maxsize=1)
def _load_spacy_model() -> Language:
    try:
        return spacy.load("en_core_web_sm")
    except OSError as error:
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' is not installed. "
            "Run: python -m spacy download en_core_web_sm"
        ) from error


def extract_entities(text: str) -> list[ExtractedEntity]:
    """Extract mapped entities while preserving exact source text and offsets."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        return []

    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, int, int]] = set()
    document = _load_spacy_model()(text)

    for entity in document.ents:
        entity_type = _SPACY_LABEL_MAP.get(entity.label_)
        if entity_type is None:
            continue
        key = (entity_type, entity.start_char, entity.end_char)
        seen.add(key)
        entities.append(
            ExtractedEntity(
                entity_type=entity_type,
                value=entity.text,
                start=entity.start_char,
                end=entity.end_char,
            )
        )

    # These narrow fallbacks make the prototype reliable for its documented
    # expressions while spaCy remains the primary general-purpose extractor.
    for entity_type, pattern in _FALLBACK_PATTERNS.items():
        for match in pattern.finditer(text):
            if entity_type == "LOCATION":
                start, end = match.span("location")
                value = match.group("location")
            else:
                start, end = match.span()
                value = match.group(0)
            key = (entity_type, start, end)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                ExtractedEntity(
                    entity_type=entity_type,
                    value=value,
                    start=start,
                    end=end,
                )
            )

    return sorted(entities, key=lambda entity: (entity.start or 0, entity.end or 0))


class EntityExtractor:
    """Extract location, date, and time entities from original input text."""

    def extract(self, text: str) -> list[ExtractedEntity]:
        return extract_entities(text)
