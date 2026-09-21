"""Comprehensive end-to-end test suite for the complete claim submission and review lifecycle."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import io
import pytest
from fastapi.testclient import TestClient

from backend.app.api import orchestrator as orchestrator_api
from backend.app.api import reviewer as reviewer_api
from backend.app.graph.state import WorkflowState
from backend.app.main import app
from backend.app.orchestrator.agent_clients import LocalGuidanceClient
from backend.app.orchestrator.claim_repository import (
    InMemoryClaimRepository,
    get_claim_repository,
)
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.review.repository import InMemoryHumanReviewRepository
from backend.app.review.service import HumanReviewService
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.domain import ClaimContext, IncidentType
from backend.app.security.dependencies import (
    get_current_admin,
    get_current_customer,
    get_current_reviewer,
    get_current_user,
)
from backend.app.security.roles import UserRole
from backend.app.services.document_service import (
    DocumentService,
    InMemoryDocumentRepository,
    get_document_repository,
)
from backend.app.services.notification_service import (
    InMemoryNotificationRepository,
    NotificationService,
    get_notification_repository,
)


CUSTOMER_USER = AuthenticatedUser(
    user_id="USR-CUSTOMER-1",
    email="customer@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)

OTHER_CUSTOMER_USER = AuthenticatedUser(
    user_id="USR-CUSTOMER-2",
    email="other@example.com",
    role=UserRole.CUSTOMER,
    created_at=datetime.now(timezone.utc),
)

OFFICER_USER = AuthenticatedUser(
    user_id="USR-OFFICER-1",
    email="officer@example.com",
    role=UserRole.CLAIMS_OFFICER,
    created_at=datetime.now(timezone.utc),
)

OTHER_OFFICER_USER = AuthenticatedUser(
    user_id="USR-OFFICER-2",
    email="other_officer@example.com",
    role=UserRole.CLAIMS_OFFICER,
    created_at=datetime.now(timezone.utc),
)

ADMIN_USER = AuthenticatedUser(
    user_id="USR-ADMIN-1",
    email="admin@example.com",
    role=UserRole.ADMIN,
    created_at=datetime.now(timezone.utc),
)


class DummyFraudClient:
    async def assess(self, *args, **kwargs):
        from backend.app.schemas.domain import FraudAssessmentContext, RecommendedAction, RiskLevel
        return FraudAssessmentContext(
            risk_score=0.15,
            risk_level=RiskLevel.LOW,
            indicators=[],
            recommended_action=RecommendedAction.CONTINUE_PROCESSING,
            automated_decision=False,
        )


def build_test_claim_state(
    workflow_id: str,
    claim_id: str,
    status: WorkflowStatus = WorkflowStatus.AWAITING_DOCUMENTS,
    owner_id: str = "USR-CUSTOMER-1",
) -> WorkflowState:
    claim = ClaimContext(
        claim_id=claim_id,
        claim_reference=f"REF-{claim_id}",
        customer_id=owner_id,
        policy_id="POL-123",
        policy_number="POL-12345",
        incident_type=IncidentType.VEHICLE_COLLISION,
        incident_date=date(2026, 3, 10),
        incident_location="Highway 1",
        incident_description="Front bumper damaged",
        claimed_amount=1500.0,
        claim_status="awaiting_documents",
    )
    return WorkflowState(
        workflow_id=workflow_id,
        request_id="REQ-1",
        last_request_id="REQ-1",
        raw_text="Car collided on highway",
        original_text="Car collided on highway",
        accumulated_text="Car collided on highway",
        authenticated_user_id=owner_id,
        authenticated_user_role=UserRole.CUSTOMER.value,
        workflow_type=WorkflowType.CLAIM_SUBMISSION,
        current_status=status,
        claim_context=claim,
        retrieval_result={
            "request_id": "REQ-1",
            "status": "success",
            "result": {
                "knowledge_evidence": [
                    {
                        "chunk_id": "chk-test-1",
                        "document_id": "doc-test-1",
                        "source_title": "Required Documents for Collision",
                        "section_title": "Collision Requirements",
                        "content": "For vehicle collision claims, you must submit a repair_estimate and damage_photo.",
                        "confidence_score": 0.9,
                    }
                ],
                "document_facts": [
                    {
                        "document_id": "doc-test-1",
                        "document_type": "policy_manual",
                        "source_title": "Required Documents for Collision",
                        "content": "For vehicle collision claims, you must submit a repair_estimate and damage_photo.",
                    }
                ],
                "warnings": [],
            },
            "errors": [],
        },
    )


@pytest.fixture
def lifecycle_env():
    workflows_repo = InMemoryWorkflowRepository()
    claims_repo = InMemoryClaimRepository(
        policies=[
            {"policy_id": "POL-123", "policy_number": "POL-12345", "customer_id": "USR-CUSTOMER-1", "status": "active"}
        ]
    )
    docs_repo = InMemoryDocumentRepository()
    notifs_repo = InMemoryNotificationRepository()
    human_review_repo = InMemoryHumanReviewRepository(workflows_repo)

    doc_service = DocumentService(repository=docs_repo)
    notif_service = NotificationService(repository=notifs_repo)
    review_service = HumanReviewService(
        repository=human_review_repo,
        notification_service=notif_service,
    )
    orch_service = OrchestratorService(
        workflow_repository=workflows_repo,
        claim_repository=claims_repo,
        fraud_client=DummyFraudClient(),
        guidance_client=LocalGuidanceClient(),
    )

    from backend.app.api.claims import get_workflow_repository
    from backend.app.api.notifications import get_notification_service

    app.dependency_overrides[get_document_repository] = lambda: docs_repo
    app.dependency_overrides[get_notification_repository] = lambda: notifs_repo
    app.dependency_overrides[get_notification_service] = lambda: notif_service
    app.dependency_overrides[get_claim_repository] = lambda: claims_repo
    app.dependency_overrides[get_workflow_repository] = lambda: workflows_repo
    app.dependency_overrides[orchestrator_api.get_orchestrator_service] = lambda: orch_service
    app.dependency_overrides[reviewer_api.get_review_service] = lambda: review_service

    with TestClient(app) as client:
        yield {
            "client": client,
            "workflows": workflows_repo,
            "claims": claims_repo,
            "documents": docs_repo,
            "notifications": notifs_repo,
            "human_review": human_review_repo,
            "orch_service": orch_service,
            "review_service": review_service,
        }

    app.dependency_overrides.clear()


def test_submit_claim_unauthorized(lifecycle_env):
    client = lifecycle_env["client"]
    # No auth dependency override -> 401
    response = client.post("/orchestrator/workflows/WF-TEST/submit-claim")
    assert response.status_code == 401


def test_submit_claim_forbidden_for_other_customer(lifecycle_env):
    client = lifecycle_env["client"]
    workflows = lifecycle_env["workflows"]

    state = build_test_claim_state("WF-OWNED", "CLM-100", owner_id="USR-CUSTOMER-1")
    asyncio.run(workflows.save(state))

    # Authenticate as OTHER_CUSTOMER_USER
    app.dependency_overrides[get_current_customer] = lambda: OTHER_CUSTOMER_USER
    app.dependency_overrides[get_current_user] = lambda: OTHER_CUSTOMER_USER

    response = client.post("/orchestrator/workflows/WF-OWNED/submit-claim")
    assert response.status_code == 403


def test_submit_claim_missing_required_documents(lifecycle_env):
    client = lifecycle_env["client"]
    workflows = lifecycle_env["workflows"]
    claims_repo = lifecycle_env["claims"]

    state = build_test_claim_state("WF-NEED-DOCS", "CLM-200", owner_id="USR-CUSTOMER-1")
    asyncio.run(workflows.save(state))
    claims_repo.save_for_workflow(workflow_id="WF-NEED-DOCS", claim=state.claim_context)

    app.dependency_overrides[get_current_customer] = lambda: CUSTOMER_USER
    app.dependency_overrides[get_current_user] = lambda: CUSTOMER_USER

    response = client.post("/orchestrator/workflows/WF-NEED-DOCS/submit-claim")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_documents"
    assert "missing_required_documents" in data
    assert len(data["missing_required_documents"]) > 0

    # Ensure fraud triage was NOT triggered
    saved_state = asyncio.run(workflows.get("WF-NEED-DOCS"))
    assert saved_state.fraud_result is None


def test_full_claim_submission_and_review_lifecycle(lifecycle_env):
    client = lifecycle_env["client"]
    workflows = lifecycle_env["workflows"]
    claims_repo = lifecycle_env["claims"]
    docs_repo = lifecycle_env["documents"]
    notifs_repo = lifecycle_env["notifications"]

    workflow_id = "WF-LIFECYCLE-1"
    claim_id = "CLM-LIFECYCLE-1"

    state = build_test_claim_state(workflow_id, claim_id, owner_id=CUSTOMER_USER.user_id)
    asyncio.run(workflows.save(state))
    claims_repo.save_for_workflow(workflow_id=workflow_id, claim=state.claim_context)

    # 1. Customer uploads required documents
    app.dependency_overrides[get_current_customer] = lambda: CUSTOMER_USER
    app.dependency_overrides[get_current_user] = lambda: CUSTOMER_USER

    file_content = b"%PDF-1.4 dummy pdf content for testing"
    doc_response = client.post(
        f"/orchestrator/workflows/{workflow_id}/documents",
        files={"file": ("estimate.pdf", io.BytesIO(file_content), "application/pdf")},
        data={"document_type": "repair_estimate"},
    )
    assert doc_response.status_code == 201

    photo_content = b"\xff\xd8\xff\xe0 dummy jpeg content"
    photo_response = client.post(
        f"/orchestrator/workflows/{workflow_id}/documents",
        files={"file": ("damage.jpg", io.BytesIO(photo_content), "image/jpeg")},
        data={"document_type": "damage_photo"},
    )
    assert photo_response.status_code == 201

    # 2. Customer presses Submit Claim
    submit_response = client.post(f"/orchestrator/workflows/{workflow_id}/submit-claim")
    assert submit_response.status_code == 200
    sub_data = submit_response.json()

    # Status must be awaiting_assignment
    assert sub_data["status"] == "awaiting_assignment"

    # CRITICAL PRIVACY: response must never contain fraud score, risk level, or internal staff summary
    assert "fraud_result" not in sub_data
    assert "reviewer_guidance_result" not in sub_data
    assert "risk_score" not in sub_data

    # Verify backend state has fraud assessment persisted with automated_decision = False
    saved_state = asyncio.run(workflows.get(workflow_id))
    assert saved_state.fraud_result is not None
    assert saved_state.fraud_result["automated_decision"] is False
    assert saved_state.reviewer_guidance_result is not None

    # 3. Admin views common review queue
    app.dependency_overrides[get_current_reviewer] = lambda: ADMIN_USER
    app.dependency_overrides[get_current_admin] = lambda: ADMIN_USER
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    queue_res = client.get("/review/queue")
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["items"]
    matching = [i for i in queue_items if i["workflow_id"] == workflow_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "awaiting_assignment"
    assert matching[0]["assigned_to"] is None

    # 4. Admin assigns claim to Claims Officer 1
    assign_res = client.post(
        f"/review/workflows/{workflow_id}/assign",
        json={"assigned_to": OFFICER_USER.user_id},
    )
    assert assign_res.status_code == 200
    assign_data = assign_res.json()
    assert assign_data["assigned_to"] == OFFICER_USER.user_id
    assert assign_data["status"] == "under_human_review"

    # Verify state updated to under_human_review
    saved_state = asyncio.run(workflows.get(workflow_id))
    assert saved_state.current_status == WorkflowStatus.UNDER_HUMAN_REVIEW

    # 5. Assigned claims officer views review detail
    app.dependency_overrides[get_current_reviewer] = lambda: OFFICER_USER
    app.dependency_overrides[get_current_user] = lambda: OFFICER_USER

    detail_res = client.get(f"/review/workflows/{workflow_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["status"] == "under_human_review"
    assert detail_data["assigned_to"] == OFFICER_USER.user_id
    assert len(detail_data["documents"]) == 2
    assert detail_data["fraud_assessment"]["risk_level"] == "low"
    assert detail_data["reviewer_guidance_result"] is not None

    # 6. Different officer cannot submit decision for this assigned claim
    app.dependency_overrides[get_current_reviewer] = lambda: OTHER_OFFICER_USER
    app.dependency_overrides[get_current_user] = lambda: OTHER_OFFICER_USER

    conflict_res = client.post(
        f"/review/workflows/{workflow_id}/decision",
        json={"decision": "approve", "reason": "Approved by other officer"},
    )
    assert conflict_res.status_code == 409

    # 7. Reject strictly requires a non-empty reason
    app.dependency_overrides[get_current_reviewer] = lambda: OFFICER_USER
    app.dependency_overrides[get_current_user] = lambda: OFFICER_USER

    empty_reason_res = client.post(
        f"/review/workflows/{workflow_id}/decision",
        json={"decision": "reject", "reason": "   "},
    )
    assert empty_reason_res.status_code in (409, 422)

    # 8. Assigned officer submits valid authoritative rejection
    rejection_reason = "Damage pattern is inconsistent with collision description."
    decision_res = client.post(
        f"/review/workflows/{workflow_id}/decision",
        json={"decision": "reject", "reason": rejection_reason, "notes": "Investigated by Officer 1"},
    )
    assert decision_res.status_code == 200
    dec_data = decision_res.json()
    decision_val = dec_data["decision"]["decision"] if isinstance(dec_data["decision"], dict) else dec_data["decision"]
    assert decision_val == "reject"
    assert dec_data["status"] == "rejected"

    # 9. Verification: Customer notification is created
    app.dependency_overrides[get_current_user] = lambda: CUSTOMER_USER
    notif_res = client.get("/notifications")
    assert notif_res.status_code == 200
    notif_data = notif_res.json()
    assert notif_data["unread_count"] >= 1
    assert any(n["claim_id"] == claim_id and "rejected" in n["title"].lower() for n in notif_data["notifications"])

    # Customer marks notification read
    notif_id = notif_data["notifications"][0]["id"]
    mark_read_res = client.patch(f"/notifications/{notif_id}/read")
    assert mark_read_res.status_code == 200
    assert mark_read_res.json()["is_read"] is True

    # 10. Customer checks claim detail
    claim_detail_res = client.get(f"/claims/{claim_id}")
    assert claim_detail_res.status_code == 200
    cd = claim_detail_res.json()
    assert cd["claim_id"] == claim_id
    assert cd["decision"] == "reject"
    assert cd["rejection_reason"] == rejection_reason
    assert len(cd["documents"]) == 2

    # CRITICAL: Confirm that customer claim detail never exposes fraud or internal summary
    assert "risk_score" not in cd
    assert "risk_level" not in cd
    assert "fraud_assessment" not in cd
    assert "reviewer_guidance_result" not in cd

    # 11. Customer checks list of my claims
    my_claims_res = client.get("/claims/my-claims")
    assert my_claims_res.status_code == 200
    assert my_claims_res.json()["total"] >= 1
