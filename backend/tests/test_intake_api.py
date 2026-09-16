"""API tests for the Claim Intake Agent service."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.api import intake as intake_api
from backend.app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "claim-intake-agent",
    }


def test_complete_claim_request() -> None:
    response = client.post(
        "/intake/analyze",
        json={
            "request_id": "REQ001",
            "text": "A bus hit my car yesterday near Kandy and damaged the left door.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "REQ001"
    assert body["agent"] == "claim_intake"
    assert body["status"] == "success"
    assert body["data"]["intent"]["label"] == "claim_submission"
    assert 0.0 <= body["data"]["intent"]["confidence"] <= 1.0
    assert body["data"]["insurance_type"] == "motor"
    assert body["data"]["incident"] == {
        "type": "vehicle_collision",
        "date_text": "yesterday",
        "normalized_date": (date.today() - timedelta(days=1)).isoformat(),
        "location": "Kandy",
    }
    assert body["data"]["damage"]["areas"] == ["left door"]
    assert body["data"]["missing_fields"] == []
    assert body["data"]["requires_clarification"] is False
    assert body["errors"] == []


def test_non_claim_request() -> None:
    response = client.post(
        "/intake/analyze",
        json={
            "request_id": "REQ002",
            "text": "Does my policy cover flood damage?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["intent"]["label"] == "coverage_question"
    assert body["data"]["incident"]["type"] == "flood_damage"
    assert body["data"]["missing_fields"] == []


def test_response_has_stable_top_level_structure() -> None:
    response = client.post(
        "/intake/analyze",
        json={
            "request_id": "REQ003",
            "text": "How does motor insurance work?",
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "request_id",
        "agent",
        "status",
        "data",
        "errors",
    }


def test_rejects_empty_request_id() -> None:
    response = client.post(
        "/intake/analyze",
        json={"request_id": "   ", "text": "A valid customer message"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_rejects_text_shorter_than_schema_minimum() -> None:
    response = client.post(
        "/intake/analyze",
        json={"request_id": "REQ004", "text": "x"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_rejects_oversized_text() -> None:
    response = client.post(
        "/intake/analyze",
        json={"request_id": "REQ005", "text": "x" * 3001},
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_unexpected_internal_failure_returns_generic_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_analysis(_request):
        raise RuntimeError("sensitive internal failure")

    monkeypatch.setattr(intake_api._claim_intake_agent, "analyze", fail_analysis)

    response = client.post(
        "/intake/analyze",
        json={"request_id": "REQ006", "text": "A valid customer message"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Claim intake service failed"}
    assert "sensitive internal failure" not in response.text
