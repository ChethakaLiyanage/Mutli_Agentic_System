from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.review.repository import InMemoryHumanReviewRepository
from backend.app.review.service import HumanReviewService, ReviewWorkflowConflictError
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.domain import ClaimContext, HumanDecision
from backend.app.schemas.review import HumanDecisionRequest
from backend.app.security.roles import UserRole


OFFICER = AuthenticatedUser(
    user_id="OFFICER-1", email="officer@example.com",
    role=UserRole.CLAIMS_OFFICER, created_at=datetime.now(timezone.utc),
)
ADMIN = AuthenticatedUser(
    user_id="ADMIN-1", email="admin@example.com",
    role=UserRole.ADMIN, created_at=datetime.now(timezone.utc),
)


def review_state(
    workflow_id: str,
    *,
    status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
    risk="medium",
    created_at=None,
) -> WorkflowState:
    created_at = created_at or datetime.now(timezone.utc)
    score = {"low": .1, "medium": .5, "high": .8}[risk]
    return WorkflowState(
        workflow_id=workflow_id, request_id=f"REQ-{workflow_id}",
        last_request_id=f"REQ-{workflow_id}", raw_text="Customer claim text",
        original_text="Customer claim text", accumulated_text="Customer claim text",
        authenticated_user_id=f"CUSTOMER-{workflow_id}",
        authenticated_user_role="customer", workflow_type=WorkflowType.CLAIM_SUBMISSION,
        current_status=status,
        claim_context=ClaimContext(
            claim_id=f"CLM-{workflow_id}", claim_reference=f"REF-{workflow_id}",
            customer_id=f"CUSTOMER-{workflow_id}", policy_id=f"POL-{workflow_id}",
            incident_type="vehicle_collision", incident_date="2026-09-16",
            incident_location="Colombo", claim_status="awaiting_human_review",
        ),
        retrieval_result={
            "status": "success",
            "result": {
                "policy_data": {
                    "policy_id": f"POL-{workflow_id}", "policy_number": "MTR-1",
                    "customer_id": f"CUSTOMER-{workflow_id}", "status": "active",
                    "start_date": "2026-01-01", "end_date": "2027-01-01",
                    "coverage_details": {},
                },
                "claim_record": None, "historical_claims": [],
                "document_facts": [], "missing_evidence": [],
            },
        },
        fraud_result={
            "assessment_id": f"FRA-{workflow_id}", "claim_id": f"CLM-{workflow_id}",
            "risk_score": score, "risk_level": risk, "rule_score": score,
            "anomaly_score": None,
            "indicators": [{
                "rule_id": "REVIEW_SIGNAL", "severity": risk, "weight": 20,
                "title": "Review signal", "explanation": "Requires human review.",
                "evidence": {"source": "rule"},
            }],
            "recommended_action": "manual_review" if risk != "high" else "escalate",
            "missing_documents": ["police_report"], "automated_decision": False,
            "rules_version": "1.0.0", "model_version": None, "warnings": [],
        },
        created_at=created_at, updated_at=created_at,
    )


async def setup(*states):
    workflows = InMemoryWorkflowRepository()
    for state in states:
        await workflows.save(state)
    repository = InMemoryHumanReviewRepository(workflows)
    return workflows, repository, HumanReviewService(repository)


def test_queue_only_includes_pending_oldest_first_with_pagination_and_filter() -> None:
    now = datetime.now(timezone.utc)
    _, _, service = asyncio.run(setup(
        review_state("NEW", risk="low", created_at=now),
        review_state("OLD", risk="high", created_at=now - timedelta(days=1)),
        review_state("DONE", status=WorkflowStatus.APPROVED, created_at=now - timedelta(days=2)),
    ))
    first = asyncio.run(service.list_queue(limit=1, offset=0))
    assert [item.workflow_id for item in first.items] == ["OLD"]
    second = asyncio.run(service.list_queue(limit=1, offset=1))
    assert [item.workflow_id for item in second.items] == ["NEW"]
    filtered = asyncio.run(service.list_queue(limit=20, offset=0, risk_level="low"))
    assert [item.workflow_id for item in filtered.items] == ["NEW"]


def test_review_detail_contains_grounded_claim_fraud_and_no_credentials() -> None:
    _, _, service = asyncio.run(setup(review_state("DETAIL", risk="high")))
    detail = asyncio.run(service.get_detail("DETAIL"))
    assert detail.claim.claim_id == "CLM-DETAIL"
    assert detail.policy.policy_id == "POL-DETAIL"
    assert detail.fraud_assessment.risk_level.value == "high"
    assert detail.fraud_assessment.indicators[0].rule_id == "REVIEW_SIGNAL"
    assert detail.fraud_assessment.automated_decision is False
    serialized = detail.model_dump_json().lower()
    assert "password_hash" not in serialized
    assert "service_role" not in serialized


@pytest.mark.parametrize(
    ("decision", "expected_status", "claim_status"),
    [
        (HumanDecision.APPROVE, WorkflowStatus.APPROVED, "approved"),
        (HumanDecision.REJECT, WorkflowStatus.REJECTED, "rejected"),
        (HumanDecision.REQUEST_MORE_INFORMATION, WorkflowStatus.MORE_INFORMATION_REQUIRED, "information_required"),
        (HumanDecision.ESCALATE, WorkflowStatus.ESCALATED, "escalated"),
    ],
)
def test_authoritative_decisions_transition_and_are_attributable(
    decision, expected_status, claim_status
) -> None:
    workflows, repository, service = asyncio.run(setup(review_state("DECIDE")))
    response = asyncio.run(service.submit_decision(
        "DECIDE", HumanDecisionRequest(decision=decision, reason="Reviewed supporting evidence."),
        OFFICER,
    ))
    assert response.status is expected_status
    assert response.decision.reviewer_id == OFFICER.user_id
    assert response.decision.reviewer_role == "claims_officer"
    assert response.decision.reason == "Reviewed supporting evidence."
    assert repository.claim_statuses["CLM-DECIDE"] == claim_status
    saved = asyncio.run(workflows.get("DECIDE"))
    assert saved.current_status is expected_status
    assert saved.claim_context.claim_status == claim_status
    assert saved.fraud_result["automated_decision"] is False
    assert any(OFFICER.user_id in item.message for item in saved.audit_trail)


@pytest.mark.parametrize(
    ("risk", "decision"),
    [("high", HumanDecision.APPROVE), ("low", HumanDecision.REJECT)],
)
def test_human_may_disagree_with_agent_three(risk, decision) -> None:
    _, _, service = asyncio.run(setup(review_state("DISAGREE", risk=risk)))
    response = asyncio.run(service.submit_decision(
        "DISAGREE", HumanDecisionRequest(
            decision=decision, reason="Human review reached a different conclusion."
        ), ADMIN,
    ))
    assert response.decision.decision is decision
    assert response.decision.reviewer_role == "admin"


def test_second_contradictory_decision_is_rejected() -> None:
    _, repository, service = asyncio.run(setup(review_state("ONCE")))
    asyncio.run(service.submit_decision(
        "ONCE", HumanDecisionRequest(decision="approve", reason="Evidence verified."), OFFICER
    ))
    with pytest.raises(ReviewWorkflowConflictError):
        asyncio.run(service.submit_decision(
            "ONCE", HumanDecisionRequest(decision="reject", reason="Different decision."), ADMIN
        ))
    assert len(repository.decisions) == 1


def test_concurrent_reviewers_cannot_create_two_decisions() -> None:
    _, repository, service = asyncio.run(setup(review_state("RACE")))

    async def race():
        return await asyncio.gather(
            service.submit_decision(
                "RACE", HumanDecisionRequest(decision="approve", reason="Officer review."), OFFICER
            ),
            service.submit_decision(
                "RACE", HumanDecisionRequest(decision="reject", reason="Admin review."), ADMIN
            ),
            return_exceptions=True,
        )

    results = asyncio.run(race())
    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert len(repository.decisions) == 1


def test_reason_is_required_by_schema() -> None:
    with pytest.raises(ValueError):
        HumanDecisionRequest(decision="reject", reason=" ")
