"""Configuration for LLM clients in the Guidance Agent."""

from __future__ import annotations

import os
from typing import Literal
from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """LLM provider and generation parameters."""

    provider: Literal["mock", "gemini", "openai"] = "mock"
    model_name: str = "gemini-1.5-flash"
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

        model_name = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash" if provider == "gemini" else "gpt-4o-mini")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))

        return cls(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
        )
