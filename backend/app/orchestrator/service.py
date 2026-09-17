"""Orchestrator service for Agent 1 intake and initial workflow routing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Iterable
from uuid import uuid4

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.agent_clients import (
    ClaimIntakeClient,
    LocalClaimIntakeClient,
    RetrievalClient,
)
from backend.app.orchestrator.adapters import build_retrieval_request
from backend.app.orchestrator.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    AuditEventStatus,
    CLARIFICATION_LIMIT_MESSAGE,
    CLARIFICATION_QUESTIONS,
    INTENT_TO_WORKFLOW_TYPE,
    LOW_CONFIDENCE_CLARIFICATION_MESSAGE,
    MAX_CLARIFICATION_ATTEMPTS,
    WorkflowStatus,
    WorkflowType,
)
from backend.app.orchestrator.repository import (
    InMemoryWorkflowRepository,
    WorkflowRepository,
)
from backend.app.schemas.intake import IntakeRequest, IntakeResponse
from backend.app.retrieval.schemas import RetrievalResponse
from backend.app.schemas.orchestrator import (
    AuditEvent,
    ClarificationRequest,
    ClarificationResponse,
    OrchestratorError,
    OrchestratorRequest,
    OrchestratorResponse,
)


logger = logging.getLogger(__name__)


class InvalidWorkflowTransition(ValueError):
    """Raised when a workflow attempts a disallowed lifecycle transition."""


class WorkflowNotFoundError(LookupError):
    """Raised when a requested persisted workflow does not exist."""


class WorkflowNotResumableError(ValueError):
    """Raised when clarification is submitted to a non-waiting workflow."""


class WorkflowAccessDeniedError(PermissionError):
    """Raised when a caller does not own the requested workflow."""


class OrchestratorService:
    """Run Agent 1 and determine which future workflow should handle a request."""

    def __init__(
        self,
        claim_intake_client: ClaimIntakeClient | None = None,
        workflow_repository: WorkflowRepository | None = None,
        retrieval_client: RetrievalClient | None = None,
    ) -> None:
        self.claim_intake_client = claim_intake_client or LocalClaimIntakeClient()
        self.retrieval_client = retrieval_client
        self.workflow_repository = (
            workflow_repository or InMemoryWorkflowRepository()
        )

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
        workflow_id = f"WF-{uuid4().hex.upper()}"
        state = WorkflowState(
            workflow_id=workflow_id,
            request_id=request.request_id,
            last_request_id=request.request_id,
            raw_text=request.text,
            original_text=request.text,
            accumulated_text=request.text,
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

        retrieval_result = self._public_retrieval_result(state.retrieval_result)
        retrieval_status = (
            str(retrieval_result.get("status")) if retrieval_result else None
        )
        retrieval_body = retrieval_result.get("result", {}) if retrieval_result else {}
        warnings = list(retrieval_body.get("warnings", []))
        evidence_summary = list(retrieval_body.get("knowledge_evidence", []))
        message = self._retrieval_message(retrieval_status)

        return OrchestratorResponse(
            request_id=state.last_request_id,
            workflow_id=state.workflow_id,
            status=state.current_status,
            workflow_type=state.workflow_type,
            intake_result=state.intake_result,
            retrieval_result=retrieval_result,
            retrieval_status=retrieval_status,
            warnings=warnings,
            evidence_summary=evidence_summary,
            message=message,
            fraud_result=state.fraud_result,
            human_review_result=state.human_review_result,
            guidance_result=state.guidance_result,
            missing_fields=list(state.missing_fields),
            requires_clarification=state.requires_clarification,
            errors=list(state.errors),
            audit_trail=list(state.audit_trail),
        )

    @staticmethod
    def _public_retrieval_result(
        retrieval_result: dict | None,
    ) -> dict | None:
        """Remove ingestion-only metadata while preserving grounded evidence."""
        if retrieval_result is None:
            return None
        public = {
            key: value for key, value in retrieval_result.items()
        }
        result = dict(public.get("result") or {})
        safe_evidence = []
        allowed_metadata = {
            "source_document_id", "chunk_id", "document_type",
            "insurance_type", "page", "query_intent",
        }
        for item in result.get("knowledge_evidence", []):
            evidence = dict(item)
            metadata = dict(evidence.get("metadata") or {})
            evidence["metadata"] = {
                key: value for key, value in metadata.items()
                if key in allowed_metadata
            }
            safe_evidence.append(evidence)
        result["knowledge_evidence"] = safe_evidence
        public["result"] = result
        return public

    @staticmethod
    def _retrieval_message(status: str | None) -> str | None:
        return {
            "success": (
                "Relevant controlled policy information was retrieved. "
                "Final guidance is not yet connected."
            ),
            "partial_success": (
                "Some controlled policy information was retrieved. "
                "Final guidance is not yet connected."
            ),
            "no_results": "No relevant controlled evidence was found.",
            "failed": "Policy information retrieval failed.",
        }.get(status)

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
            request_id=state.last_request_id,
            workflow_id=state.workflow_id,
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
            await self.workflow_repository.save(state)
            return self.to_response(state)

        if intake_response.status == "error":
            self.mark_failed(
                state,
                code="CLAIM_INTAKE_FAILED",
                message="Claim Intake Agent failed to analyze the request",
                step="claim_intake",
            )
            await self.workflow_repository.save(state)
            return self.to_response(state)

        if intake_response.status != "success":
            self.mark_failed(
                state,
                code="CLAIM_INTAKE_INVALID_STATUS",
                message="Claim Intake Agent returned an unsupported status",
                step="claim_intake",
            )
            await self.workflow_repository.save(state)
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
            await self.workflow_repository.save(state)
            return self._clarification_response(
                state,
                reason=reason,
                questions=questions,
            )

        await self.workflow_repository.save(state)
        await self._advance_after_intake(
            state,
            completion_message="Request understood and ready for downstream routing",
            completion_step="orchestrator",
        )
        await self.workflow_repository.save(state)
        return self.to_response(state)

    async def resume_clarification(
        self,
        workflow_id: str,
        request: ClarificationRequest,
        authenticated_user_id: str | None = None,
        authenticated_user_role: str | None = None,
    ) -> OrchestratorResponse | ClarificationResponse:
        """Append clarification context and resume one persisted workflow."""

        state = await self.workflow_repository.get(workflow_id)
        if state is None:
            raise WorkflowNotFoundError("Workflow not found")
        if (
            authenticated_user_id is None
            or state.authenticated_user_id != authenticated_user_id
        ):
            logger.warning(
                "Workflow access denied: workflow %s requesting user %s",
                workflow_id,
                authenticated_user_id or "unauthenticated",
            )
            raise WorkflowAccessDeniedError(
                "You are not authorized to access this workflow"
            )
        if state.current_status is not WorkflowStatus.AWAITING_CLARIFICATION:
            raise WorkflowNotResumableError(
                "Workflow is not awaiting clarification"
            )

        # The stored role remains authoritative for this workflow. Role-specific
        # reviewer behavior is intentionally outside this step.
        _ = authenticated_user_role
        state.last_request_id = request.request_id
        state.clarification_count += 1
        state.accumulated_text = (
            f"{state.accumulated_text.rstrip()} {request.text.strip()}"
        )
        self.append_audit_event(
            state,
            step="clarification",
            status=AuditEventStatus.SUCCESS,
            message="Clarification received",
        )
        self.update_status(
            state,
            WorkflowStatus.INTAKE_PROCESSING,
            message="Clarification analysis started",
            step="clarification",
            audit_status=AuditEventStatus.STARTED,
        )

        try:
            intake_response = await self.claim_intake_client.analyze(
                IntakeRequest(
                    request_id=request.request_id,
                    text=state.accumulated_text,
                )
            )
            if not isinstance(intake_response, IntakeResponse):
                raise TypeError("Claim Intake client returned an invalid response")
            state.intake_result = intake_response
        except Exception:
            logger.exception(
                "Clarification analysis failed for workflow %s request %s",
                state.workflow_id,
                request.request_id,
            )
            self.mark_failed(
                state,
                code="CLARIFICATION_ANALYSIS_FAILED",
                message="Clarification could not be analyzed",
                step="clarification",
            )
            await self.workflow_repository.save(state)
            return self.to_response(state)

        if intake_response.status != "success":
            self.mark_failed(
                state,
                code="CLARIFICATION_ANALYSIS_FAILED",
                message="Clarification could not be analyzed",
                step="clarification",
            )
            await self.workflow_repository.save(state)
            return self.to_response(state)

        self.append_audit_event(
            state,
            step="clarification",
            status=AuditEventStatus.SUCCESS,
            message="Clarification analysis completed",
        )

        mapped_workflow = self.determine_workflow_type(state)
        state.workflow_type = mapped_workflow
        state.missing_fields = list(dict.fromkeys(intake_response.data.missing_fields))
        claim_fields_missing = (
            mapped_workflow is WorkflowType.CLAIM_SUBMISSION
            and bool(state.missing_fields)
        )
        state.requires_clarification = (
            intake_response.data.requires_clarification
            or claim_fields_missing
            or mapped_workflow is WorkflowType.UNKNOWN
        )

        if state.requires_clarification:
            if state.clarification_count >= MAX_CLARIFICATION_ATTEMPTS:
                state.workflow_type = WorkflowType.CLARIFICATION
                state.errors.append(
                    OrchestratorError(
                        code="CLARIFICATION_LIMIT_REACHED",
                        message=CLARIFICATION_LIMIT_MESSAGE,
                        step="clarification",
                    )
                )
                self.update_status(
                    state,
                    WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
                    message="Clarification limit reached",
                    step="clarification",
                    audit_status=AuditEventStatus.AWAITING_INPUT,
                )
                await self.workflow_repository.save(state)
                return self.to_response(state)

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
            state.audit_trail[-1].message = (
                f"Clarification still required: {reason}"
            )
            await self.workflow_repository.save(state)
            return self._clarification_response(
                state,
                reason=reason,
                questions=questions,
            )

        await self.workflow_repository.save(state)
        await self._advance_after_intake(
            state,
            completion_message="Intake completed after clarification",
            completion_step="clarification",
        )
        await self.workflow_repository.save(state)
        return self.to_response(state)

    async def _advance_after_intake(
        self,
        state: WorkflowState,
        *,
        completion_message: str,
        completion_step: str,
    ) -> None:
        """Run Agent 2 only for information requests, then stop before guidance."""
        if (
            state.workflow_type is not WorkflowType.INFORMATION_REQUEST
            or self.retrieval_client is None
        ):
            self.update_status(
                state,
                WorkflowStatus.INTAKE_COMPLETE,
                message=completion_message,
                step=completion_step,
            )
            return

        if state.intake_result is None or state.authenticated_user_id is None:
            self.mark_failed(
                state,
                code="RETRIEVAL_CONTEXT_INVALID",
                message="Information retrieval could not be started safely",
                step="information_retrieval",
            )
            return

        self.update_status(
            state,
            WorkflowStatus.INFORMATION_RETRIEVAL,
            message="Information retrieval started",
            step="information_retrieval",
            audit_status=AuditEventStatus.STARTED,
        )
        await self.workflow_repository.save(state)

        try:
            retrieval_request = build_retrieval_request(
                request_id=state.last_request_id,
                authenticated_user_id=state.authenticated_user_id,
                original_query=state.accumulated_text,
                intake=state.intake_result,
            )
            retrieval_response = await self.retrieval_client.retrieve(
                retrieval_request
            )
            if not isinstance(retrieval_response, RetrievalResponse):
                raise TypeError("Retrieval client returned an invalid response")
            state.retrieval_result = retrieval_response.model_dump(mode="json")
        except Exception:
            logger.exception(
                "Information retrieval client failed for workflow %s",
                state.workflow_id,
            )
            self.mark_failed(
                state,
                code="RETRIEVAL_FAILED",
                message="Information retrieval could not be completed",
                step="information_retrieval",
            )
            return

        if retrieval_response.status == "failed":
            self.mark_failed(
                state,
                code="RETRIEVAL_FAILED",
                message="Information retrieval could not be completed",
                step="information_retrieval",
            )
            return

        messages = {
            "success": "Information retrieval completed",
            "partial_success": "Information retrieval partially completed",
            "no_results": "Information retrieval returned no results",
        }
        self.update_status(
            state,
            WorkflowStatus.RETRIEVAL_COMPLETE,
            message=messages[retrieval_response.status],
            step="information_retrieval",
        )

    async def route_next_step(self, _state: WorkflowState) -> None:
        """Placeholder for future agent routing and human-review coordination."""

        raise NotImplementedError("Orchestrator routing is not implemented yet")
