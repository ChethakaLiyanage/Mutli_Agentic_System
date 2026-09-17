"""Opt-in isolated Supabase verification for Step 7 grounded Agent 4 guidance."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest

from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalGuidanceClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.orchestrator.supabase_workflow_repository import SupabaseWorkflowRepository
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.service import RetrievalService
from backend.app.review.repository import SupabaseHumanReviewRepository
from backend.app.review.service import HumanReviewService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.orchestrator import OrchestratorRequest
from backend.app.schemas.review import HumanDecisionRequest
from backend.app.security.roles import UserRole
from backend.app.services.supabase_service import get_supabase_client
from backend.app.orchestrator.service import OrchestratorService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_GUIDANCE") != "1",
    reason="Set RUN_SUPABASE_GUIDANCE=1 for isolated live Step 7 verification",
)


def _check_database_readiness(client) -> None:
    """Verify all 8 canonical tables and migrations before running live tests."""
    for table in (
        "users", "workflows", "policies", "claims", "claim_documents",
        "fraud_assessments", "knowledge_chunks", "human_decisions",
    ):
        client.table(table).select("*").limit(0).execute()
    try:
        client.table("workflows").select(
            "workflow_id,claim_context,current_status"
        ).limit(0).execute()
        client.table("claims").select("claim_id,workflow_id").limit(0).execute()
    except Exception:
        pytest.skip("STEP 5 DATABASE MIGRATION REQUIRED")
    try:
        client.table("human_decisions").select(
            "decision_id,workflow_id,reviewer_role,reason"
        ).limit(0).execute()
    except Exception:
        pytest.skip("STEP 6 DATABASE MIGRATION REQUIRED")
    try:
        client.table("workflows").select(
            "workflow_id,guidance_result,current_status"
        ).limit(0).execute()
    except Exception:
        pytest.skip("STEP 7 DATABASE MIGRATION REQUIRED: guidance_result column or status missing")


def test_live_information_guidance_flow() -> None:
    """Live Supabase verification: customer -> Agent 1 -> Agent 2 -> Agent 4 -> completed."""
    client = get_supabase_client()
    _check_database_readiness(client)

    suffix = uuid4().hex[:8]
    customer_id = f"TEST-CUST-LIVE-{suffix}"
    customer_email = f"cust-live-{suffix}@example.com"
    chunk_id = f"CHK-LIVE-{suffix}"
    source_doc_id = f"DOC-LIVE-{suffix}"
    workflow_id = None

    chunk_content = (
        f"Synthetic Policy Section {suffix}: Accidental windscreen breakage "
        "is eligible for repair without affecting no-claims discount."
    )

    try:
        # Create synthetic user
        client.table("users").insert({
            "user_id": customer_id,
            "email": customer_email,
            "password_hash": "synthetic-hash",
            "role": "customer",
        }).execute()

        # Insert synthetic knowledge chunk
        client.table("knowledge_chunks").insert({
            "chunk_id": chunk_id,
            "source_document_id": source_doc_id,
            "source_title": f"Live Test Manual {suffix}",
            "insurance_type": "motor",
            "document_type": "policy_manual",
            "section": "Windscreen",
            "content": chunk_content,
            "normalized_content": preprocess_for_retrieval(chunk_content),
            "metadata": {"test_suffix": suffix},
        }).execute()

        repo = RetrievalRepository(client)
        retriever = KnowledgeRetriever(repository=repo)
        retriever.refresh()
        retrieval_service = RetrievalService(repository=repo, knowledge_retriever=retriever)
        retrieval_client = LocalRetrievalClient(retrieval_service)

        workflow_repo = SupabaseWorkflowRepository(client)
        service = OrchestratorService(
            claim_intake_client=LocalClaimIntakeClient(),
            workflow_repository=workflow_repo,
            retrieval_client=retrieval_client,
            guidance_client=LocalGuidanceClient(),
        )

        response = asyncio.run(service.process_request(
            OrchestratorRequest(
                request_id=f"REQ-LIVE-{suffix}",
                text=f"Does my policy cover windscreen breakage? {suffix}",
            ),
            authenticated_user_id=customer_id,
            authenticated_user_role="customer",
        ))

        workflow_id = response.workflow_id
        assert response.status is WorkflowStatus.COMPLETED
        assert response.guidance_result is not None
        assert response.guidance_result["data"]["grounded"] is True
        assert response.fraud_result is None

        # Verify persisted in Supabase
        stored = client.table("workflows").select("*").eq("workflow_id", workflow_id).execute()
        assert len(stored.data) == 1
        assert stored.data[0]["current_status"] == "completed"
        assert stored.data[0]["guidance_result"] is not None

    finally:
        if workflow_id:
            client.table("workflows").delete().eq("workflow_id", workflow_id).execute()
        client.table("knowledge_chunks").delete().eq("chunk_id", chunk_id).execute()
        client.table("users").delete().eq("user_id", customer_id).execute()


def test_live_post_human_decision_guidance_flow() -> None:
    """Live Supabase verification: Authoritative human decision -> customer-safe Agent 4 guidance."""
    client = get_supabase_client()
    _check_database_readiness(client)

    suffix = uuid4().hex[:8]
    customer_id = f"TEST-CUST-POST-{suffix}"
    officer_id = f"TEST-OFFICER-POST-{suffix}"
    customer_email = f"cust-post-{suffix}@example.com"
    officer_email = f"officer-post-{suffix}@example.com"
    workflow_id = f"TEST-WF-POST-{suffix}"
    policy_id = f"TEST-POL-POST-{suffix}"
    claim_id = f"TEST-CLM-POST-{suffix}"
    assessment_id = f"TEST-FRA-POST-{suffix}"

    try:
        # Create synthetic users
        for uid, email, role in [
            (customer_id, customer_email, "customer"),
            (officer_id, officer_email, "claims_officer"),
        ]:
            client.table("users").insert({
                "user_id": uid, "email": email,
                "password_hash": "synthetic-hash", "role": role,
            }).execute()

        # Policy
        client.table("policies").insert({
            "policy_id": policy_id,
            "policy_number": f"POL-LIVE-{suffix}",
            "customer_id": customer_id,
            "status": "active",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
        }).execute()

        # Workflow
        claim_ctx = {
            "claim_id": claim_id, "claim_reference": f"REF-LIVE-{suffix}",
            "customer_id": customer_id, "policy_id": policy_id,
            "policy_number": f"POL-LIVE-{suffix}", "incident_type": "vehicle_collision",
            "incident_date": "2026-09-15", "incident_location": "Colombo",
            "incident_description": "Live test collision claim.",
            "damage_areas": [], "claim_status": "awaiting_human_review",
            "document_references": [],
        }
        fraud = {
            "assessment_id": assessment_id, "claim_id": claim_id,
            "risk_score": 0.4, "risk_level": "medium", "rule_score": 0.4,
            "anomaly_score": None, "indicators": [],
            "recommended_action": "manual_review", "missing_documents": [],
            "automated_decision": False, "rules_version": "1.0.0",
            "model_version": None, "warnings": [],
        }
        client.table("workflows").insert({
            "workflow_id": workflow_id, "request_id": f"REQ-P-{suffix}",
            "last_request_id": f"REQ-P-{suffix}", "raw_text": "Live test claim",
            "original_text": "Live test claim", "accumulated_text": "Live test claim",
            "authenticated_user_id": customer_id, "authenticated_user_role": "customer",
            "claim_context": claim_ctx,
            "retrieval_result": {"status": "success", "result": {}},
            "fraud_result": fraud, "workflow_type": "claim_submission",
            "current_status": "awaiting_human_review",
        }).execute()

        # Claim & Assessment
        client.table("claims").insert({
            "claim_id": claim_id, "workflow_id": workflow_id,
            "claim_reference": f"REF-LIVE-{suffix}", "customer_id": customer_id,
            "policy_id": policy_id, "policy_number": f"POL-LIVE-{suffix}",
            "incident_type": "vehicle_collision", "incident_date": "2026-09-15",
            "claim_status": "awaiting_human_review",
        }).execute()

        client.table("fraud_assessments").insert({
            "assessment_id": assessment_id, "claim_id": claim_id,
            "risk_level": "medium", "risk_score": 0.4, "rule_score": 0.4,
            "indicators": [], "missing_documents": [],
            "recommended_action": "manual_review", "automated_decision": False,
        }).execute()

        # Submit human decision via HumanReviewService
        wf_repo = SupabaseWorkflowRepository(client)
        review_repo = SupabaseHumanReviewRepository(client, wf_repo)
        review_service = HumanReviewService(review_repo)
        reviewer_user = AuthenticatedUser(
            user_id=officer_id, email=officer_email,
            role=UserRole.CLAIMS_OFFICER, created_at=datetime.now(timezone.utc),
        )

        decision_resp = asyncio.run(review_service.submit_decision(
            workflow_id,
            HumanDecisionRequest(
                decision="approve",
                reason="All repair estimates verified by officer.",
                notes="Internal note: low-cost repair.",
            ),
            reviewer_user,
        ))
        assert decision_resp.status.value == "approved"

        # Customer retrieves workflow result
        orchestrator_service = OrchestratorService(
            workflow_repository=wf_repo,
            guidance_client=LocalGuidanceClient(),
        )
        cust_resp = asyncio.run(orchestrator_service.get_customer_workflow_result(
            workflow_id, authenticated_user_id=customer_id
        ))

        assert cust_resp.status is WorkflowStatus.APPROVED
        assert cust_resp.guidance_result is not None
        assert "approved" in cust_resp.message.lower()
        # Internal notes and fraud metrics not exposed to customer
        assert "Internal note" not in cust_resp.message
        assert cust_resp.fraud_result is None
        assert cust_resp.human_review_result is None

        # Verify persisted guidance_result in Supabase
        stored_wf = client.table("workflows").select("*").eq("workflow_id", workflow_id).execute()
        assert stored_wf.data[0]["current_status"] == "approved"
        assert stored_wf.data[0]["guidance_result"] is not None

    finally:
        client.table("human_decisions").delete().eq("workflow_id", workflow_id).execute()
        client.table("fraud_assessments").delete().eq("assessment_id", assessment_id).execute()
        client.table("claims").delete().eq("claim_id", claim_id).execute()
        client.table("workflows").delete().eq("workflow_id", workflow_id).execute()
        client.table("policies").delete().eq("policy_id", policy_id).execute()
        client.table("users").delete().eq("user_id", officer_id).execute()
        client.table("users").delete().eq("user_id", customer_id).execute()
