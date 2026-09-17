"""Opt-in, isolated Supabase verification for the Step 5 claim pipeline."""

from __future__ import annotations

import asyncio
from datetime import date
import os
from uuid import uuid4

import pytest

from backend.app.fraud.repository import FraudRepository
from backend.app.orchestrator.agent_clients import LocalFraudClient, LocalRetrievalClient
from backend.app.orchestrator.claim_repository import SupabaseClaimRepository
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.intake import IncidentInformation, IntakeData, IntakeResponse, IntentResult
from backend.app.schemas.orchestrator import OrchestratorRequest
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_ORCHESTRATOR_FRAUD") != "1",
    reason="Set RUN_SUPABASE_ORCHESTRATOR_FRAUD=1 for isolated live verification",
)


class Intake:
    async def analyze(self, request):
        return IntakeResponse(
            request_id=request.request_id, status="success",
            data=IntakeData(
                intent=IntentResult(label="claim_submission", confidence=.95),
                incident=IncidentInformation(
                    type="vehicle_collision", normalized_date=date.today().isoformat(),
                    location="Synthetic Test Location",
                ),
            ),
        )


def test_live_supabase_claim_retrieval_and_fraud_persistence() -> None:
    client = get_supabase_client()
    suffix = uuid4().hex
    user_id = f"TEST-USER-{suffix}"
    policy_id = f"TEST-POL-{suffix}"
    policy_number = f"TEST-MTR-{suffix}"
    probe_workflow_id = f"TEST-WF-{suffix}"
    claim_ids: list[str] = []
    response = None
    try:
        for table in (
            "users", "workflows", "policies", "claims", "claim_documents",
            "fraud_assessments", "knowledge_chunks", "human_decisions",
        ):
            client.table(table).select("*").limit(0).execute()
        try:
            client.table("workflows").select("workflow_id,claim_context,current_status").limit(0).execute()
            client.table("claims").select("claim_id,workflow_id").limit(0).execute()
        except Exception:
            pytest.skip("Apply step5_add_claim_fraud_workflow.sql before live Step 5 testing")

        client.table("users").insert({
            "user_id": user_id, "email": f"{suffix}@example.invalid",
            "password_hash": "synthetic-not-a-real-password", "role": "customer",
        }).execute()
        try:
            client.table("workflows").insert({
                "workflow_id": probe_workflow_id,
                "request_id": f"TEST-PROBE-{suffix}",
                "last_request_id": f"TEST-PROBE-{suffix}",
                "raw_text": "synthetic readiness probe",
                "original_text": "synthetic readiness probe",
                "accumulated_text": "synthetic readiness probe",
                "authenticated_user_id": user_id,
                "authenticated_user_role": "customer",
                "workflow_type": "claim_submission",
                "current_status": "claim_information_retrieval",
            }).execute()
            client.table("workflows").delete().eq(
                "workflow_id", probe_workflow_id
            ).execute()
        except Exception:
            pytest.skip("Apply step5_add_claim_fraud_workflow.sql before live Step 5 testing")
        client.table("policies").insert({
            "policy_id": policy_id, "policy_number": policy_number,
            "customer_id": user_id, "insurance_type": "motor", "status": "active",
            "start_date": "2026-01-01", "end_date": "2027-01-01",
        }).execute()

        retrieval = LocalRetrievalClient(RetrievalService(RetrievalRepository(client)))
        service = OrchestratorService(
            claim_intake_client=Intake(),
            workflow_repository=InMemoryWorkflowRepository(),
            retrieval_client=retrieval, fraud_client=LocalFraudClient(),
            claim_repository=SupabaseClaimRepository(client),
            fraud_repository=FraudRepository(client),
        )
        response = asyncio.run(service.process_request(
            OrchestratorRequest(
                request_id=f"TEST-REQ-{suffix}",
                text="A synthetic test collision happened today at the test location.",
            ),
            authenticated_user_id=user_id, authenticated_user_role="customer",
        ))
        if response.errors and response.errors[0].code == "CLAIM_PERSISTENCE_FAILED":
            pytest.skip("Apply step5_add_claim_fraud_workflow.sql before live Step 5 testing")
        assert response.status.value == "awaiting_human_review"
        assert response.fraud_result["automated_decision"] is False
        claim_ids.append(response.fraud_result["claim_id"])
        stored = client.table("fraud_assessments").select("*").eq(
            "claim_id", claim_ids[0]
        ).execute()
        assert len(stored.data) == 1
    finally:
        if not claim_ids:
            found = client.table("claims").select("claim_id").eq(
                "customer_id", user_id
            ).execute()
            claim_ids = [row["claim_id"] for row in (found.data or [])]
        for claim_id in claim_ids:
            client.table("fraud_assessments").delete().eq("claim_id", claim_id).execute()
            client.table("claim_documents").delete().eq("claim_id", claim_id).execute()
            client.table("claims").delete().eq("claim_id", claim_id).execute()
        client.table("workflows").delete().eq("workflow_id", probe_workflow_id).execute()
        client.table("policies").delete().eq("policy_id", policy_id).execute()
        client.table("users").delete().eq("user_id", user_id).execute()
