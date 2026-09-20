"""Authoritative claims-officer review application service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    AuditEventStatus,
    WorkflowStatus,
)
from backend.app.review.repository import (
    HumanReviewRepository,
    ReviewDecisionConflictError,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.domain import (
    FraudAssessmentContext,
    HumanDecision,
    HumanDecisionContext,
    PolicyContext,
)
from backend.app.schemas.orchestrator import AuditEvent
from backend.app.schemas.review import (
    HumanDecisionRequest,
    HumanDecisionResponse,
    ReviewDetailResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)


class ReviewWorkflowNotFoundError(LookupError):
    pass


class ReviewWorkflowConflictError(ValueError):
    pass


DECISION_STATUS = {
    HumanDecision.APPROVE: WorkflowStatus.APPROVED,
    HumanDecision.REJECT: WorkflowStatus.REJECTED,
    HumanDecision.REQUEST_MORE_INFORMATION: WorkflowStatus.MORE_INFORMATION_REQUIRED,
    HumanDecision.ESCALATE: WorkflowStatus.ESCALATED,
}
CLAIM_STATUS = {
    HumanDecision.APPROVE: "approved",
    HumanDecision.REJECT: "rejected",
    HumanDecision.REQUEST_MORE_INFORMATION: "information_required",
    HumanDecision.ESCALATE: "escalated",
}


class HumanReviewService:
    def __init__(self, repository: HumanReviewRepository) -> None:
        self.repository = repository

    async def list_queue(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        risk_level: str | None = None,
        incident_type: str | None = None,
    ) -> ReviewQueueResponse:
        # Fetch enough rows to apply simple safe filters before pagination.
        states = await self.repository.list_pending(limit=1000, offset=0)
        items = [self._queue_item(state) for state in states]
        if risk_level:
            items = [item for item in items if item.risk_level == risk_level]
        if incident_type:
            items = [item for item in items if item.incident_type == incident_type]
        page = items[offset:offset + limit]
        return ReviewQueueResponse(
            items=page, limit=limit, offset=offset, returned=len(page)
        )

    async def get_detail(self, workflow_id: str) -> ReviewDetailResponse:
        state = await self.repository.get_workflow(workflow_id)
        if state is None:
            raise ReviewWorkflowNotFoundError("Workflow not found")
        return await self._detail(state)

    async def submit_decision(
        self,
        workflow_id: str,
        request: HumanDecisionRequest,
        reviewer: AuthenticatedUser,
    ) -> HumanDecisionResponse:
        state = await self.repository.get_workflow(workflow_id)
        if state is None:
            raise ReviewWorkflowNotFoundError("Workflow not found")
        existing = await self.repository.get_decision(workflow_id)
        if existing is not None:
            raise ReviewWorkflowConflictError("A human decision already exists")
        if state.current_status is not WorkflowStatus.AWAITING_HUMAN_REVIEW:
            raise ReviewWorkflowConflictError("Workflow is not awaiting human review")
        if state.claim_context is None or not state.claim_context.claim_id:
            raise ReviewWorkflowConflictError("Workflow has no persisted claim")
        if state.fraud_result is None:
            raise ReviewWorkflowConflictError("Workflow has no risk assessment")

        target = DECISION_STATUS[request.decision]
        if target not in ALLOWED_STATUS_TRANSITIONS[state.current_status]:
            raise ReviewWorkflowConflictError("Invalid human-review transition")
        now = datetime.now(timezone.utc)
        decision = HumanDecisionContext(
            decision_id=f"DEC-{uuid5(NAMESPACE_URL, workflow_id).hex.upper()}",
            workflow_id=workflow_id,
            claim_id=state.claim_context.claim_id,
            decision=request.decision,
            reviewer_id=reviewer.user_id,
            reviewer_role=reviewer.role.value,
            reason=request.reason,
            notes=request.notes,
            decided_at=now,
            requested_information=(
                [request.reason]
                if request.decision is HumanDecision.REQUEST_MORE_INFORMATION
                else []
            ),
        )
        reason_summary = request.reason[:160]
        state.audit_trail.append(AuditEvent(
            step="human_review", status=AuditEventStatus.STARTED,
            message=(
                f"Human review opened by {reviewer.user_id} "
                f"({reviewer.role.value})"
            ),
            timestamp=now,
        ))
        state.audit_trail.append(AuditEvent(
            step="human_review", status=AuditEventStatus.SUCCESS,
            message=(
                f"Human decision submitted by {reviewer.user_id} "
                f"({reviewer.role.value}): {request.decision.value}; "
                f"reason: {reason_summary}"
            ),
            timestamp=now,
        ))
        state.current_status = target
        state.claim_context = state.claim_context.model_copy(
            update={"claim_status": CLAIM_STATUS[request.decision]}
        )
        state.human_review_result = decision.model_dump(mode="json")
        state.updated_at = now
        state.audit_trail.append(AuditEvent(
            step="human_review", status=AuditEventStatus.SUCCESS,
            message={
                HumanDecision.APPROVE: "Claim approved by human reviewer",
                HumanDecision.REJECT: "Claim rejected by human reviewer",
                HumanDecision.REQUEST_MORE_INFORMATION: "More information requested by human reviewer",
                HumanDecision.ESCALATE: "Claim escalated by human reviewer",
            }[request.decision],
            timestamp=now,
        ))
        try:
            await self.repository.commit_decision(
                state=state,
                decision=decision,
                claim_status=CLAIM_STATUS[request.decision],
            )
        except ReviewDecisionConflictError as error:
            raise ReviewWorkflowConflictError(str(error)) from error
        return HumanDecisionResponse(
            workflow_id=workflow_id,
            claim_id=decision.claim_id,
            status=target,
            decision=decision,
            message=self._decision_message(target),
        )

    async def _detail(self, state: WorkflowState) -> ReviewDetailResponse:
        if state.claim_context is None or state.fraud_result is None:
            raise ReviewWorkflowConflictError("Workflow is not reviewable")
        result = (state.retrieval_result or {}).get("result") or {}
        policy_data = result.get("policy_data")
        policy = PolicyContext.model_validate(policy_data) if policy_data else None
        fraud = FraudAssessmentContext.model_validate(state.fraud_result)
        decision = await self.repository.get_decision(state.workflow_id)
        retrieval_context = {
            "claim_record": result.get("claim_record"),
            "historical_claim_count": len(result.get("historical_claims") or []),
            "document_facts": result.get("document_facts") or [],
            "missing_evidence": result.get("missing_evidence") or [],
        }
        return ReviewDetailResponse(
            workflow_id=state.workflow_id,
            status=state.current_status,
            claim=state.claim_context,
            policy=policy,
            retrieval_context=retrieval_context,
            fraud_assessment=fraud,
            reviewer_guidance_result=state.reviewer_guidance_result,
            audit_timeline=list(state.audit_trail),
            human_decision=decision,
        )

    @staticmethod
    def _queue_item(state: WorkflowState) -> ReviewQueueItem:
        if state.claim_context is None:
            raise ReviewWorkflowConflictError("Pending workflow has no claim")
        fraud = FraudAssessmentContext.model_validate(state.fraud_result or {})
        claim = state.claim_context
        assert claim.claim_id is not None
        return ReviewQueueItem(
            workflow_id=state.workflow_id,
            claim_id=claim.claim_id,
            created_at=state.created_at,
            updated_at=state.updated_at,
            claim_status=claim.claim_status,
            incident_type=claim.incident_type.value if claim.incident_type else None,
            incident_date=claim.incident_date,
            location=claim.incident_location,
            risk_level=fraud.risk_level.value,
            risk_score=fraud.risk_score,
            recommended_action=fraud.recommended_action.value,
            risk_indicator_count=len(fraud.indicators),
            missing_documents=[item.value for item in fraud.missing_documents],
            reviewer_summary=(
                (state.reviewer_guidance_result or {}).get("data", {}).get(
                    "reviewer_summary"
                )
            ),
        )

    @staticmethod
    def _decision_message(status: WorkflowStatus) -> str:
        return {
            WorkflowStatus.APPROVED: "The claim was approved by a human claims officer.",
            WorkflowStatus.REJECTED: "The human claims review has been completed.",
            WorkflowStatus.MORE_INFORMATION_REQUIRED: "Additional information was requested by a human claims officer.",
            WorkflowStatus.ESCALATED: "The claim was escalated for specialist human review.",
        }[status]
