"""Tests for deterministic claim-detail extraction components."""

from datetime import date

import pytest

from backend.app.nlp.damage_extraction import DamageExtractor, extract_damage_areas
from backend.app.nlp.date_extraction import DateExtractor, extract_date
from backend.app.nlp.entity_extraction import EntityExtractor, extract_entities
from backend.app.nlp.incident_extraction import IncidentExtractor, extract_incident_type


def test_extracts_details_from_collision_message() -> None:
    text = "A bus hit my car yesterday near Kandy and damaged the left door."

    incident = IncidentExtractor().extract(text)
    damage = DamageExtractor().extract(text)
    entities = EntityExtractor().extract(text)
    date_text, normalized_date = DateExtractor().extract(
        text,
        reference_date=date(2026, 9, 16),
    )

    assert incident.type == "vehicle_collision"
    assert damage.areas == ["left door"]
    assert date_text == "yesterday"
    assert normalized_date == "2026-09-15"
    assert any(
        entity.entity_type == "LOCATION" and entity.value == "Kandy"
        for entity in entities
    )
    assert any(
        entity.entity_type == "DATE" and entity.value == "yesterday"
        for entity in entities
    )


@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        ("A stone cracked my windscreen.", "windscreen_damage"),
        ("My car was submerged during the storm.", "flood_damage"),
        ("My vehicle was stolen last night.", "theft_or_break_in"),
        ("Someone broke into my parked car.", "theft_or_break_in"),
        ("Another driver rear-ended my car.", "vehicle_collision"),
    ],
)
def test_extracts_supported_incident_types(text: str, expected_type: str) -> None:
    assert extract_incident_type(text) == expected_type


def test_returns_none_when_incident_evidence_is_missing() -> None:
    assert extract_incident_type("I have a question about my policy.") is None
    assert IncidentExtractor().extract("My car is blue.").type is None


def test_extracts_multiple_damage_areas_in_text_order() -> None:
    text = "The crash damaged my left door and rear bumper plus one headlight."

    assert extract_damage_areas(text) == ["left door", "rear bumper", "headlight"]


def test_normalizes_damage_area_variants() -> None:
    assert extract_damage_areas("Both tires and the side mirrors were damaged.") == [
        "tyre",
        "mirror",
    ]


@pytest.mark.parametrize(
    ("date_text", "expected_date"),
    [
        ("today", "2026-09-16"),
        ("yesterday", "2026-09-15"),
        ("last night", "2026-09-15"),
        ("two days ago", "2026-09-14"),
    ],
)
def test_normalizes_relative_dates(date_text: str, expected_date: str) -> None:
    assert extract_date(
        f"The incident happened {date_text}.",
        reference_date=date(2026, 9, 16),
    ) == (date_text, expected_date)


@pytest.mark.parametrize(
    ("text", "date_text", "expected_date"),
    [
        ("Accident on 16/09/2026.", "16/09/2026", "2026-09-16"),
        ("Accident on 2026-09-16.", "2026-09-16", "2026-09-16"),
        ("Accident on 31/02/2026.", "31/02/2026", None),
    ],
)
def test_handles_explicit_dates(
    text: str,
    date_text: str,
    expected_date: str | None,
) -> None:
    assert extract_date(text) == (date_text, expected_date)


def test_missing_claim_details_return_empty_values() -> None:
    text = "Please help with my motor insurance question."

    assert extract_incident_type(text) is None
    assert extract_damage_areas(text) == []
    assert extract_date(text) == (None, None)


def test_entity_extractor_uses_original_text_offsets() -> None:
    text = "The accident happened at 10:30 near Colombo."

    entities = EntityExtractor().extract(text)
    time_entity = next(entity for entity in entities if entity.entity_type == "TIME")
    location_entity = next(
        entity for entity in entities if entity.entity_type == "LOCATION"
    )

    assert text[time_entity.start : time_entity.end] == time_entity.value
    assert text[location_entity.start : location_entity.end] == "Colombo"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my car crashed yesterday at Kandy", "Kandy"),
        ("my car crashed near Kandy", "Kandy"),
        ("accident in Colombo", "Colombo"),
        ("collision near Negombo", "Negombo"),
        ("my car crashed near at kandy", "kandy"),
        ("my car crashed at near kandy", "kandy"),
        ("the crash happened kandy", "kandy"),
        ("crashed yesterday kandy", "kandy"),
        ("the collision was close to Matara", "Matara"),
    ],
)
def test_layered_location_extraction_handles_customer_phrasing(
    text: str,
    expected: str,
) -> None:
    locations = [
        entity.value
        for entity in extract_entities(text)
        if entity.entity_type == "LOCATION"
    ]

    assert expected in locations


def test_time_after_at_is_not_treated_as_a_location() -> None:
    entities = extract_entities("The accident happened at 5pm.")

    assert not any(entity.entity_type == "LOCATION" for entity in entities)
    assert any(
        entity.entity_type == "TIME" and entity.value == "5pm"
        for entity in entities
    )
