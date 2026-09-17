"""Opt-in isolated Supabase verification for authoritative human review."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest

from backend.app.orchestrator.supabase_workflow_repository import SupabaseWorkflowRepository
from backend.app.review.repository import ReviewRepositoryError, SupabaseHumanReviewRepository
from backend.app.review.service import HumanReviewService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.review import HumanDecisionRequest
from backend.app.security.roles import UserRole
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_HUMAN_REVIEW") != "1",
    reason="Set RUN_SUPABASE_HUMAN_REVIEW=1 for isolated live verification",
)


def test_live_human_review_decision_transaction() -> None:
    client = get_supabase_client()
    suffix = uuid4().hex
    customer_id = f"TEST-CUSTOMER-{suffix}"
    officer_id = f"TEST-OFFICER-{suffix}"
    customer_email = f"customer-{suffix}@example.com"
    officer_email = f"officer-{suffix}@example.com"
    workflow_id = f"TEST-WF-{suffix}"
    policy_id = f"TEST-POL-{suffix}"
    claim_id = f"TEST-CLM-{suffix}"
    assessment_id = f"TEST-FRA-{suffix}"
    decision_id = None
    try:
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

        for user_id, email, role in (
            (customer_id, customer_email, "customer"),
            (officer_id, officer_email, "claims_officer"),
        ):
            client.table("users").insert({
                "user_id": user_id, "email": email,
                "password_hash": "synthetic-not-a-password", "role": role,
            }).execute()
        client.table("policies").insert({
            "policy_id": policy_id, "policy_number": f"MTR-{suffix}",
            "customer_id": customer_id, "status": "active",
            "start_date": "2026-01-01", "end_date": "2027-01-01",
        }).execute()
        claim_context = {
            "claim_id": claim_id, "claim_reference": f"REF-{suffix}",
            "customer_id": customer_id, "policy_id": policy_id,
            "policy_number": f"MTR-{suffix}", "incident_type": "vehicle_collision",
            "incident_date": "2026-09-16", "incident_location": "Synthetic Location",
            "incident_description": "Synthetic isolated review test.",
            "damage_areas": [], "claim_status": "awaiting_human_review",
            "document_references": [],
        }
        fraud = {
            "assessment_id": assessment_id, "claim_id": claim_id,
            "risk_score": .5, "risk_level": "medium", "rule_score": .5,
            "anomaly_score": None, "indicators": [],
            "recommended_action": "manual_review", "missing_documents": [],
            "automated_decision": False, "rules_version": "1.0.0",
            "model_version": None, "warnings": [],
        }
        client.table("workflows").insert({
            "workflow_id": workflow_id, "request_id": f"REQ-{suffix}",
            "last_request_id": f"REQ-{suffix}", "raw_text": "synthetic claim",
            "original_text": "synthetic claim", "accumulated_text": "synthetic claim",
            "authenticated_user_id": customer_id, "authenticated_user_role": "customer",
            "claim_context": claim_context, "retrieval_result": {"status": "success", "result": {}},
            "fraud_result": fraud, "workflow_type": "claim_submission",
            "current_status": "awaiting_human_review",
        }).execute()
        client.table("claims").insert({
            "claim_id": claim_id, "workflow_id": workflow_id,
            "claim_reference": f"REF-{suffix}", "customer_id": customer_id,
            "policy_id": policy_id, "policy_number": f"MTR-{suffix}",
            "incident_type": "vehicle_collision", "incident_date": "2026-09-16",
            "claim_status": "awaiting_human_review",
        }).execute()
        client.table("fraud_assessments").insert({
            "assessment_id": assessment_id, "claim_id": claim_id,
            "risk_level": "medium", "risk_score": .5, "rule_score": .5,
            "indicators": [], "missing_documents": [],
            "recommended_action": "manual_review", "automated_decision": False,
        }).execute()

        repository = SupabaseHumanReviewRepository(
            client, SupabaseWorkflowRepository(client)
        )
        service = HumanReviewService(repository)
        reviewer = AuthenticatedUser(
            user_id=officer_id, email=officer_email,
            role=UserRole.CLAIMS_OFFICER, created_at=datetime.now(timezone.utc),
        )
        try:
            response = asyncio.run(service.submit_decision(
                workflow_id,
                HumanDecisionRequest(decision="approve", reason="Synthetic evidence verified."),
                reviewer,
            ))
        except ReviewRepositoryError:
            pytest.skip("STEP 6 DATABASE MIGRATION REQUIRED")
        decision_id = response.decision.decision_id
        assert response.status.value == "approved"
        stored = client.table("human_decisions").select("*").eq(
            "workflow_id", workflow_id
        ).execute()
        assert len(stored.data) == 1
        assert stored.data[0]["reviewer_id"] == officer_id
        assert stored.data[0]["reason"] == "Synthetic evidence verified."
        workflow = client.table("workflows").select("current_status").eq(
            "workflow_id", workflow_id
        ).execute()
        assert workflow.data[0]["current_status"] == "approved"
    finally:
        client.table("human_decisions").delete().eq("workflow_id", workflow_id).execute()
        client.table("fraud_assessments").delete().eq("assessment_id", assessment_id).execute()
        client.table("claim_documents").delete().eq("claim_id", claim_id).execute()
        client.table("claims").delete().eq("claim_id", claim_id).execute()
        client.table("workflows").delete().eq("workflow_id", workflow_id).execute()
        client.table("policies").delete().eq("policy_id", policy_id).execute()
        client.table("users").delete().eq("user_id", officer_id).execute()
        client.table("users").delete().eq("user_id", customer_id).execute()
