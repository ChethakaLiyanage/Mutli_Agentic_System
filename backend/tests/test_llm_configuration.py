from __future__ import annotations

import json

import httpx
import pytest

from backend.app.llm.client import (
    BaseLLMClient,
    GeminiLLMClient,
    LLMClientError,
    get_llm_client,
)
from backend.app.llm.config import LLMSettings


class StubFallback(BaseLLMClient):
    def generate_json(self, system_instruction: str, user_prompt: str):
        return {
            "message": "Grounded fallback response",
            "next_steps": [],
            "evidence_used": [],
            "requires_human_review": False,
            "insufficient_evidence": False,
            "automated_decision": False,
        }


class FakeHttpClient:
    response: httpx.Response
    last_url: str | None = None
    last_headers: dict[str, str] | None = None

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict):
        del json
        type(self).last_url = url
        type(self).last_headers = headers
        return type(self).response


def _response(status_code: int, payload: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    return httpx.Response(status_code, request=request, json=payload or {})


def _client(monkeypatch: pytest.MonkeyPatch) -> GeminiLLMClient:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setattr("backend.app.llm.client.httpx.Client", FakeHttpClient)
    settings = LLMSettings(provider="gemini", model_name="gemini-3.6-flash")
    return GeminiLLMClient(
        settings,
        grounded_fallback=StubFallback(settings=settings),
    )


def test_gemini_configuration_uses_stable_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "configured")

    settings = LLMSettings.from_env()

    assert settings.model_name == "gemini-3.6-flash"
    assert isinstance(get_llm_client(settings), GeminiLLMClient)


def test_gemini_key_is_sent_in_header_not_url(monkeypatch: pytest.MonkeyPatch):
    client = _client(monkeypatch)
    raw = {
        "message": "Grounded answer",
        "next_steps": [],
        "evidence_used": [],
        "requires_human_review": False,
        "insufficient_evidence": False,
        "automated_decision": False,
    }
    FakeHttpClient.response = _response(
        200,
        {"candidates": [{"content": {"parts": [{"text": json.dumps(raw)}]}}]},
    )

    result = client.generate_json("system", "user")

    assert result == raw
    assert "test-secret-key" not in (FakeHttpClient.last_url or "")
    assert FakeHttpClient.last_headers["x-goog-api-key"] == "test-secret-key"


@pytest.mark.parametrize("status_code", [429, 503])
def test_transient_gemini_status_uses_grounded_fallback(
    monkeypatch: pytest.MonkeyPatch, status_code: int
):
    client = _client(monkeypatch)
    FakeHttpClient.response = _response(status_code)

    result = client.generate_json("system", "user")

    assert result["message"] == "Grounded fallback response"
    assert result["automated_decision"] is False


def test_non_transient_gemini_error_is_controlled_and_hides_key(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(monkeypatch)
    FakeHttpClient.response = _response(400)

    with pytest.raises(LLMClientError) as caught:
        client.generate_json("system", "user")

    assert "test-secret-key" not in str(caught.value)
    assert "HTTP 400" in str(caught.value)
