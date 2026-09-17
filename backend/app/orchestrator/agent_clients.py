"""Replaceable client contracts for specialized agents."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.schemas.intake import IntakeRequest, IntakeResponse
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import RetrievalRequest, RetrievalResponse
from backend.app.retrieval.service import RetrievalService
from backend.app.services.supabase_service import get_supabase_client


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


@runtime_checkable
class RetrievalClient(Protocol):
    """Async replaceable boundary for Agent 2; not wired into orchestration yet."""

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        ...


class _LocalRetrievalService(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        ...


class LocalRetrievalClient:
    def __init__(self, service: _LocalRetrievalService | None = None) -> None:
        if service is None:
            client = get_supabase_client()
            repository = RetrievalRepository(client)
            service = RetrievalService(
                repository=repository,
                knowledge_retriever=KnowledgeRetriever(repository=repository),
            )
        self._service = service

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        return await asyncio.to_thread(self._service.retrieve, request)
