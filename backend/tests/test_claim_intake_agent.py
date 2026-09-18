"""Integration tests for the Claim Intake & Query Understanding Agent."""

import logging
from datetime import date

import pytest

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.schemas.intake import IntakeRequest


@pytest.fixture(scope="module")
def agent() -> ClaimIntakeAgent:
    return ClaimIntakeAgent(reference_date_provider=lambda: date(2026, 9, 16))


def analyze(agent: ClaimIntakeAgent, text: str, request_id: str = "REQ001"):
    return agent.analyze(IntakeRequest(request_id=request_id, text=text))


def test_complete_collision_claim(agent: ClaimIntakeAgent) -> None:
    original_text = "A bus hit my car yesterday near Kandy and damaged the left door."
    request = IntakeRequest(request_id="REQ001", text=original_text)

    response = agent.analyze(request)

    assert request.text == original_text
    assert response.status == "success"
    assert response.data.intent.label == "claim_submission"
    assert 0.0 <= response.data.intent.confidence <= 1.0
    assert response.data.incident.type == "vehicle_collision"
    assert response.data.incident.date_text == "yesterday"
    assert response.data.incident.normalized_date == "2026-09-15"
    assert response.data.incident.location == "Kandy"
    assert response.data.damage.areas == ["left door"]
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False
    assert response.errors == []


@pytest.mark.parametrize(
    ("text", "expected_location"),
    [
        ("my car crashed yesterday at kandy", "Kandy"),
        ("my car crashed yesterday near Kandy", "Kandy"),
        ("my car had an accident yesterday in Colombo", "Colombo"),
        ("my car had a collision yesterday near Negombo", "Negombo"),
    ],
)
def test_claim_location_is_normalized_from_layered_extraction(
    agent: ClaimIntakeAgent,
    text: str,
    expected_location: str,
) -> None:
    response = analyze(agent, text)

    assert response.data.intent.label == "claim_submission"
    assert response.data.incident.location == expected_location
    assert "location" not in response.data.missing_fields


def test_time_is_not_selected_as_claim_location(agent: ClaimIntakeAgent) -> None:
    response = analyze(agent, "My car crashed yesterday at 5pm and I want to claim")

    assert response.data.incident.location is None
    assert "location" in response.data.missing_fields


def test_incomplete_claim_reports_only_genuinely_missing_fields(
    agent: ClaimIntakeAgent,
) -> None:
    response = analyze(agent, "My car was damaged and I want to claim.")

    assert response.data.intent.label == "claim_submission"
    assert response.data.missing_fields == [
        "incident_type",
        "incident_date",
        "location",
    ]
    assert response.data.requires_clarification is True


def test_windscreen_coverage_question_does_not_require_claim_fields(
    agent: ClaimIntakeAgent,
) -> None:
    response = analyze(agent, "Does my policy cover windscreen damage?")

    assert response.data.intent.label == "coverage_question"
    assert response.data.incident.type == "windscreen_damage"
    assert response.data.damage.areas == ["windscreen"]
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_required_documents_question(agent: ClaimIntakeAgent) -> None:
    response = analyze(agent, "What documents do I need after an accident?")

    assert response.data.intent.label == "required_documents_question"
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_claim_status_question(agent: ClaimIntakeAgent) -> None:
    response = analyze(agent, "What is happening with my claim?")

    assert response.data.intent.label == "claim_status"
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_complete_flood_claim(agent: ClaimIntakeAgent) -> None:
    response = analyze(
        agent,
        "Flood water entered my car yesterday near Galle and damaged the engine. "
        "I want to claim.",
    )

    assert response.data.intent.label == "claim_submission"
    assert response.data.incident.type == "flood_damage"
    assert response.data.incident.location == "Galle"
    assert response.data.incident.normalized_date == "2026-09-15"
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_complete_theft_or_break_in_claim(agent: ClaimIntakeAgent) -> None:
    response = analyze(
        agent,
        "Someone broke into my car yesterday near Colombo and I need to make a claim.",
    )

    assert response.data.intent.label == "claim_submission"
    assert response.data.incident.type == "theft_or_break_in"
    assert response.data.incident.location == "Colombo"
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_multiple_damage_areas_are_preserved(agent: ClaimIntakeAgent) -> None:
    response = analyze(
        agent,
        "The crash damaged my left door and rear bumper yesterday near Kandy. "
        "I want to claim.",
    )

    assert response.data.incident.type == "vehicle_collision"
    assert response.data.damage.areas == ["left door", "rear bumper"]
    assert response.data.missing_fields == []


def test_low_confidence_request_requires_clarification(
    agent: ClaimIntakeAgent,
) -> None:
    response = analyze(agent, "I need some help with this thing")

    assert response.data.intent.confidence < agent.confidence_threshold
    assert response.data.requires_clarification is True


def test_non_claim_intent_keeps_detectable_incident_details(
    agent: ClaimIntakeAgent,
) -> None:
    response = analyze(agent, "Does my policy cover flood damage?")

    assert response.data.intent.label == "coverage_question"
    assert response.data.incident.type == "flood_damage"
    assert response.data.missing_fields == []


def test_greeting_never_requests_claim_fields(agent: ClaimIntakeAgent) -> None:
    response = analyze(agent, "ih")

    assert response.data.intent.label == "greeting"
    assert response.data.missing_fields == []
    assert response.data.requires_clarification is False


def test_noisy_classification_does_not_replace_text_used_for_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = "my car ws hit ystrday in colombo"
    observed: list[str] = []

    def record_entities(text: str):
        observed.append(text)
        return []

    def record_incident(text: str):
        observed.append(text)
        return None

    def record_damage(text: str):
        observed.append(text)
        return []

    def record_date(text: str, reference_date: date):
        observed.append(text)
        return None, None

    monkeypatch.setattr(
        "backend.app.agents.claim_intake_agent.extract_entities",
        record_entities,
    )
    monkeypatch.setattr(
        "backend.app.agents.claim_intake_agent.extract_incident_type",
        record_incident,
    )
    monkeypatch.setattr(
        "backend.app.agents.claim_intake_agent.extract_damage_areas",
        record_damage,
    )
    monkeypatch.setattr(
        "backend.app.agents.claim_intake_agent.extract_date",
        record_date,
    )

    response = analyze(ClaimIntakeAgent(), original)

    assert response.data.intent.label == "claim_submission"
    assert observed == [original, original, original, original]


def test_internal_failure_returns_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_prediction(_: str) -> tuple[str, float]:
        raise RuntimeError("developer-only failure detail")

    monkeypatch.setattr(
        "backend.app.agents.claim_intake_agent.predict_intent",
        fail_prediction,
    )
    request = IntakeRequest(request_id="REQ-ERROR", text="A valid customer message")

    with caplog.at_level(logging.ERROR):
        response = ClaimIntakeAgent().analyze(request)

    assert response.status == "error"
    assert response.errors == ["Claim intake analysis failed"]
    assert "developer-only failure detail" not in response.model_dump_json()
    assert "developer-only failure detail" in caplog.text
