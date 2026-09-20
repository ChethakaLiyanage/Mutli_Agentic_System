"""Opt-in live Gemini integration test for Agent 4 Guidance Agent."""

from __future__ import annotations

import os
import pytest

from backend.app.guidance.schemas import GuidanceRequest
from backend.app.guidance.service import GuidanceService
from backend.app.llm.client import GeminiLLMClient, get_llm_client
from backend.app.llm.config import LLMSettings


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_GEMINI") != "1",
    reason="Set RUN_LIVE_GEMINI=1 for controlled live Gemini verification",
)


def test_live_gemini_configuration_and_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Gemini configuration loads, client is instantiated, and one request succeeds."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    settings = LLMSettings.from_env()
    assert settings.provider == "gemini", f"Expected gemini provider, got {settings.provider}"

    client = get_llm_client(settings)
    assert isinstance(client, GeminiLLMClient), f"Expected GeminiLLMClient, got {type(client).__name__}"

    service = GuidanceService(llm_client=client)
    request = GuidanceRequest(
        request_id="LIVE-GEMINI-TEST-001",
        audience="customer",
        task_type="greeting",
        safe_customer_context={"customer_message": "Hello, good afternoon!"},
    )

    response = service.process_request(request)
    assert response is not None
    assert response.data is not None
    assert isinstance(response.data.message, str)
    assert len(response.data.message.strip()) > 0
    assert response.data.automated_decision is False
