"""General entity extraction from original customer messages."""

from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

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
}

_GAZETTEER_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "sri_lanka_locations.csv"
)


def _location_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z]+", value.casefold()))


@lru_cache(maxsize=1)
def _load_location_gazetteer() -> dict[str, str]:
    """Load canonical names and aliases from the controlled project data file."""

    aliases: dict[str, str] = {}
    with _GAZETTEER_PATH.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            canonical = (row.get("name") or "").strip()
            if not canonical:
                continue
            values = [canonical, *((row.get("aliases") or "").split("|"))]
            for value in values:
                key = _location_key(value)
                if key:
                    aliases[key] = canonical
    return aliases


_LOCATION_CANONICAL = _load_location_gazetteer()
_LOCATION_LEXICON_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(
        re.escape(location).replace(r"\ ", r"[\s-]+")
        for location in sorted(_LOCATION_CANONICAL, key=len, reverse=True)
    )
    + r")\b",
    flags=re.IGNORECASE,
)
_LOCATION_PREPOSITION_PATTERN = re.compile(
    r"\b(?:close\s+to|outside|around|near|in|at)\s+"
    r"(?:(?:at|near|in)\s+)?"
    r"(?P<location>[A-Za-z][A-Za-z'’-]*"
    r"(?:\s+[A-Za-z][A-Za-z'’-]*){0,2})",
    flags=re.IGNORECASE,
)
_LOCATION_BOUNDARY_WORDS = {
    "and",
    "but",
    "when",
    "where",
    "while",
    "which",
    "with",
    "yesterday",
    "today",
}
_NON_LOCATION_WORDS = {
    "accident",
    "car",
    "claim",
    "collision",
    "damage",
    "home",
    "insurance",
    "night",
    "policy",
    "road",
    "time",
    "vehicle",
}
_TIME_LIKE_PATTERN = re.compile(
    r"^(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight)$",
    flags=re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_spacy_model() -> Language:
    try:
        return spacy.load("en_core_web_sm")
    except OSError as error:
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' is not installed. "
            "Run: python -m spacy download en_core_web_sm"
        ) from error


def normalize_location(value: str) -> str | None:
    """Return a safe display value while retaining raw text in the entity."""

    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n,.;:!?()[]{}")
    if not cleaned:
        return None
    return _match_gazetteer(cleaned) or cleaned


def _edit_distance(left: str, right: str) -> int:
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


def _match_gazetteer(value: str, *, fuzzy: bool = True) -> str | None:
    key = _location_key(value)
    exact = _LOCATION_CANONICAL.get(key)
    if exact or not fuzzy or len(key.replace(" ", "")) < 6:
        return exact

    ranked: list[tuple[float, int, str]] = []
    for alias, canonical in _LOCATION_CANONICAL.items():
        if abs(len(alias) - len(key)) > 2:
            continue
        distance = _edit_distance(key, alias)
        ratio = SequenceMatcher(None, key, alias).ratio()
        if distance <= 2 and ratio >= 0.82:
            ranked.append((ratio, -distance, canonical))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    if len(ranked) > 1 and ranked[0][:2] == ranked[1][:2] and ranked[0][2] != ranked[1][2]:
        return None
    return ranked[0][2]


def _preposition_location(match: re.Match[str]) -> tuple[str, int, int] | None:
    """Validate a narrow phrase following a location preposition."""

    raw = match.group("location")
    base_start = match.start("location")
    accepted: list[re.Match[str]] = []
    for token in re.finditer(r"[A-Za-z][A-Za-z'’-]*", raw):
        if accepted and token.group(0).casefold() in _LOCATION_BOUNDARY_WORDS:
            break
        accepted.append(token)

    if not accepted:
        return None
    candidate = raw[accepted[0].start() : accepted[-1].end()]
    normalized = normalize_location(candidate)
    if normalized is None or _TIME_LIKE_PATTERN.fullmatch(normalized):
        return None

    words = normalized.casefold().split()
    known_location = _match_gazetteer(candidate) is not None
    source_looks_proper = all(word[:1].isupper() for word in candidate.split())
    if (
        not known_location
        and (
            not source_looks_proper
            or any(word in _NON_LOCATION_WORDS for word in words)
        )
    ):
        return None

    start = base_start + accepted[0].start()
    end = base_start + accepted[-1].end()
    return candidate, start, end


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

    # Narrow date/time fallbacks follow spaCy, which remains the primary
    # general-purpose entity extractor.
    for entity_type, pattern in _FALLBACK_PATTERNS.items():
        for match in pattern.finditer(text):
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

    # A controlled Sri Lankan lexicon catches common places when statistical
    # NER misses lowercase or informal customer text. Entity values remain the
    # exact source slice; ClaimIntakeAgent normalizes the selected display value.
    for match in _LOCATION_LEXICON_PATTERN.finditer(text):
        start, end = match.span()
        key = ("LOCATION", start, end)
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            ExtractedEntity(
                entity_type="LOCATION",
                value=match.group(0),
                start=start,
                end=end,
            )
        )

    # Conservative fuzzy lookup handles minor customer spelling mistakes for
    # gazetteer places. It accepts only a unique close match within two edits.
    word_matches = list(re.finditer(r"[A-Za-z][A-Za-z'-]*", text))
    for width in (3, 2, 1):
        for index in range(0, len(word_matches) - width + 1):
            selected = word_matches[index : index + width]
            start, end = selected[0].start(), selected[-1].end()
            candidate = text[start:end]
            key = _location_key(candidate)
            if key in _LOCATION_CANONICAL:
                continue
            canonical = _match_gazetteer(candidate)
            entity_key = ("LOCATION", start, end)
            if canonical is None or entity_key in seen:
                continue
            seen.add(entity_key)
            entities.append(
                ExtractedEntity(
                    entity_type="LOCATION",
                    value=candidate,
                    start=start,
                    end=end,
                )
            )

    # Finally, accept lexically safe proper-name phrases after common location
    # prepositions. This deliberately rejects time-like and generic phrases.
    for match in _LOCATION_PREPOSITION_PATTERN.finditer(text):
        extracted = _preposition_location(match)
        if extracted is None:
            continue
        value, start, end = extracted
        key = ("LOCATION", start, end)
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            ExtractedEntity(
                entity_type="LOCATION",
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
