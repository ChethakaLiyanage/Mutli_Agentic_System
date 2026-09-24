"""Authoritative claims-officer review application service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

logger = logging.getLogger(__name__)

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
    ClaimAssignmentRequest,
    ClaimAssignmentResponse,
    HumanDecisionRequest,
    HumanDecisionResponse,
    ReviewDetailResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from backend.app.services.document_service import get_document_repository
from backend.app.services.notification_service import NotificationService


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
    def __init__(
        self,
        repository: HumanReviewRepository,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.repository = repository
        self.notification_service = notification_service or NotificationService()

    async def list_queue(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        risk_level: str | None = None,
        incident_type: str | None = None,
    ) -> ReviewQueueResponse:
        # Fetch pending workflows
        states = await self.repository.list_pending(limit=1000, offset=0)
        items: list[ReviewQueueItem] = []
        for state in states:
            try:
                assignment = await self.repository.get_assignment(state.workflow_id)
                items.append(self._queue_item(state, assignment))
            except Exception as err:
                logger.warning("Skipping queue item for workflow %s: %s", getattr(state, "workflow_id", "unknown"), err)
                continue

        if risk_level:
            items = [item for item in items if item.risk_level == risk_level]
        if incident_type:
            items = [item for item in items if item.incident_type == incident_type]
        page = items[offset : offset + limit]
        return ReviewQueueResponse(
            items=page, limit=limit, offset=offset, returned=len(page)
        )

    async def get_detail(self, workflow_id: str) -> ReviewDetailResponse:
        state = await self.repository.get_workflow(workflow_id)
        if state is None:
            raise ReviewWorkflowNotFoundError("Workflow not found")
        return await self._detail(state)

    async def assign_claim(
        self,
        workflow_id: str,
        request: ClaimAssignmentRequest,
        assigned_by: AuthenticatedUser,
    ) -> ClaimAssignmentResponse:
        state = await self.repository.get_workflow(workflow_id)
        if state is None:
            raise ReviewWorkflowNotFoundError("Workflow not found")
        if state.claim_context is None or not state.claim_context.claim_id:
            raise ReviewWorkflowConflictError("Workflow has no persisted claim")
        if state.current_status not in {
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
        }:
            raise ReviewWorkflowConflictError("Workflow is not in an assignable status")

        assignment = await self.repository.assign_claim(
            claim_id=state.claim_context.claim_id,
            workflow_id=workflow_id,
            assigned_to=request.assigned_to,
            assigned_by=assigned_by.user_id,
        )

        now = datetime.now(timezone.utc)
        state.current_status = WorkflowStatus.UNDER_HUMAN_REVIEW
        state.updated_at = now
        state.audit_trail.append(
            AuditEvent(
                step="assignment",
                status=AuditEventStatus.SUCCESS,
                message=f"Claim assigned to officer {request.assigned_to} by {assigned_by.user_id}",
                timestamp=now,
            )
        )
        await self.repository.workflows.save(state)

        return ClaimAssignmentResponse(
            assignment_id=assignment["assignment_id"],
            workflow_id=workflow_id,
            claim_id=state.claim_context.claim_id,
            assigned_to=request.assigned_to,
            assigned_by=assigned_by.user_id,
            assigned_at=now,
            status=state.current_status,
            message=f"Claim assigned to {request.assigned_to}",
        )

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
        if state.current_status not in {
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_ASSIGNMENT,
        }:
            raise ReviewWorkflowConflictError("Workflow is not awaiting human review")
        if state.claim_context is None or not state.claim_context.claim_id:
            raise ReviewWorkflowConflictError("Workflow has no persisted claim")
        if state.fraud_result is None:
            raise ReviewWorkflowConflictError("Workflow has no risk assessment")

        # Officer assignment check: If role is claims_officer, cannot act on claims assigned to another officer
        if reviewer.role.value == "claims_officer":
            assignment = await self.repository.get_assignment(workflow_id)
            if assignment and assignment.get("assigned_to") and assignment.get("assigned_to") != reviewer.user_id:
                raise ReviewWorkflowConflictError(
                    f"This claim is assigned to officer {assignment.get('assigned_to')}"
                )

        # Invariant: reject requires a non-empty reason
        if request.decision is HumanDecision.REJECT and not request.reason.strip():
            raise ReviewWorkflowConflictError("A non-empty reason is required to reject a claim")

        target = DECISION_STATUS[request.decision]
        allowed = ALLOWED_STATUS_TRANSITIONS.get(state.current_status, frozenset())
        if target not in allowed and target not in {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
        }:
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
        state.audit_trail.append(
            AuditEvent(
                step="human_review",
                status=AuditEventStatus.STARTED,
                message=f"Human review opened by {reviewer.user_id} ({reviewer.role.value})",
                timestamp=now,
            )
        )
        state.audit_trail.append(
            AuditEvent(
                step="human_review",
                status=AuditEventStatus.SUCCESS,
                message=(
                    f"Human decision submitted by {reviewer.user_id} "
                    f"({reviewer.role.value}): {request.decision.value}; "
                    f"reason: {reason_summary}"
                ),
                timestamp=now,
            )
        )
        state.current_status = target
        state.claim_context = state.claim_context.model_copy(
            update={"claim_status": CLAIM_STATUS[request.decision]}
        )
        state.human_review_result = decision.model_dump(mode="json")
        state.updated_at = now
        state.audit_trail.append(
            AuditEvent(
                step="human_review",
                status=AuditEventStatus.SUCCESS,
                message={
                    HumanDecision.APPROVE: "Claim approved by human reviewer",
                    HumanDecision.REJECT: "Claim rejected by human reviewer",
                    HumanDecision.REQUEST_MORE_INFORMATION: "More information requested by human reviewer",
                    HumanDecision.ESCALATE: "Claim escalated by human reviewer",
                }[request.decision],
                timestamp=now,
            )
        )

        try:
            await self.repository.commit_decision(
                state=state,
                decision=decision,
                claim_status=CLAIM_STATUS[request.decision],
            )
        except ReviewDecisionConflictError as error:
            raise ReviewWorkflowConflictError(str(error)) from error

        # Generate customer notification
        notif_type = {
            HumanDecision.APPROVE: "claim_approved",
            HumanDecision.REJECT: "claim_rejected",
            HumanDecision.REQUEST_MORE_INFORMATION: "more_information_required",
            HumanDecision.ESCALATE: "claim_escalated",
        }[request.decision]
        title = {
            HumanDecision.APPROVE: "Claim Approved",
            HumanDecision.REJECT: "Claim Rejected",
            HumanDecision.REQUEST_MORE_INFORMATION: "Additional Information Required",
            HumanDecision.ESCALATE: "Claim Escalated for Review",
        }[request.decision]
        msg = {
            HumanDecision.APPROVE: "Your motor insurance claim has been approved by a claims officer.",
            HumanDecision.REJECT: f"Your claim has been reviewed and rejected. Reason: {request.reason}",
            HumanDecision.REQUEST_MORE_INFORMATION: f"A claims officer has requested more information: {request.reason}",
            HumanDecision.ESCALATE: "Your claim has been escalated for specialist human review.",
        }[request.decision]

        user_to_notify = state.authenticated_user_id or (
            state.claim_context.customer_id if state.claim_context else None
        )
        if user_to_notify:
            try:
                await self.notification_service.notify_customer(
                    user_id=user_to_notify,
                    workflow_id=workflow_id,
                    claim_id=decision.claim_id,
                    notification_type=notif_type,
                    title=title,
                    message=msg,
                )
                logger.info(
                    "Customer notification dispatched for workflow %s to user %s (%s)",
                    workflow_id,
                    user_to_notify,
                    notif_type,
                )
            except Exception as notif_err:
                logger.warning(
                    "Failed to dispatch customer notification for workflow %s: %s",
                    workflow_id,
                    notif_err,
                )

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
        policy = (
            PolicyContext.model_validate(
                {
                    key: value
                    for key, value in policy_data.items()
                    if key in PolicyContext.model_fields
                }
            )
            if policy_data
            else None
        )
        fraud = FraudAssessmentContext.model_validate(state.fraud_result)
        decision = await self.repository.get_decision(state.workflow_id)
        assignment = await self.repository.get_assignment(state.workflow_id)

        # Retrieve documents
        doc_repo = get_document_repository()
        docs: list[dict[str, Any]] = []
        cust_id = state.authenticated_user_id or (
            state.claim_context.customer_id if state.claim_context else None
        )
        if state.claim_context.claim_id and cust_id:
            try:
                raw_docs = await doc_repo.get_documents_for_claim(
                    state.claim_context.claim_id, cust_id
                )
            except Exception:
                raw_docs = []

            for d in raw_docs:
                meta = d.get("metadata") or {}
                fname = d.get("file_name") or meta.get("original_filename") or "document.pdf"
                docs.append({
                    "document_id": d.get("document_id"),
                    "claim_id": d.get("claim_id"),
                    "customer_id": d.get("customer_id"),
                    "document_type": d.get("document_type", "other"),
                    "original_filename": meta.get("original_filename") or fname,
                    "file_name": fname,
                    "file_size_bytes": meta.get("file_size") or d.get("file_size_bytes"),
                    "content_type": meta.get("content_type") or d.get("content_type"),
                    "uploaded_at": d.get("created_at") or meta.get("uploaded_at"),
                    "download_url": f"/documents/{d.get('document_id')}/download",
                })

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
            documents=docs,
            assigned_to=assignment.get("assigned_to") if assignment else None,
            assigned_at=assignment.get("assigned_at") if assignment else None,
        )

    @staticmethod
    def _queue_item(
        state: WorkflowState, assignment: dict | None = None
    ) -> ReviewQueueItem:
        if state.claim_context is None:
            raise ReviewWorkflowConflictError("Pending workflow has no claim")
        fraud = (
            FraudAssessmentContext.model_validate(state.fraud_result)
            if state.fraud_result
            else None
        )
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
            risk_level=fraud.risk_level.value if fraud else "unassessed",
            risk_score=fraud.risk_score if fraud else None,
            recommended_action=fraud.recommended_action.value if fraud else "manual_review",
            risk_indicator_count=len(fraud.indicators) if fraud else 0,
            status=state.current_status.value,
            assigned_to=assignment.get("assigned_to") if assignment else None,
            assigned_at=assignment.get("assigned_at") if assignment else None,
            missing_documents=(
                [item.value for item in fraud.missing_documents]
                if fraud
                else []
            ),
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
