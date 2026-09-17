"""Tests for Agent 4 FastAPI endpoints (Section 13.2, 13.3)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.guidance_routes import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_guidance_health_endpoint():
    """Verify health check endpoint returns 200 OK."""
    response = client.get("/guidance/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "guidance-agent"


def test_guidance_generate_endpoint():
    """Verify POST /guidance/generate produces valid response envelope."""
    payload = {
        "request_id": "REQ-API-01",
        "audience": "customer",
        "task_type": "coverage_explanation",
        "retrieved_evidence": [
            {
                "document_id": "DOC-101",
                "document_name": "Motor Policy",
                "section": "Section 3 - Windscreen",
                "content": "Accidental damage to windscreen is covered.",
            }
        ],
    }

    response = client.post("/guidance/generate", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["agent"] == "guidance_agent"
    assert result["data"]["automated_decision"] is False
    assert len(result["data"]["evidence_used"]) > 0


def test_guidance_customer_endpoint():
    """Verify POST /guidance/customer endpoint."""
    payload = {
        "request_id": "REQ-API-02",
        "audience": "customer",
        "task_type": "claim_status",
        "claim_status": "under_review",
    }
    response = client.post("/guidance/customer", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert "under_review" in result["data"]["message"]


def test_guidance_reviewer_summary_endpoint():
    """Verify POST /guidance/reviewer-summary endpoint."""
    payload = {
        "request_id": "REQ-API-03",
        "audience": "reviewer",
        "task_type": "reviewer_summary",
        "claim_data": {
            "claim_id": "CLM-999",
            "incident_type": "vehicle_collision",
        },
    }
    response = client.post("/guidance/reviewer-summary", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["data"]["reviewer_summary"] is not None
