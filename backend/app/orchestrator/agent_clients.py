"""Replaceable client contracts for specialized agents."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.agents.guidance_agent import GuidanceAgent
from backend.app.fraud.engine import FraudDetectionEngine
from backend.app.orchestrator.adapters import (
    canonical_to_fraud_inputs,
    fraud_to_canonical,
)
from backend.app.schemas.domain import (
    ClaimContext,
    DocumentFact,
    FraudAssessmentContext,
    PolicyContext,
)
from backend.app.schemas.intake import IntakeRequest, IntakeResponse
from backend.app.guidance.schemas import GuidanceRequest, GuidanceResponse
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import RetrievalRequest, RetrievalResponse
from backend.app.retrieval.schemas import HistoricalClaim
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


@runtime_checkable
class FraudClient(Protocol):
    """Async replaceable boundary for Agent 3 risk triage."""

    async def assess(
        self,
        *,
        claim: ClaimContext,
        policy: PolicyContext,
        document_facts: list[DocumentFact],
        historical_claims: list[HistoricalClaim],
    ) -> FraudAssessmentContext:
        ...


class _LocalFraudEngine(Protocol):
    def evaluate(
        self,
        claim_data: dict,
        policy_data: dict,
        document_facts: list[dict],
        historical_claims: list[dict],
        duplicate_police_report_claims: list[dict],
    ): ...


class LocalFraudClient:
    """Run the production fraud engine without coupling it to orchestration."""

    def __init__(self, engine: _LocalFraudEngine | None = None) -> None:
        self._engine = engine or FraudDetectionEngine()

    async def assess(
        self,
        *,
        claim: ClaimContext,
        policy: PolicyContext,
        document_facts: list[DocumentFact],
        historical_claims: list[HistoricalClaim],
    ) -> FraudAssessmentContext:
        claim_data, policy_data = canonical_to_fraud_inputs(claim, policy)
        document_rows = [
            {
                "document_id": item.document_id,
                "document_type": item.document_type.value,
                "incident_date": item.incident_date,
                "claimed_amount": item.claim_amount,
                "incident_type": (
                    item.incident_type.value if item.incident_type else None
                ),
                "police_report_number": item.police_report_number,
                "extracted_text": item.extracted_text,
            }
            for item in document_facts
        ]
        history_rows = [
            {
                "id": item.claim_id,
                "claim_reference": item.claim_reference,
                "claim_type": item.claim_type,
                "incident_date": item.incident_date,
                "claimed_amount": item.claimed_amount,
                "status": item.status,
                "police_report_number": item.police_report_number,
            }
            for item in historical_claims
        ]
        duplicate_reports = [
            row for row in history_rows
            if claim.police_report_number
            and row.get("police_report_number") == claim.police_report_number
        ]
        assessment = await asyncio.to_thread(
            self._engine.evaluate,
            claim_data=claim_data,
            policy_data=policy_data,
            document_facts=document_rows,
            historical_claims=history_rows,
            duplicate_police_report_claims=duplicate_reports,
        )
        return fraud_to_canonical(assessment, claim_id=claim.claim_id)


@runtime_checkable
class GuidanceClient(Protocol):
    """Async replaceable boundary for Agent 4 grounded explanations."""

    async def generate(self, request: GuidanceRequest) -> GuidanceResponse:
        ...


class _LocalGuidanceAgent(Protocol):
    def process(self, request: GuidanceRequest) -> GuidanceResponse: ...


class LocalGuidanceClient:
    """Run the configured Agent 4 provider outside the event loop."""

    def __init__(self, agent: Any | None = None) -> None:
        self._agent = agent or GuidanceAgent()

    async def generate(self, request: GuidanceRequest) -> GuidanceResponse:
        handler = getattr(self._agent, "process", None) or getattr(
            self._agent, "process_request", None
        )
        if handler is None:
            raise TypeError("Guidance Agent must implement process or process_request")
        response = await asyncio.to_thread(handler, request)
        if not isinstance(response, GuidanceResponse):
            raise TypeError("Guidance Agent returned an invalid response")
        return response
