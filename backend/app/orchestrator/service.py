"""Foundation service for managing Orchestrator workflow state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    AuditEventStatus,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.schemas.orchestrator import (
    AuditEvent,
    OrchestratorError,
    OrchestratorRequest,
    OrchestratorResponse,
)


class InvalidWorkflowTransition(ValueError):
    """Raised when a workflow attempts a disallowed lifecycle transition."""


class OrchestratorService:
    """Create and safely mutate workflow state without routing agents yet."""

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
            step="orchestrator",
            status=AuditEventStatus.SUCCESS,
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
            message=reason,
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
            message="Workflow failed",
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

    def determine_workflow_type(self, _state: WorkflowState) -> WorkflowType:
        """Placeholder for the next implementation step's routing rules."""

        return WorkflowType.UNKNOWN

    async def route_next_step(self, _state: WorkflowState) -> None:
        """Placeholder for future agent routing and human-review coordination."""

        raise NotImplementedError("Orchestrator routing is not implemented yet")
