"""Configuration for LLM clients in the Guidance Agent."""

from __future__ import annotations

import os
from typing import Literal
from pydantic import BaseModel, Field

from backend.app.config import ENV_FILE_PATH as _ENV_FILE_PATH


# Importing the canonical application environment path ensures the repository-
# root .env has been loaded even when Agent 4 is used outside FastAPI startup.
assert _ENV_FILE_PATH.name == ".env"


class LLMSettings(BaseModel):
    """LLM provider and generation parameters."""

    provider: Literal["mock", "gemini", "openai"] = "mock"
    model_name: str = "gemini-3.6-flash"
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_retries: int = Field(default=2, ge=0)
    timeout_seconds: float = Field(default=30.0, ge=1.0)

    @classmethod
    def from_env(cls) -> LLMSettings:
        """Create settings automatically from environment variables."""
        provider_env = os.getenv("LLM_PROVIDER")
        if provider_env in ("gemini", "openai", "mock"):
            provider = provider_env
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "mock"

        default_model = (
            "gemini-3.6-flash" if provider == "gemini" else "gpt-4o-mini"
        )
        model_name = os.getenv("LLM_MODEL_NAME", default_model)
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))

        return cls(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
        )
