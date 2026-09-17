"""Orchestrator service for Agent 1 intake and initial workflow routing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Iterable

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.agent_clients import (
    ClaimIntakeClient,
    LocalClaimIntakeClient,
)
from backend.app.orchestrator.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    AuditEventStatus,
    CLARIFICATION_QUESTIONS,
    INTENT_TO_WORKFLOW_TYPE,
    LOW_CONFIDENCE_CLARIFICATION_MESSAGE,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.schemas.intake import IntakeRequest, IntakeResponse
from backend.app.schemas.orchestrator import (
    AuditEvent,
    ClarificationResponse,
    OrchestratorError,
    OrchestratorRequest,
    OrchestratorResponse,
)


logger = logging.getLogger(__name__)


class InvalidWorkflowTransition(ValueError):
    """Raised when a workflow attempts a disallowed lifecycle transition."""


class OrchestratorService:
    """Run Agent 1 and determine which future workflow should handle a request."""

    def __init__(self, claim_intake_client: ClaimIntakeClient | None = None) -> None:
        self.claim_intake_client = claim_intake_client or LocalClaimIntakeClient()

    def validate_request(self, request: OrchestratorRequest) -> None:
        if not isinstance(request, OrchestratorRequest):
            raise TypeError("request must be an OrchestratorRequest instance")

    def create_initial_state(
        self,
        request: OrchestratorRequest,
        *,
        authenticated_user_id: str | None = None,
        authenticated_user_role: str | None = None,
    ) -> WorkflowState:
        """Create received state; authentication context comes from outside."""

        self.validate_request(request)
        state = WorkflowState(
            request_id=request.request_id,
            raw_text=request.text,
            authenticated_user_id=authenticated_user_id,
            authenticated_user_role=authenticated_user_role,
        )
        self.append_audit_event(
            state,
            step="orchestrator",
            status=AuditEventStatus.SUCCESS,
            message="Workflow request received",
        )
        return state

    def append_audit_event(
        self,
        state: WorkflowState,
        *,
        step: str,
        status: AuditEventStatus,
        message: str,
    ) -> AuditEvent:
        event = AuditEvent(step=step, status=status, message=message)
        state.audit_trail.append(event)
        state.updated_at = datetime.now(timezone.utc)
        return event

    def update_status(
        self,
        state: WorkflowState,
        new_status: WorkflowStatus,
        *,
        message: str | None = None,
        step: str = "orchestrator",
        audit_status: AuditEventStatus = AuditEventStatus.SUCCESS,
    ) -> WorkflowState:
        """Apply one controlled lifecycle transition and record it."""

        new_status = WorkflowStatus(new_status)
        allowed = ALLOWED_STATUS_TRANSITIONS[state.current_status]
        if new_status not in allowed:
            raise InvalidWorkflowTransition(
                f"Cannot transition from {state.current_status.value} "
                f"to {new_status.value}"
            )

        state.current_status = new_status
        self.append_audit_event(
            state,
            step=step,
            status=audit_status,
            message=message or f"Workflow status changed to {new_status.value}",
        )
        return state

    def mark_clarification_required(
        self,
        state: WorkflowState,
        missing_fields: Iterable[str] = (),
        *,
        reason: str = "Additional user information is required",
    ) -> WorkflowState:
        """Represent a workflow pause without generating clarification text."""

        state.missing_fields = list(dict.fromkeys(missing_fields))
        state.requires_clarification = True
        state.workflow_type = WorkflowType.CLARIFICATION
        self.update_status(
            state,
            WorkflowStatus.AWAITING_CLARIFICATION,
            message=f"Clarification required: {reason}",
        )
        state.audit_trail[-1].status = AuditEventStatus.AWAITING_INPUT
        return state

    def mark_failed(
        self,
        state: WorkflowState,
        *,
        code: str,
        message: str,
        step: str = "orchestrator",
    ) -> WorkflowState:
        """Record a controlled error and move a non-terminal workflow to failed."""

        state.errors.append(OrchestratorError(code=code, message=message, step=step))
        self.update_status(
            state,
            WorkflowStatus.FAILED,
            message=f"{step.replace('_', ' ').title()} failed",
            step=step,
        )
        state.audit_trail[-1].status = AuditEventStatus.FAILED
        return state

    def to_response(self, state: WorkflowState) -> OrchestratorResponse:
        """Create a public response snapshot from current workflow state."""

        return OrchestratorResponse(
            request_id=state.request_id,
            status=state.current_status,
            workflow_type=state.workflow_type,
            intake_result=state.intake_result,
            retrieval_result=state.retrieval_result,
            fraud_result=state.fraud_result,
            human_review_result=state.human_review_result,
            guidance_result=state.guidance_result,
            missing_fields=list(state.missing_fields),
            requires_clarification=state.requires_clarification,
            errors=list(state.errors),
            audit_trail=list(state.audit_trail),
        )

    def determine_workflow_type(self, state: WorkflowState) -> WorkflowType:
        """Map Agent 1's intent to one controlled Orchestrator workflow type."""

        if state.intake_result is None:
            return WorkflowType.UNKNOWN
        intent_label = state.intake_result.data.intent.label
        return INTENT_TO_WORKFLOW_TYPE.get(intent_label or "", WorkflowType.UNKNOWN)

    @staticmethod
    def _questions_for(missing_fields: Iterable[str]) -> list[str]:
        return [
            CLARIFICATION_QUESTIONS[field]
            for field in dict.fromkeys(missing_fields)
            if field in CLARIFICATION_QUESTIONS
        ]

    def _clarification_response(
        self,
        state: WorkflowState,
        *,
        reason: str,
        questions: list[str],
    ) -> ClarificationResponse:
        return ClarificationResponse(
            request_id=state.request_id,
            intake_result=state.intake_result,
            missing_fields=list(state.missing_fields),
            questions=questions,
            reason=reason,
            audit_trail=list(state.audit_trail),
        )

    async def process_request(
        self,
        request: OrchestratorRequest,
        authenticated_user_id: str | None = None,
        authenticated_user_role: str | None = None,
    ) -> OrchestratorResponse | ClarificationResponse:
        """Run intake, then stop at clarification or a downstream-ready state."""

        state = self.create_initial_state(
            request,
            authenticated_user_id=authenticated_user_id,
            authenticated_user_role=authenticated_user_role,
        )
        self.update_status(
            state,
            WorkflowStatus.INTAKE_PROCESSING,
            message="Claim intake started",
            step="claim_intake",
            audit_status=AuditEventStatus.STARTED,
        )

        try:
            intake_response = await self.claim_intake_client.analyze(
                IntakeRequest(request_id=request.request_id, text=request.text)
            )
            if not isinstance(intake_response, IntakeResponse):
                raise TypeError("Claim Intake client returned an invalid response")
            state.intake_result = intake_response
        except Exception:
            logger.exception(
                "Claim intake client failed for request %s",
                request.request_id,
            )
            self.mark_failed(
                state,
                code="CLAIM_INTAKE_FAILED",
                message="Claim Intake Agent failed to analyze the request",
                step="claim_intake",
            )
            return self.to_response(state)

        if intake_response.status == "error":
            self.mark_failed(
                state,
                code="CLAIM_INTAKE_FAILED",
                message="Claim Intake Agent failed to analyze the request",
                step="claim_intake",
            )
            return self.to_response(state)

        if intake_response.status != "success":
            self.mark_failed(
                state,
                code="CLAIM_INTAKE_INVALID_STATUS",
                message="Claim Intake Agent returned an unsupported status",
                step="claim_intake",
            )
            return self.to_response(state)

        self.append_audit_event(
            state,
            step="claim_intake",
            status=AuditEventStatus.SUCCESS,
            message="Claim intake completed",
        )

        mapped_workflow = self.determine_workflow_type(state)
        state.workflow_type = mapped_workflow
        state.missing_fields = list(dict.fromkeys(intake_response.data.missing_fields))
        agent_requires_clarification = intake_response.data.requires_clarification
        claim_fields_missing = (
            mapped_workflow is WorkflowType.CLAIM_SUBMISSION
            and bool(state.missing_fields)
        )
        unknown_intent = mapped_workflow is WorkflowType.UNKNOWN
        state.requires_clarification = (
            agent_requires_clarification or claim_fields_missing or unknown_intent
        )

        self.append_audit_event(
            state,
            step="workflow_routing",
            status=AuditEventStatus.SUCCESS,
            message=f"Workflow type determined as {mapped_workflow.value}",
        )

        if state.requires_clarification:
            questions = self._questions_for(state.missing_fields)
            if questions:
                reason = "Additional claim information is required"
            else:
                reason = LOW_CONFIDENCE_CLARIFICATION_MESSAGE
                questions = [LOW_CONFIDENCE_CLARIFICATION_MESSAGE]

            self.mark_clarification_required(
                state,
                state.missing_fields,
                reason=reason,
            )
            return self._clarification_response(
                state,
                reason=reason,
                questions=questions,
            )

        self.update_status(
            state,
            WorkflowStatus.INTAKE_COMPLETE,
            message="Request understood and ready for downstream routing",
        )
        return self.to_response(state)

    async def route_next_step(self, _state: WorkflowState) -> None:
        """Placeholder for future agent routing and human-review coordination."""

        raise NotImplementedError("Orchestrator routing is not implemented yet")
