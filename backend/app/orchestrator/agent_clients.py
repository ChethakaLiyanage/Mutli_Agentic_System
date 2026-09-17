"""Replaceable client contracts for specialized agents."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.schemas.intake import IntakeRequest, IntakeResponse


@runtime_checkable
class ClaimIntakeClient(Protocol):
    """Async boundary used by the Orchestrator to call Agent 1."""

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        """Analyze one request without exposing Agent 1 implementation details."""

        ...


class _LocalClaimIntakeAnalyzer(Protocol):
    def analyze(self, request: IntakeRequest) -> IntakeResponse:
        ...


class LocalClaimIntakeClient:
    """Local adapter that can later be replaced by an HTTP implementation."""

    def __init__(self, agent: _LocalClaimIntakeAnalyzer | None = None) -> None:
        self._agent = agent or ClaimIntakeAgent()

    async def analyze(self, request: IntakeRequest) -> IntakeResponse:
        return await asyncio.to_thread(self._agent.analyze, request)
