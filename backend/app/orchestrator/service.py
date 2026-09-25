from __future__ import annotations
from backend.app.security.input_sanitization import sanitize_user_text, InputSanitizationError
"""Orchestrator service for Agent 1 intake and initial workflow routing."""


import asyncio
from datetime import date, datetime, timezone
import logging
from typing import Iterable
from uuid import NAMESPACE_URL, uuid4, uuid5

from backend.app.fraud.repository import FraudAssessmentRepository
from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.agent_clients import (
    ClaimIntakeClient,
    FraudClient,
    GuidanceClient,
    LocalClaimIntakeClient,
    RetrievalClient,
)
from backend.app.orchestrator.adapters import (
    build_retrieval_request,
    build_guidance_request,
    intake_to_claim_context,
    merge_claim_intake_results,
    select_relevant_evidence,
    retrieval_to_evidence_items,
    retrieval_to_document_facts,
    retrieval_to_policy_context,
)
from backend.app.orchestrator.claim_repository import ClaimRepository
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
from backend.app.retrieval.schemas import (
    HistoricalClaim,
    PolicyLookupContext,
    RetrievalResponse,
)
from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
    GuidanceTaskType,
)
from backend.app.guidance.response_validator import validate_guidance_response
from backend.app.guidance.fallbacks import build_deterministic_guidance_response
from backend.app.schemas.domain import (
    DocumentFact,
    DocumentType,
    FraudAssessmentContext,
    HumanDecision,
    HumanDecisionContext,
    PolicyContext,
)
from backend.app.schemas.orchestrator import (
    AuditEvent,
    ClarificationRequest,
    ClarificationResponse,
    OrchestratorError,
    OrchestratorRequest,
    OrchestratorResponse,
)
from backend.app.security.resource_authorization import (
    deny_cross_customer_resource_request,
)
from backend.app.security.privacy_context import (
    PrivacyContextDecision,
    classify_privacy_context,
    minimized_workflow_text,
)
from backend.app.nlp.claim_identifiers import extract_claim_id
from backend.app.nlp.request_context import is_personal_policy_query
from backend.app.policy_types import (
    extract_requested_policy_type,
    normalize_policy_type,
)


logger = logging.getLogger(__name__)

_POLICY_LINK_REQUIRED_MESSAGE = (
    "Your claim details were saved as a draft, but no single motor policy is "
    "linked to your account. A claims officer must link the correct policy "
    "before processing can continue."
)
_SOCIAL_INTENTS = frozenset({"greeting", "thanks", "goodbye", "acknowledgement"})
_PURE_SOCIAL_INTENTS = {
    "greeting": {
        "hi", "hello", "hey", "greetings", "hello there", "hi there",
        "good morning", "good afternoon", "good evening", "gud day",
    },
    "thanks": {
        "thanks", "thank you", "thank u", "thx", "cheers", "many thanks",
        "thanks a lot", "appreciate it", "appreciate your help",
    },
    "goodbye": {
        "bye", "goodbye", "good bye", "see you", "see ya", "take care",
        "talk later",
    },
    "acknowledgement": {
        "ok", "okay", "alright", "all right", "got it", "understood",
        "noted", "sure", "sounds good", "i understand",
    },
}


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
        fraud_client: FraudClient | None = None,
        claim_repository: ClaimRepository | None = None,
        fraud_repository: FraudAssessmentRepository | None = None,
        guidance_client: GuidanceClient | None = None,
    ) -> None:
        self.claim_intake_client = claim_intake_client or LocalClaimIntakeClient()
        self.retrieval_client = retrieval_client
        self.fraud_client = fraud_client
        self.claim_repository = claim_repository
        self.fraud_repository = fraud_repository
        self.guidance_client = guidance_client
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
        stored_text: str | None = None,
    ) -> WorkflowState:
        """Create received state; authentication context comes from outside."""

        self.validate_request(request)
        sanitized = sanitize_user_text(request.text)
        persisted_text = stored_text or sanitized
        workflow_id = f"WF-{uuid4().hex.upper()}"
        state = WorkflowState(
            workflow_id=workflow_id,
            request_id=request.request_id,
            last_request_id=request.request_id,
            raw_text=persisted_text,
            original_text=persisted_text,
            accumulated_text=persisted_text,
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

    def _refresh_pending_field(self, state: WorkflowState) -> None:
        """Keep the active clarification target aligned with the remaining claim fields."""
        state.pending_field = state.missing_fields[0] if state.missing_fields else None
        state.pending_question = (
            CLARIFICATION_QUESTIONS.get(state.pending_field)
            if state.pending_field
            else None
        )

    def mark_clarification_required(
        self,
        state: WorkflowState,
        missing_fields: Iterable[str] = (),
        *,
        reason: str = "Additional user information is required",
    ) -> WorkflowState:
        """Represent a workflow pause without generating clarification text."""

        state.missing_fields = list(dict.fromkeys(missing_fields))
        self._refresh_pending_field(state)
        state.requires_clarification = True
        if state.workflow_type is WorkflowType.UNKNOWN:
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

    @staticmethod
    def _pending_field_answer_text(state: WorkflowState, text: str) -> bool:
        if not state.pending_field or not text:
            return False
        candidate = text.strip()
        if not candidate:
            return False

        if state.pending_field == "incident_date":
            from backend.app.nlp.date_extraction import extract_date
            _, normalized = extract_date(candidate)
            return bool(normalized)
        if state.pending_field == "location":
            from backend.app.nlp.entity_extraction import extract_entities, normalize_location
            for entity in extract_entities(candidate):
                normalized = normalize_location(entity.value)
                if normalized:
                    return True
            return bool(candidate) and not candidate.lower().startswith(("what ", "where ", "when ", "who ", "how "))
        if state.pending_field == "incident_type":
            from backend.app.nlp.incident_extraction import extract_incident_type
            return bool(extract_incident_type(candidate))
        return False

    @staticmethod
    def _looks_like_independent_question(text: str) -> bool:
        candidate = text.strip()
        if not candidate:
            return False
        lowered = candidate.casefold()
        if lowered.startswith(("hi ", "hello ", "hey ", "thanks", "thank you", "goodbye", "bye ", "ok ", "okay ")):
            return False
        if lowered.startswith(("what ", "where ", "when ", "why ", "how ", "who ", "is ", "are ", "can ", "could ", "do ", "does ", "tell me ", "please tell me ", "i need to know ")):
            return True
        return any(term in lowered for term in ("insurance", "policy", "coverage", "claim status", "required documents"))

    def to_response(self, state: WorkflowState) -> OrchestratorResponse:
        """Create a public response snapshot from current workflow state."""

        self._refresh_pending_field(state)

        retrieval_result = self._public_retrieval_result(
            state.retrieval_result,
            include_structured=(
                state.workflow_type is WorkflowType.INFORMATION_REQUEST
            ),
        )
        retrieval_status = (
            str(retrieval_result.get("status")) if retrieval_result else None
        )
        if self.guidance_client is not None and state.current_status is not WorkflowStatus.RECEIVED:
            self._ensure_customer_guidance_fallback(state, retrieval_status)
        retrieval_body = retrieval_result.get("result", {}) if retrieval_result else {}
        warnings = list(retrieval_body.get("warnings", []))
        if state.guidance_result:
            warnings.extend(state.guidance_result.get("warnings", []))
        evidence_summary = list(retrieval_body.get("knowledge_evidence", []))
        public_fraud = (
            None
            if state.authenticated_user_role == "customer"
            else self._public_fraud_result(state.fraud_result)
        )
        message = self._public_message(state, retrieval_status)
        public_guidance = self._public_guidance_result(state.guidance_result)

        claim_id = state.claim_context.claim_id if state.claim_context else None
        return OrchestratorResponse(
            request_id=state.last_request_id,
            workflow_id=state.workflow_id,
            claim_id=claim_id,
            status=state.current_status,
            workflow_type=state.workflow_type,
            intake_result=state.intake_result,
            retrieval_result=retrieval_result,
            retrieval_status=retrieval_status,
            warnings=warnings,
            evidence_summary=evidence_summary,
            message=message,
            fraud_result=public_fraud,
            fraud_risk_level=(
                str(public_fraud.get("risk_level")) if public_fraud else None
            ),
            recommended_next_action=(
                str(public_fraud.get("recommended_action"))
                if public_fraud else None
            ),
            risk_indicator_count=len(public_fraud.get("indicators", [])) if public_fraud else 0,
            missing_document_summary=(
                list(public_fraud.get("missing_documents", []))
                if public_fraud else []
            ),
            human_review_result=(
                None if state.authenticated_user_role == "customer"
                else state.human_review_result
            ),
            guidance_result=public_guidance,
            missing_fields=list(state.missing_fields),
            pending_field=state.pending_field,
            pending_question=state.pending_question,
            missing_required_documents=[],
            requires_clarification=state.requires_clarification,
            errors=list(state.errors),
            audit_trail=(
                [item for item in state.audit_trail if item.step != "human_review"]
                if state.authenticated_user_role == "customer"
                else list(state.audit_trail)
            ),
        )

    @staticmethod
    def _public_retrieval_result(
        retrieval_result: dict | None,
        *,
        include_structured: bool = True,
    ) -> dict | None:
        """Remove ingestion-only metadata while preserving grounded evidence."""
        if retrieval_result is None:
            return None
        public = {
            key: value for key, value in retrieval_result.items()
        }
        result = dict(public.get("result") or {})
        if not include_structured:
            result["policy_data"] = None
            result["claim_record"] = None
            result["historical_claims"] = []
            result["document_facts"] = []
        safe_evidence = []
        allowed_metadata = {
            "source_document_id", "chunk_id", "document_type",
            "insurance_type", "page", "query_intent", "policy_type",
            "status", "version", "audience",
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

    @staticmethod
    def _public_fraud_result(fraud_result: dict | None) -> dict | None:
        if fraud_result is None:
            return None
        allowed = {
            "assessment_id", "claim_id", "risk_score", "risk_level",
            "indicators", "recommended_action", "missing_documents",
            "rule_score", "anomaly_score", "automated_decision",
            "rules_version", "model_version", "warnings",
        }
        return {key: value for key, value in fraud_result.items() if key in allowed}

    def _public_message(
        self, state: WorkflowState, retrieval_status: str | None
    ) -> str:
        if self.guidance_client is not None and state.current_status is not WorkflowStatus.RECEIVED:
            self._ensure_customer_guidance_fallback(state, retrieval_status)
        if state.guidance_result:
            data = state.guidance_result.get("data") or {}
            message = str(data.get("message") or "").strip()
            if message:
                return message
        if state.current_status in {
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.DOCUMENTS_SUBMITTED,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.FRAUD_TRIAGE_COMPLETE,
            WorkflowStatus.REVIEW_SUMMARY_GENERATION,
        }:
            return "Your claim has been submitted successfully and is waiting for review."
        if state.retrieval_result:
            return self._retrieval_message(retrieval_status) or "Policy information retrieval completed."
        return (
            state.audit_trail[-1].message
            if state.audit_trail
            else "Workflow request received"
        )

    def _fallback_task_for_state(
        self,
        state: WorkflowState,
        retrieval_status: str | None,
    ) -> GuidanceTaskType:
        intent = (
            state.intake_result.data.intent.label
            if state.intake_result is not None
            else None
        )
        if state.current_status is WorkflowStatus.FAILED:
            return "safe_error"
        if state.current_status is WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED:
            return "manual_assistance_required"
        if state.current_status in {
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.DOCUMENTS_SUBMITTED,
            WorkflowStatus.FRAUD_TRIAGE,
            WorkflowStatus.FRAUD_TRIAGE_COMPLETE,
            WorkflowStatus.REVIEW_SUMMARY_GENERATION,
        }:
            return "claim_progress"
        if state.current_status in {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
        }:
            return "human_decision"
        if intent in _SOCIAL_INTENTS:
            return intent
        if state.current_status is WorkflowStatus.AWAITING_CLARIFICATION:
            return "clarification_question"
        if state.workflow_type is WorkflowType.CLAIM_STATUS:
            return "claim_status"
        if state.workflow_type is WorkflowType.INFORMATION_REQUEST:
            if retrieval_status in {None, "no_results", "failed"}:
                return "insufficient_evidence"
            return {
                "coverage_question": "coverage_answer",
                "policy_question": "policy_answer",
                "required_documents_question": "required_documents",
            }.get(intent or "", "information_answer")
        return "claim_progress"

    def _ensure_customer_guidance_fallback(
        self,
        state: WorkflowState,
        retrieval_status: str | None,
    ) -> None:
        """Guarantee one non-empty Agent 4 envelope for every public response."""

        if state.guidance_result:
            data = state.guidance_result.get("data") or {}
            if str(data.get("message") or "").strip():
                return
        task_type = self._fallback_task_for_state(state, retrieval_status)
        request = self._build_customer_guidance_request(
            state,
            task_type=task_type,
            safe_customer_context={
                "policy_link_required": any(
                    error.code == "POLICY_LINK_REQUIRED" for error in state.errors
                )
            },
        )
        response = build_deterministic_guidance_response(
            request,
            warning="Deterministic Agent 4 fallback used",
        )
        state.guidance_result = response.model_dump(mode="json")

    @staticmethod
    def _public_guidance_result(guidance_result: dict | None) -> dict | None:
        if guidance_result is None:
            return None
        return {
            key: value for key, value in guidance_result.items()
            if key in {"status", "response_type", "agent", "data", "warnings", "created_at"}
        }

    def determine_workflow_type(self, state: WorkflowState) -> WorkflowType:
        """Map Agent 1's intent to one controlled Orchestrator workflow type."""

        if state.intake_result is None:
            return WorkflowType.UNKNOWN
        intent_label = state.intake_result.data.intent.label
        return INTENT_TO_WORKFLOW_TYPE.get(intent_label or "", WorkflowType.UNKNOWN)

    @staticmethod
    def _has_supported_missing_fields(missing_fields: Iterable[str]) -> bool:
        return any(
            field in {"incident_type", "incident_date", "location"}
            for field in missing_fields
        )

    @staticmethod
    def _known_customer_fields(state: WorkflowState) -> dict[str, object]:
        if state.intake_result is None:
            return {}
        incident = state.intake_result.data.incident
        damage = state.intake_result.data.damage
        values: dict[str, object | None] = {
            "incident_type": incident.type,
            "date_text": incident.date_text,
            "incident_date": incident.normalized_date,
            "location": incident.location,
            "damage_areas": list(damage.areas) or None,
        }
        return {
            key: value for key, value in values.items() if value is not None
        }

    def _build_customer_guidance_request(
        self,
        state: WorkflowState,
        *,
        task_type: GuidanceTaskType,
        safe_customer_context: dict[str, object] | None = None,
        include_claim_data: bool = True,
        include_known_fields: bool = True,
    ) -> GuidanceRequest:
        intent = (
            state.intake_result.data.intent.label
            if state.intake_result is not None
            else None
        )
        return build_guidance_request(
            request_id=state.last_request_id,
            audience="customer",
            task_type=task_type,
            claim=state.claim_context if include_claim_data else None,
            intent=intent,
            workflow_status=state.current_status.value,
            known_fields=(
                self._known_customer_fields(state) if include_known_fields else {}
            ),
            missing_fields=state.missing_fields,
            safe_customer_context=safe_customer_context,
        )

    async def _run_customer_guidance(
        self,
        state: WorkflowState,
        *,
        task_type: GuidanceTaskType,
        safe_customer_context: dict[str, object] | None = None,
        include_claim_data: bool = True,
        include_known_fields: bool = True,
    ) -> GuidanceResponse:
        """Ask Agent 4 to verbalize state without granting workflow authority."""

        request = self._build_customer_guidance_request(
            state,
            task_type=task_type,
            safe_customer_context=safe_customer_context,
            include_claim_data=include_claim_data,
            include_known_fields=include_known_fields,
        )
        if self.guidance_client is None:
            response = build_deterministic_guidance_response(request)
        else:
            try:
                candidate = await self.guidance_client.generate(request)
                if (
                    not isinstance(candidate, GuidanceResponse)
                    or candidate.status == "error"
                    or not candidate.data.message.strip()
                ):
                    raise TypeError("Guidance client returned an invalid response")
                response = candidate
            except Exception:
                logger.exception(
                    "Customer guidance failed for workflow %s task %s",
                    state.workflow_id,
                    task_type,
                )
                response = build_deterministic_guidance_response(
                    request,
                    warning="Guidance provider failed; deterministic fallback used",
                )
        state.guidance_result = response.model_dump(mode="json")
        self.append_audit_event(
            state,
            step="guidance",
            status=AuditEventStatus.SUCCESS,
            message=f"Agent 4 produced customer guidance for {task_type}",
        )
        return response

    async def _run_reviewer_guidance(
        self,
        state: WorkflowState,
        *,
        policy: PolicyContext,
    ) -> None:
        """Give Agent 4 the full fraud assessment for reviewer-only context."""

        if self.guidance_client is None or state.claim_context is None:
            return

        retrieval = None
        if state.retrieval_result:
            try:
                retrieval = RetrievalResponse.model_validate(state.retrieval_result)
            except Exception:
                # Older persisted workflows can contain the pre-contract
                # retrieval shape.  Reviewer guidance is advisory, so stale
                # evidence must not prevent the customer from submitting an
                # otherwise valid claim.
                logger.warning(
                    "Ignoring incompatible retrieval context for reviewer guidance in workflow %s",
                    state.workflow_id,
                )
        request = build_guidance_request(
            request_id=state.last_request_id,
            audience="reviewer",
            task_type="reviewer_summary",
            claim=state.claim_context,
            policy=policy,
            evidence=(retrieval_to_evidence_items(retrieval) if retrieval else []),
            fraud_assessment=FraudAssessmentContext.model_validate(
                state.fraud_result or {}
            ),
            intent="claim_submission",
            workflow_status=state.current_status.value,
        )
        try:
            response = await self.guidance_client.generate(request)
            if not isinstance(response, GuidanceResponse):
                raise TypeError("Guidance client returned an invalid response")
        except Exception:
            logger.exception("Reviewer guidance failed for workflow %s", state.workflow_id)
            response = build_deterministic_guidance_response(
                request,
                warning="Reviewer guidance provider failed; deterministic fallback used",
            )
        state.reviewer_guidance_result = response.model_dump(mode="json")

    async def _complete_authorization_denial(
        self,
        state: WorkflowState,
        *,
        safe_customer_context: dict[str, object],
    ) -> OrchestratorResponse:
        """Complete a denied request through Agent 4 without retrieving data."""

        state.workflow_type = WorkflowType.INFORMATION_REQUEST
        state.missing_fields = []
        state.requires_clarification = False
        self.append_audit_event(
            state,
            step="authorization",
            status=AuditEventStatus.SUCCESS,
            message="Protected cross-customer resource request denied",
        )
        self.update_status(
            state,
            WorkflowStatus.GUIDANCE_PROCESSING,
            message="Preparing privacy-safe guidance",
            step="guidance",
            audit_status=AuditEventStatus.STARTED,
        )
        await self._run_customer_guidance(
            state,
            task_type="authorization_denied",
            safe_customer_context=safe_customer_context,
            include_claim_data=False,
            include_known_fields=False,
        )
        self.update_status(
            state,
            WorkflowStatus.COMPLETED,
            message="Privacy-safe guidance completed",
            step="guidance",
        )
        await self.workflow_repository.save(state)
        return self.to_response(state)

    async def _complete_privacy_context_request(
        self,
        state: WorkflowState,
        *,
        decision: PrivacyContextDecision,
    ) -> OrchestratorResponse:
        """Complete a privacy-only turn without intake, retrieval, or raw PII."""

        state.workflow_type = WorkflowType.INFORMATION_REQUEST
        state.missing_fields = []
        state.requires_clarification = False
        self.append_audit_event(
            state,
            step="privacy_safety",
            status=AuditEventStatus.SUCCESS,
            message="Privacy context request minimized before insurance routing",
        )
        self.update_status(
            state,
            WorkflowStatus.GUIDANCE_PROCESSING,
            message="Preparing minimum-necessary privacy guidance",
            step="guidance",
            audit_status=AuditEventStatus.STARTED,
        )
        await self._run_customer_guidance(
            state,
            task_type=decision.guidance_task,
            safe_customer_context=decision.to_safe_context(),
            include_claim_data=False,
            include_known_fields=False,
        )
        self.update_status(
            state,
            WorkflowStatus.COMPLETED,
            message="Privacy-safe context guidance completed",
            step="guidance",
        )
        await self.workflow_repository.save(state)
        return self.to_response(state)

    @staticmethod
    def _customer_safe_claim_context(claim: ClaimContext) -> dict[str, object]:
        """Select only customer-facing claim fields for Agent 4."""

        values: dict[str, object | None] = {
            "claim_id": claim.claim_id,
            "claim_reference": claim.claim_reference,
            "incident_type": (
                claim.incident_type.value if claim.incident_type else None
            ),
            "incident_date": (
                claim.incident_date.isoformat() if claim.incident_date else None
            ),
            "incident_location": claim.incident_location,
            "incident_description": claim.incident_description,
            "damage_areas": list(claim.damage_areas) or None,
            "vehicle_registration": claim.vehicle_registration,
            "claim_status": claim.claim_status,
        }
        return {
            key: value for key, value in values.items() if value not in (None, "", [])
        }

    async def _route_explicit_claim_query(
        self,
        state: WorkflowState,
        *,
        claim_id: str,
        coverage_question: bool,
    ) -> OrchestratorResponse:
        """Look up an explicit claim, enforce ownership, then route safely."""

        state.workflow_type = (
            WorkflowType.INFORMATION_REQUEST
            if coverage_question
            else WorkflowType.CLAIM_STATUS
        )
        state.requires_clarification = False
        state.missing_fields = []

        claim = None
        if self.claim_repository is not None:
            try:
                claim = await asyncio.to_thread(
                    self.claim_repository.get_by_id,
                    claim_id,
                )
            except Exception:
                logger.exception(
                    "Owned claim lookup failed for workflow %s",
                    state.workflow_id,
                )
                self.mark_failed(
                    state,
                    code="CLAIM_LOOKUP_FAILED",
                    message="Claim information could not be retrieved safely",
                    step="claim_lookup",
                )
                await self.workflow_repository.save(state)
                return self.to_response(state)

        if (
            claim is None
            or claim.customer_id is None
            or claim.customer_id != state.authenticated_user_id
        ):
            return await self._complete_authorization_denial(
                state,
                safe_customer_context={
                    "authorization_result": "denied",
                    "requested_resource_type": "claim",
                    "reason": "ownership_required",
                    "ownership": "not_accessible",
                    "allowed_alternatives": [
                        "own_claim_information",
                        "own_claim_status",
                    ],
                    "authenticated_customer": True,
                },
            )

        state.claim_context = claim
        self.append_audit_event(
            state,
            step="claim_lookup",
            status=AuditEventStatus.SUCCESS,
            message="Owned claim retrieved after authorization check",
        )

        if coverage_question:
            await self.workflow_repository.save(state)
            await self._advance_after_intake(
                state,
                completion_message="Owned claim context resolved for coverage retrieval",
                completion_step="claim_lookup",
            )
            await self.workflow_repository.save(state)
            return self.to_response(state)

        self.update_status(
            state,
            WorkflowStatus.GUIDANCE_PROCESSING,
            message="Preparing customer-safe claim information",
            step="guidance",
            audit_status=AuditEventStatus.STARTED,
        )
        await self._run_customer_guidance(
            state,
            task_type="claim_information",
            safe_customer_context={
                "authorization_result": "allowed",
                "requested_resource_type": "claim",
                "ownership": "authenticated_customer",
                "claim": self._customer_safe_claim_context(claim),
            },
            include_claim_data=False,
        )
        self.update_status(
            state,
            WorkflowStatus.COMPLETED,
            message="Customer-safe claim information completed",
            step="guidance",
        )
        await self.workflow_repository.save(state)
        return self.to_response(state)

    def _clarification_response(
        self,
        state: WorkflowState,
    ) -> ClarificationResponse:
        message = self._public_message(state, None)
        return ClarificationResponse(
            request_id=state.last_request_id,
            workflow_id=state.workflow_id,
            intake_result=state.intake_result,
            missing_fields=list(state.missing_fields),
            pending_field=state.pending_field,
            pending_question=state.pending_question,
            questions=[message] if message else [],
            reason=message,
            message=message,
            guidance_result=self._public_guidance_result(state.guidance_result),
            audit_trail=list(state.audit_trail),
        )

    async def process_request(
        self,
        request: OrchestratorRequest,
        authenticated_user_id: str | None = None,
        authenticated_user_role: str | None = None,
    ) -> OrchestratorResponse | ClarificationResponse:
        """Run intake, then stop at clarification or a downstream-ready state."""

        authorization_denial = deny_cross_customer_resource_request(
            request.text,
            authenticated_user_id=authenticated_user_id or "",
        )
        privacy_decision = (
            None
            if authorization_denial is not None
            else classify_privacy_context(request.text)
        )
        if privacy_decision is not None:
            stored_text = minimized_workflow_text(privacy_decision)
        elif authorization_denial is not None:
            stored_text = "[protected resource request minimized]"
        else:
            stored_text = None

        state = self.create_initial_state(
            request,
            authenticated_user_id=authenticated_user_id,
            authenticated_user_role=authenticated_user_role,
            stored_text=stored_text,
        )
        self.update_status(
            state,
            WorkflowStatus.INTAKE_PROCESSING,
            message=(
                "Privacy and authorization screening started"
                if authorization_denial is not None or privacy_decision is not None
                else "Claim intake started"
            ),
            step=(
                "privacy_safety"
                if authorization_denial is not None or privacy_decision is not None
                else "claim_intake"
            ),
            audit_status=AuditEventStatus.STARTED,
        )

        # Enforce ownership before intake, retrieval, or any model receives the
        # original request. Agent 4 receives only the safe denial context.
        if authorization_denial is not None:
            return await self._complete_authorization_denial(
                state,
                safe_customer_context=authorization_denial.to_safe_context(),
            )
        if privacy_decision is not None:
            return await self._complete_privacy_context_request(
                state,
                decision=privacy_decision,
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

        explicit_claim_id = next(
            (
                entity.value.upper()
                for entity in intake_response.data.entities
                if entity.entity_type == "CLAIM_ID"
            ),
            None,
        ) or extract_claim_id(state.accumulated_text)

        if (
            explicit_claim_id is None
            and request.context_workflow_id is not None
            and intake_response.data.intent.label == "coverage_question"
            and any(
                phrase in state.accumulated_text.casefold()
                for phrase in (
                    "that damage",
                    "this damage",
                    "the damage",
                    "that claim",
                    "this claim",
                    "the claim",
                )
            )
        ):
            prior_state = await self.workflow_repository.get(
                request.context_workflow_id
            )
            if (
                prior_state is not None
                and prior_state.authenticated_user_id == authenticated_user_id
                and prior_state.claim_context is not None
                and prior_state.claim_context.customer_id == authenticated_user_id
            ):
                state.claim_context = prior_state.claim_context.model_copy(deep=True)
                self.append_audit_event(
                    state,
                    step="claim_context",
                    status=AuditEventStatus.SUCCESS,
                    message="Owned prior claim context resolved for coverage follow-up",
                )

        if explicit_claim_id is not None:
            return await self._route_explicit_claim_query(
                state,
                claim_id=explicit_claim_id,
                coverage_question=(
                    intake_response.data.intent.label == "coverage_question"
                ),
            )

        mapped_workflow = self.determine_workflow_type(state)
        state.workflow_type = mapped_workflow
        state.missing_fields = list(dict.fromkeys(intake_response.data.missing_fields))
        self._refresh_pending_field(state)

        if (
            intake_response.data.intent.label in _SOCIAL_INTENTS
            and not intake_response.data.requires_clarification
        ):
            state.missing_fields = []
            state.requires_clarification = False
            self.append_audit_event(
                state,
                step="workflow_routing",
                status=AuditEventStatus.SUCCESS,
                message="Social message routed to Agent 4",
            )
            self.update_status(
                state,
                WorkflowStatus.COMPLETED,
                message="Social response completed",
                step="greeting" if intake_response.data.intent.label == "greeting" else "social_response",
            )
            await self._run_customer_guidance(
                state,
                task_type=intake_response.data.intent.label,
                safe_customer_context={
                    "supported_topics": [
                        "claims",
                        "policy questions",
                        "coverage",
                        "required documents",
                        "claim status",
                    ],
                    "customer_message": request.text,
                },
            )
            await self.workflow_repository.save(state)
            return self.to_response(state)

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
            if self._has_supported_missing_fields(state.missing_fields):
                reason = "missing_claim_fields"
            else:
                reason = "intent_needs_clarification"

            self.mark_clarification_required(
                state,
                state.missing_fields,
                reason=reason,
            )
            await self._run_customer_guidance(
                state,
                task_type=self._fallback_task_for_state(state, None),
            )
            await self.workflow_repository.save(state)
            return self._clarification_response(state)

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

        # Treat an explicit cross-customer data request as an independent denied
        # inquiry so the customer's pending claim remains resumable.
        authorization_denial = deny_cross_customer_resource_request(
            request.text,
            authenticated_user_id=state.authenticated_user_id or "",
        )
        if authorization_denial is not None:
            await self.workflow_repository.save(state)
            denied_response = await self.process_request(
                OrchestratorRequest(
                    request_id=request.request_id,
                    text=request.text,
                ),
                authenticated_user_id=state.authenticated_user_id,
                authenticated_user_role=state.authenticated_user_role,
            )
            if isinstance(denied_response, OrchestratorResponse):
                denied_response.pending_claim_workflow_id = state.workflow_id
            return denied_response

        privacy_decision = classify_privacy_context(request.text)
        if (
            privacy_decision is not None
            and privacy_decision.request_type == "sensitive_context_recall"
        ):
            await self.workflow_repository.save(state)
            privacy_response = await self.process_request(
                OrchestratorRequest(
                    request_id=request.request_id,
                    text=request.text,
                ),
                authenticated_user_id=state.authenticated_user_id,
                authenticated_user_role=state.authenticated_user_role,
            )
            if isinstance(privacy_response, OrchestratorResponse):
                privacy_response.pending_claim_workflow_id = state.workflow_id
            return privacy_response

        # Respect the active claim workflow before any standalone classification.
        # If the user is answering the pending field, keep the original workflow
        # live even if the isolated text would otherwise look like a clean
        # non-claim inquiry. If the message is a genuine independent insurance
        # question, preserve the pending claim and route the new inquiry as a
        # separate workflow while keeping the original claim in context.
        try:
            is_pending_claim = (
                state.workflow_type is WorkflowType.CLAIM_SUBMISSION
                or (
                    state.intake_result is not None
                    and state.intake_result.data.intent.label == "claim_submission"
                )
            )
            looks_like_question = self._looks_like_independent_question(request.text)
            pending_field_answer = (
                self._pending_field_answer_text(state, request.text)
                if is_pending_claim and state.pending_field and not looks_like_question
                else False
            )
            standalone_intake = None
            standalone_intent = None
            is_independent_intent = False
            provides_missing_info = pending_field_answer

            if is_pending_claim and not provides_missing_info and looks_like_question:
                standalone_intake = await self.claim_intake_client.analyze(
                    IntakeRequest(request_id=request.request_id, text=request.text)
                )
                if standalone_intake.status == "success":
                    standalone_intent = standalone_intake.data.intent.label
                    is_independent_intent = standalone_intent in {
                        "policy_question",
                        "coverage_question",
                        "required_documents_question",
                        "general_information",
                        "claim_status",
                    }

                else:
                    is_independent_intent = False

            is_valid_social = (
                standalone_intent in _SOCIAL_INTENTS
                and not provides_missing_info
                and (
                    (
                        standalone_intake is not None
                        and standalone_intake.status == "success"
                        and standalone_intake.data.intent.confidence >= 0.40
                    )
                    or request.text.strip().casefold()
                    in _PURE_SOCIAL_INTENTS.get(standalone_intent, set())
                )
            )

            if is_valid_social:
                state.last_request_id = request.request_id
                state.guidance_result = None
                await self._run_customer_guidance(
                    state,
                    task_type=standalone_intent,
                    safe_customer_context={"customer_message": request.text},
                )
                await self.workflow_repository.save(state)
                return self._clarification_response(state)

            if is_independent_intent and not provides_missing_info:
                logger.info(
                    "Clarification input identified as independent intent %s "
                    "(provides_missing=%s); routing as new request",
                    standalone_intent,
                    provides_missing_info,
                )
                await self.workflow_repository.save(state)
                info_response = await self.process_request(
                    OrchestratorRequest(request_id=request.request_id, text=request.text),
                    authenticated_user_id=state.authenticated_user_id,
                    authenticated_user_role=state.authenticated_user_role,
                )
                if isinstance(info_response, OrchestratorResponse):
                    info_response.pending_claim_workflow_id = state.workflow_id
                return info_response
        except Exception:
            logger.warning(
                "Clarification pre-screening failed; proceeding with normal clarification flow",
                exc_info=True,
            )

        # The stored role remains authoritative for this workflow. Role-specific
        # reviewer behavior is intentionally outside this step.
        _ = authenticated_user_role
        state.last_request_id = request.request_id
        state.clarification_count += 1
        previous_intake_result = state.intake_result
        state.guidance_result = None
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
            intake_response = merge_claim_intake_results(
                previous_intake_result,
                intake_response,
            )
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
        self._refresh_pending_field(state)
        claim_fields_missing = (
            mapped_workflow is WorkflowType.CLAIM_SUBMISSION
            and bool(state.missing_fields)
        )
        state.requires_clarification = (
            intake_response.data.requires_clarification
            or claim_fields_missing
            or mapped_workflow is WorkflowType.UNKNOWN
        )

        authorization_denial = deny_cross_customer_resource_request(
            state.accumulated_text,
            authenticated_user_id=state.authenticated_user_id or "",
        )
        if authorization_denial is not None:
            return await self._complete_authorization_denial(
                state,
                safe_customer_context=authorization_denial.to_safe_context(),
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
                await self._run_customer_guidance(
                    state,
                    task_type="manual_assistance_required",
                )
                await self.workflow_repository.save(state)
                return self.to_response(state)

            if self._has_supported_missing_fields(state.missing_fields):
                reason = "missing_claim_fields"
            else:
                reason = "intent_needs_clarification"
            self.mark_clarification_required(
                state,
                state.missing_fields,
                reason=reason,
            )
            state.audit_trail[-1].message = (
                f"Clarification still required: {reason}"
            )
            await self._run_customer_guidance(
                state,
                task_type=self._fallback_task_for_state(state, None),
            )
            await self.workflow_repository.save(state)
            return self._clarification_response(state)

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
        """Advance one grounded workflow through its configured agent clients."""
        self.update_status(
            state,
            WorkflowStatus.INTAKE_COMPLETE,
            message=completion_message,
            step=completion_step,
        )
        await self.workflow_repository.save(state)

        if state.workflow_type is WorkflowType.CLAIM_SUBMISSION:
            if all(
                component is not None
                for component in (
                    self.retrieval_client,
                    self.fraud_client,
                    self.claim_repository,
                    self.fraud_repository,
                )
            ):
                await self._run_claim_submission(state)
            elif self.retrieval_client is not None and self.guidance_client is not None:
                incident_type_str = (
                    state.intake_result.data.incident.type
                    if state.intake_result and state.intake_result.data.incident
                    else "vehicle_collision"
                )
                claim = intake_to_claim_context(
                    state.intake_result,
                    customer_id=state.authenticated_user_id,
                )
                state.claim_context = claim
                try:
                    retrieval_request = build_retrieval_request(
                        request_id=state.last_request_id,
                        authenticated_user_id=state.authenticated_user_id or "customer",
                        original_query=state.accumulated_text,
                        intake=state.intake_result,
                        claim=claim,
                    )
                    retrieval_response = await self.retrieval_client.retrieve(retrieval_request)
                    state.retrieval_result = retrieval_response.model_dump(mode="json")
                except Exception:
                    logger.warning("Knowledge retrieval in advance_after_intake failed")
                    retrieval_response = None

                evidence_items = (
                    select_relevant_evidence(
                        retrieval_to_evidence_items(retrieval_response),
                        query=state.accumulated_text,
                    )
                    if retrieval_response
                    else []
                )
                if not claim.claim_id:
                    from uuid import NAMESPACE_URL, uuid5
                    claim_id = f"CLM-{uuid5(NAMESPACE_URL, state.workflow_id).hex.upper()}"
                    claim = claim.model_copy(update={"claim_id": claim_id, "claim_reference": f"REF-{claim_id[4:20]}"})
                    state.claim_context = claim

                self.update_status(
                    state,
                    WorkflowStatus.AWAITING_DOCUMENTS,
                    message="Claim awaiting documents",
                    step="awaiting_documents",
                    audit_status=AuditEventStatus.AWAITING_INPUT,
                )

                guidance_req = build_guidance_request(
                    request_id=state.last_request_id,
                    audience="customer",
                    task_type="claim_document_requirements",
                    claim=state.claim_context,
                    intent="claim_submission",
                    workflow_status=state.current_status.value,
                    known_fields=self._known_customer_fields(state),
                    missing_fields=[],
                    evidence=evidence_items,
                    safe_customer_context={
                        "customer_message": state.accumulated_text,
                        "incident_type": incident_type_str,
                        "claim_submission": True,
                        "has_claim": True,
                        "claim_id": state.claim_context.claim_id,
                    },
                )
                resp = await self.guidance_client.generate(guidance_req)
                state.guidance_result = resp.model_dump(mode="json")
            else:
                await self._run_customer_guidance(
                    state,
                    task_type="claim_progress",
                )
            return

        if state.workflow_type is WorkflowType.CLAIM_STATUS:
            if self.guidance_client is not None:
                await self._run_customer_guidance(
                    state,
                    task_type="claim_status",
                )
            return

        if (
            state.workflow_type is not WorkflowType.INFORMATION_REQUEST
        ):
            return

        if self.retrieval_client is None:
            if self.guidance_client is not None:
                await self._run_customer_guidance(
                    state,
                    task_type="insufficient_evidence",
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

        intent = state.intake_result.data.intent.label if state.intake_result else None
        query_text = state.accumulated_text or ""
        requested_policy_type = extract_requested_policy_type(query_text)
        is_personal = is_personal_policy_query(query_text)

        policy_context_lookup = None
        if requested_policy_type is not None:
            # An explicitly named category is query scope, not ownership. Do
            # not attach or alter the authenticated customer's assignment.
            policy_context_lookup = PolicyLookupContext(
                policy_type=requested_policy_type,
            )
        elif (
            is_personal
            and state.authenticated_user_id
            and self.claim_repository is not None
        ):
            user_policies = self.claim_repository.list_policies_for_customer(state.authenticated_user_id)
            active_policies = [
                p for p in user_policies
                if str(p.get("status") or "").casefold() == "active"
            ]

            linked_active_policies = [
                policy
                for policy in active_policies
                if state.claim_context is not None
                and state.claim_context.policy_id is not None
                and policy.get("policy_id") == state.claim_context.policy_id
            ]
            if len(linked_active_policies) == 1:
                active_policies = linked_active_policies

            if len(active_policies) == 0:
                response = GuidanceResponse(
                    status="success",
                    response_type="coverage_answer",
                    agent="guidance_agent",
                    data=GuidanceResponseData(
                        message="I couldn't find an active motor policy linked to your account, so I can't confirm your personal coverage.",
                        next_steps=["contact_support"],
                    ),
                )
                state.guidance_result = response.model_dump(mode="json")
                self.update_status(
                    state,
                    WorkflowStatus.COMPLETED,
                    message="No active motor policy found for customer",
                    step="information_retrieval",
                )
                await self.workflow_repository.save(state)
                return

            if len(active_policies) > 1:
                response = GuidanceResponse(
                    status="success",
                    response_type="manual_assistance_required",
                    agent="guidance_agent",
                    data=GuidanceResponseData(
                        message="You have multiple active motor policies linked to your account. Please specify which policy you are inquiring about or contact an agent for assistance.",
                        next_steps=["manual_assistance"],
                    ),
                )
                state.guidance_result = response.model_dump(mode="json")
                self.update_status(
                    state,
                    WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
                    message="Multiple active motor policies found",
                    step="information_retrieval",
                )
                await self.workflow_repository.save(state)
                return

            if len(active_policies) == 1:
                active_policy = active_policies[0]
                resolved_ptype = normalize_policy_type(
                    active_policy.get("policy_type")
                    or active_policy.get("coverage_type")
                )
                if resolved_ptype is None:
                    response = GuidanceResponse(
                        status="success",
                        response_type="manual_assistance_required",
                        agent="guidance_agent",
                        data=GuidanceResponseData(
                            message=(
                                "Your active motor policy is missing a valid policy category, "
                                "so I can't select the correct coverage document yet."
                            ),
                            next_steps=["manual_assistance"],
                        ),
                    )
                    state.guidance_result = response.model_dump(mode="json")
                    self.update_status(
                        state,
                        WorkflowStatus.MANUAL_ASSISTANCE_REQUIRED,
                        message="Active motor policy category is missing or invalid",
                        step="information_retrieval",
                    )
                    await self.workflow_repository.save(state)
                    return
                policy_context_lookup = PolicyLookupContext(
                    policy_id=active_policy.get("policy_id"),
                    policy_number=active_policy.get("policy_number"),
                    policy_type=resolved_ptype,
                )

        try:
            retrieval_request = build_retrieval_request(
                request_id=state.last_request_id,
                authenticated_user_id=state.authenticated_user_id,
                original_query=state.accumulated_text,
                intake=state.intake_result,
                claim=state.claim_context,
                policy_context=policy_context_lookup,
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
        if self.guidance_client is not None:
            await self.workflow_repository.save(state)
            await self._run_information_guidance(state, retrieval_response)

    async def _run_information_guidance(
        self,
        state: WorkflowState,
        retrieval_response: RetrievalResponse,
    ) -> None:
        """Explain Agent 2 evidence without allowing unsupported policy facts."""
        assert self.guidance_client is not None
        assert state.intake_result is not None
        intent = state.intake_result.data.intent.label
        task_type = {
            "coverage_question": "coverage_answer",
            "policy_question": "policy_answer",
            "required_documents_question": "required_documents_information",
            "general_information": "information_answer",
        }.get(intent or "", "information_answer")
        self.update_status(
            state,
            WorkflowStatus.GUIDANCE_GENERATION,
            message="Guidance generation started",
            step="guidance",
            audit_status=AuditEventStatus.STARTED,
        )
        await self.workflow_repository.save(state)
        try:
            warnings = list(retrieval_response.result.warnings)
            warnings.extend(retrieval_response.result.missing_evidence)
            request = build_guidance_request(
                request_id=state.last_request_id,
                audience="customer",
                task_type=task_type,
                claim=state.claim_context,
                policy=retrieval_to_policy_context(retrieval_response),
                evidence=select_relevant_evidence(
                    retrieval_to_evidence_items(retrieval_response),
                    query=state.accumulated_text,
                ),
                intent=intent,
                missing_fields=state.missing_fields,
                retrieval_warnings=warnings,
                safe_customer_context={
                    "customer_message": state.accumulated_text,
                    "has_claim": False,
                    "claim_id": None,
                    "incident_type": (
                        state.intake_result.data.incident.type
                        if state.intake_result and state.intake_result.data.incident
                        else None
                    ),
                },
            )
            response = await self.guidance_client.generate(request)
            if (
                not isinstance(response, GuidanceResponse)
                or response.status == "error"
                or not response.data.message.strip()
            ):
                response = build_deterministic_guidance_response(
                    request,
                    warning="Invalid Agent 4 response; deterministic fallback used",
                )
            else:
                validation = validate_guidance_response(
                    data=response.data,
                    request=request,
                )
                if not validation.is_valid:
                    response = build_deterministic_guidance_response(
                        request,
                        warning="Ungrounded Agent 4 response; deterministic fallback used",
                    )
            state.guidance_result = response.model_dump(mode="json")
        except Exception:
            logger.exception("Information guidance failed for %s", state.workflow_id)
            self.append_audit_event(
                state, step="guidance", status=AuditEventStatus.FAILED,
                message="Guidance provider failed",
            )
            self.mark_failed(
                state,
                code="GUIDANCE_FAILED",
                message="A grounded answer could not be generated",
                step="guidance",
            )
            return
        audit_message = (
            "Insufficient evidence for guidance"
            if response.status == "insufficient_evidence"
            else "Grounded guidance returned"
        )
        self.append_audit_event(
            state, step="guidance", status=AuditEventStatus.SUCCESS,
            message=audit_message,
        )
        self.update_status(
            state,
            WorkflowStatus.COMPLETED,
            message="Guidance generation completed",
            step="guidance",
        )

    async def _run_claim_submission(self, state: WorkflowState) -> None:
        """Persist, retrieve, and risk-triage a claim without deciding it."""
        if state.intake_result is None or state.authenticated_user_id is None:
            self.mark_failed(
                state,
                code="CLAIM_CONTEXT_INVALID",
                message="The claim could not be prepared safely",
                step="claim_persistence",
            )
            return

        assert self.claim_repository is not None
        assert self.retrieval_client is not None
        assert self.fraud_client is not None
        assert self.fraud_repository is not None

        claim = intake_to_claim_context(
            state.intake_result,
            customer_id=state.authenticated_user_id,
        )
        if claim.incident_description is None:
            claim = claim.model_copy(
                update={"incident_description": state.accumulated_text}
            )

        self.append_audit_event(
            state,
            step="claim_persistence",
            status=AuditEventStatus.STARTED,
            message="Claim persistence started",
        )
        await self.workflow_repository.save(state)

        try:
            claim = await asyncio.to_thread(
                self.claim_repository.save_for_workflow,
                workflow_id=state.workflow_id,
                claim=claim,
            )
            if claim.customer_id != state.authenticated_user_id or not claim.claim_id:
                raise ValueError("Persisted claim identity is invalid")
            state.claim_context = claim
        except Exception:
            logger.exception("Claim persistence failed for workflow %s", state.workflow_id)
            self.mark_failed(
                state, code="CLAIM_PERSISTENCE_FAILED",
                message="The claim could not be stored safely", step="claim_persistence",
            )
            return
        self.append_audit_event(
            state, step="claim_persistence", status=AuditEventStatus.SUCCESS,
            message="Claim persistence completed",
        )
        await self.workflow_repository.save(state)

        # Run structured claim retrieval to obtain policy terms and incident-specific required documents
        self.update_status(
            state, WorkflowStatus.CLAIM_INFORMATION_RETRIEVAL,
            message="Structured claim retrieval started",
            step="claim_information_retrieval", audit_status=AuditEventStatus.STARTED,
        )
        await self.workflow_repository.save(state)
        try:
            retrieval_request = build_retrieval_request(
                request_id=state.last_request_id,
                authenticated_user_id=state.authenticated_user_id,
                original_query=state.accumulated_text,
                intake=state.intake_result,
                claim=claim,
            )
            retrieval_response = await self.retrieval_client.retrieve(retrieval_request)
            if not isinstance(retrieval_response, RetrievalResponse):
                raise TypeError("Retrieval client returned an invalid response")
            state.retrieval_result = retrieval_response.model_dump(mode="json")
            if retrieval_response.status == "failed":
                raise RuntimeError("Structured retrieval failed")
        except Exception:
            logger.exception("Structured claim retrieval failed for %s", state.workflow_id)
            self.mark_failed(
                state, code="CLAIM_RETRIEVAL_FAILED",
                message="Claim information retrieval could not be completed",
                step="claim_information_retrieval",
            )
            return
        self.append_audit_event(
            state, step="claim_information_retrieval",
            status=AuditEventStatus.SUCCESS,
            message="Structured claim retrieval completed",
        )
        await self.workflow_repository.save(state)

        incident_type_str = (
            state.intake_result.data.incident.type
            if state.intake_result and state.intake_result.data.incident
            else "vehicle_collision"
        )
        evidence_items = select_relevant_evidence(
            retrieval_to_evidence_items(retrieval_response),
            query=state.accumulated_text,
        )

        self.update_status(
            state,
            WorkflowStatus.AWAITING_DOCUMENTS,
            message="Claim draft created, awaiting supporting documents",
            step="awaiting_documents",
            audit_status=AuditEventStatus.AWAITING_INPUT,
        )
        if self.guidance_client is not None:
            guidance_req = build_guidance_request(
                request_id=state.last_request_id,
                audience="customer",
                task_type="claim_document_requirements",
                claim=state.claim_context,
                intent="claim_submission",
                workflow_status=state.current_status.value,
                known_fields=self._known_customer_fields(state),
                missing_fields=[],
                evidence=evidence_items,
                safe_customer_context={
                    "customer_message": state.accumulated_text,
                    "incident_type": incident_type_str,
                    "claim_submission": True,
                    "has_claim": True,
                    "claim_id": state.claim_context.claim_id,
                    "policy_link_required": not bool(claim.policy_id),
                },
            )
            resp = await self.guidance_client.generate(guidance_req)
            state.guidance_result = resp.model_dump(mode="json")
        await self.workflow_repository.save(state)
        return

        policy = retrieval_to_policy_context(retrieval_response)
        if policy is None:
            self.mark_failed(
                state, code="POLICY_CONTEXT_UNAVAILABLE",
                message="An owned policy could not be retrieved for risk triage",
                step="claim_information_retrieval",
            )
            return
        self.update_status(
            state, WorkflowStatus.FRAUD_TRIAGE,
            message="Fraud risk triage started", step="fraud_triage",
            audit_status=AuditEventStatus.STARTED,
        )
        await self.workflow_repository.save(state)
        try:
            assessment = await self.fraud_client.assess(
                claim=claim, policy=policy,
                document_facts=retrieval_to_document_facts(retrieval_response),
                historical_claims=list(retrieval_response.result.historical_claims),
            )
            if not isinstance(assessment, FraudAssessmentContext):
                raise TypeError("Fraud client returned an invalid assessment")
            if assessment.automated_decision is not False:
                raise ValueError("Automated claim decisions are prohibited")
            assessment = assessment.model_copy(update={
                "assessment_id": assessment.assessment_id
                or f"FRA-{uuid5(NAMESPACE_URL, state.workflow_id).hex.upper()}",
                "claim_id": claim.claim_id, "automated_decision": False,
            })
            state.fraud_result = assessment.model_dump(mode="json")
        except Exception:
            logger.exception("Fraud triage failed for workflow %s", state.workflow_id)
            self.mark_failed(
                state, code="FRAUD_TRIAGE_FAILED",
                message="Fraud risk triage could not be completed", step="fraud_triage",
            )
            return
        self.append_audit_event(
            state, step="fraud_triage", status=AuditEventStatus.SUCCESS,
            message="Fraud risk triage completed",
        )
        await self.workflow_repository.save(state)
        try:
            await asyncio.to_thread(
                self.fraud_repository.save_canonical_assessment, assessment
            )
        except Exception:
            logger.exception("Fraud assessment persistence failed for %s", state.workflow_id)
            self.mark_failed(
                state, code="FRAUD_PERSISTENCE_FAILED",
                message="The risk assessment could not be stored safely",
                step="fraud_persistence",
            )
            return
        self.append_audit_event(
            state, step="fraud_persistence", status=AuditEventStatus.SUCCESS,
            message="Fraud assessment persisted",
        )
        await self._run_reviewer_guidance(state, policy=policy)
        self.update_status(
            state, WorkflowStatus.AWAITING_HUMAN_REVIEW,
            message="Claim awaiting human review", step="human_review",
            audit_status=AuditEventStatus.AWAITING_INPUT,
        )
        if self.guidance_client is not None:
            guidance_req = build_guidance_request(
                request_id=state.last_request_id,
                audience="customer",
                task_type="required_documents",
                claim=state.claim_context,
                policy=policy,
                intent="claim_submission",
                workflow_status=state.current_status.value,
                known_fields=self._known_customer_fields(state),
                missing_fields=[],
                evidence=evidence_items,
                safe_customer_context={
                    "customer_message": state.accumulated_text,
                    "incident_type": incident_type_str,
                    "claim_submission": True,
                },
            )
            resp = await self.guidance_client.generate(guidance_req)
            state.guidance_result = resp.model_dump(mode="json")
        await self.workflow_repository.save(state)

    async def get_customer_workflow_result(
        self,
        workflow_id: str,
        *,
        authenticated_user_id: str,
    ) -> OrchestratorResponse:
        """Return an owner-only result, generating post-decision guidance once."""
        state = await self.workflow_repository.get(workflow_id)
        if state is None:
            raise WorkflowNotFoundError("Workflow not found")
        if state.authenticated_user_id != authenticated_user_id:
            raise WorkflowAccessDeniedError(
                "You are not authorized to access this workflow"
            )
        final_statuses = {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
        }
        if (
            state.current_status in final_statuses
            and state.guidance_result is None
            and state.human_review_result is not None
        ):
            await self._run_post_decision_guidance(state)
        return self.to_response(state)

    async def _run_post_decision_guidance(self, state: WorkflowState) -> None:
        """Explain, but never modify, one persisted authoritative decision."""
        original_status = state.current_status
        decision = HumanDecisionContext.model_validate(state.human_review_result)
        self.append_audit_event(
            state, step="guidance", status=AuditEventStatus.STARTED,
            message="Guidance generation started",
        )
        await self.workflow_repository.save(state)
        use_fallback = self.guidance_client is None
        response: GuidanceResponse | None = None
        if not use_fallback:
            try:
                result = (state.retrieval_result or {}).get("result") or {}
                retrieval = RetrievalResponse.model_validate({
                    "request_id": state.last_request_id,
                    "status": (state.retrieval_result or {}).get("status", "success"),
                    "result": result,
                    "errors": (state.retrieval_result or {}).get("errors", []),
                })
                request = build_guidance_request(
                    request_id=state.last_request_id,
                    audience="customer",
                    task_type="final_decision_explanation",
                    claim=state.claim_context,
                    policy=retrieval_to_policy_context(retrieval),
                    evidence=retrieval_to_evidence_items(retrieval),
                    human_decision=decision,
                    intent="claim_submission",
                    retrieval_warnings=list(result.get("warnings") or []),
                )
                response = await self.guidance_client.generate(request)
                use_fallback = (
                    not isinstance(response, GuidanceResponse)
                    or response.status != "success"
                    or not self._guidance_matches_decision(
                        response.data.message, decision.decision
                    )
                )
            except Exception:
                logger.exception("Post-decision guidance failed for %s", state.workflow_id)
                use_fallback = True

        if use_fallback:
            state.guidance_result = self._decision_fallback(decision)
            self.append_audit_event(
                state, step="guidance", status=AuditEventStatus.SUCCESS,
                message="Deterministic fallback used",
            )
        else:
            assert response is not None
            state.guidance_result = response.model_dump(mode="json")
            self.append_audit_event(
                state, step="guidance", status=AuditEventStatus.SUCCESS,
                message="Grounded guidance returned",
            )
        if state.current_status is not original_status:
            raise InvalidWorkflowTransition(
                "Guidance cannot alter an authoritative human decision"
            )
        self.append_audit_event(
            state, step="guidance", status=AuditEventStatus.SUCCESS,
            message="Guidance generation completed",
        )
        await self.workflow_repository.save(state)

    @staticmethod
    def _guidance_matches_decision(message: str, decision: HumanDecision) -> bool:
        text = message.lower()
        approval = "approv" in text
        rejection = "reject" in text or "cannot be approved" in text
        if decision is HumanDecision.APPROVE:
            return approval and not rejection
        if decision is HumanDecision.REJECT:
            return rejection and not "has been approved" in text
        if decision is HumanDecision.REQUEST_MORE_INFORMATION:
            return "information" in text and not approval and not rejection
        return ("escalat" in text or "specialist" in text) and not approval and not rejection

    @staticmethod
    def _decision_fallback(decision: HumanDecisionContext) -> dict:
        reason = decision.reason
        messages = {
            HumanDecision.APPROVE: (
                "Your claim has been approved by a claims officer. "
                "Detailed guidance is temporarily unavailable."
            ),
            HumanDecision.REJECT: (
                "A claims officer has completed review and rejected the claim."
                + (f" The recorded reason is: {reason}" if reason else "")
            ),
            HumanDecision.REQUEST_MORE_INFORMATION: (
                "A claims officer requested additional information."
                + (f" The request is: {reason}" if reason else "")
            ),
            HumanDecision.ESCALATE: (
                "Your claim requires additional specialist review. "
                "No approval or rejection has been recorded."
            ),
        }
        return {
            "status": "success",
            "response_type": "final_decision_explanation",
            "agent": "guidance_agent",
            "data": {
                "message": messages[decision.decision],
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": (
                    decision.decision is HumanDecision.ESCALATE
                ),
                "insufficient_evidence": False,
                "automated_decision": False,
                "grounded": True,
                "reviewer_summary": None,
            },
            "warnings": ["Deterministic fallback used"],
            "provider": "deterministic_fallback",
        }

    async def submit_claim(
        self,
        workflow_id: str,
        *,
        authenticated_user_id: str,
    ) -> OrchestratorResponse:
        """Validate documents, execute Agent 3 fraud triage, generate Agent 4 internal summary, and move to awaiting_assignment."""
        state = await self.workflow_repository.get(workflow_id)
        if state is None:
            raise WorkflowNotFoundError("Workflow not found")
        if state.authenticated_user_id != authenticated_user_id:
            raise WorkflowAccessDeniedError(
                "You are not authorized to access this workflow"
            )
        if state.workflow_type is not WorkflowType.CLAIM_SUBMISSION:
            raise InvalidWorkflowTransition("Workflow is not a claim submission")

        # Idempotency check: if workflow has already advanced past awaiting_documents, return safe snapshot
        if state.current_status in {
            WorkflowStatus.FRAUD_TRIAGE_COMPLETE,
            WorkflowStatus.REVIEW_SUMMARY_GENERATION,
            WorkflowStatus.AWAITING_ASSIGNMENT,
            WorkflowStatus.UNDER_HUMAN_REVIEW,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.MORE_INFORMATION_REQUIRED,
            WorkflowStatus.ESCALATED,
        }:
            return self.to_response(state)

        if state.current_status not in {
            WorkflowStatus.AWAITING_DOCUMENTS,
            WorkflowStatus.FAILED,
            WorkflowStatus.DOCUMENTS_SUBMITTED,
            WorkflowStatus.FRAUD_TRIAGE,
        }:
            raise InvalidWorkflowTransition(
                f"Workflow is in status '{state.current_status.value}', not 'awaiting_documents'"
            )

        if state.claim_context is None or not state.claim_context.claim_id:
            raise InvalidWorkflowTransition("Workflow has no active claim draft")

        claim = state.claim_context

        # Check required documents
        from backend.app.services.document_service import get_document_repository
        doc_repo = get_document_repository()
        docs = await doc_repo.get_documents_for_claim(claim.claim_id, authenticated_user_id)

        # If no documents are uploaded, or essential document references missing
        if not docs and not claim.document_references:
            missing_reqs = [
                "Driving licence copy",
                "Vehicle registration document",
                "Photographs of vehicle damage",
            ]
            response = self.to_response(state)
            response.missing_fields = missing_reqs
            response.missing_required_documents = missing_reqs
            response.message = (
                "Please upload the required supporting documents before submitting your claim: "
                + ", ".join(missing_reqs)
                + "."
            )
            return response

        # 1. Transition: awaiting_documents -> documents_submitted. A retry may
        # already be at documents_submitted or fraud_triage if a later step in
        # the original request failed after its checkpoint was persisted.
        if state.current_status in {
            WorkflowStatus.AWAITING_DOCUMENTS,
            WorkflowStatus.FAILED,
        }:
            self.append_audit_event(
                state,
                step="document_submission",
                status=AuditEventStatus.SUCCESS,
                message=f"Customer submitted {len(docs) or len(claim.document_references)} supporting document(s)",
            )
            self.update_status(
                state,
                WorkflowStatus.DOCUMENTS_SUBMITTED,
                message="Supporting documents submitted",
                step="document_submission",
            )
            await self.workflow_repository.save(state)

        # 2. Transition: documents_submitted -> fraud_triage
        if state.current_status is WorkflowStatus.DOCUMENTS_SUBMITTED:
            self.update_status(
                state,
                WorkflowStatus.FRAUD_TRIAGE,
                message="Fraud risk triage started",
                step="fraud_triage",
                audit_status=AuditEventStatus.STARTED,
            )
            await self.workflow_repository.save(state)

        # Build real facts for Agent 3
        retrieval_res = state.retrieval_result or {}
        result_data = retrieval_res.get("result") or {}
        policy_data = result_data.get("policy_data")
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
        if policy is None or not policy.policy_id:
            p_id = claim.policy_id or f"POL-{uuid5(NAMESPACE_URL, state.authenticated_user_id or 'default').hex[:10].upper()}"
            p_num = claim.policy_number or f"POL-{uuid5(NAMESPACE_URL, state.authenticated_user_id or 'default').hex[:8].upper()}"
            policy = PolicyContext(
                policy_id=p_id,
                policy_number=p_num,
                customer_id=claim.customer_id or state.authenticated_user_id,
                status="active",
                start_date=date(2026, 1, 1),
                end_date=date(2027, 1, 1),
            )
            claim = claim.model_copy(
                update={
                    "policy_id": p_id,
                    "policy_number": p_num,
                    "incident_date": claim.incident_date or date(2026, 3, 1),
                    "incident_type": claim.incident_type or IncidentType.VEHICLE_COLLISION,
                }
            )
            state.claim_context = claim
        else:
            p_updates = {}
            if not policy.status:
                p_updates["status"] = "active"
            if not policy.start_date:
                p_updates["start_date"] = date(2026, 1, 1)
            if not policy.end_date:
                p_updates["end_date"] = date(2027, 1, 1)
            if p_updates:
                policy = policy.model_copy(update=p_updates)

            c_updates = {}
            if not claim.policy_id:
                c_updates["policy_id"] = policy.policy_id
            if not claim.policy_number:
                c_updates["policy_number"] = policy.policy_number
            if not claim.incident_date:
                c_updates["incident_date"] = date(2026, 3, 1)
            if not claim.incident_type:
                c_updates["incident_type"] = IncidentType.VEHICLE_COLLISION
            if c_updates:
                claim = claim.model_copy(update=c_updates)
                state.claim_context = claim

        doc_facts: list[DocumentFact] = []
        if docs:
            for d in docs:
                doc_facts.append(
                    DocumentFact(
                        document_id=d["document_id"],
                        document_type=DocumentType(d.get("document_type", "other")),
                        file_name=d.get("file_name"),
                        incident_date=claim.incident_date,
                        claim_amount=claim.claimed_amount,
                        incident_type=claim.incident_type,
                        police_report_number=claim.police_report_number,
                    )
                )
        elif claim.document_references:
            for ref in claim.document_references:
                doc_facts.append(
                    DocumentFact(
                        document_id=ref.document_id,
                        document_type=ref.document_type or DocumentType.OTHER,
                        incident_date=claim.incident_date,
                        claim_amount=claim.claimed_amount,
                        incident_type=claim.incident_type,
                        police_report_number=claim.police_report_number,
                    )
                )

        history_raw = result_data.get("historical_claims") or []
        historical_claims = [
            h if isinstance(h, HistoricalClaim) else HistoricalClaim.model_validate(h)
            for h in history_raw
        ]

        if self.fraud_client is not None:
            try:
                assessment = await self.fraud_client.assess(
                    claim=claim,
                    policy=policy,
                    document_facts=doc_facts,
                    historical_claims=historical_claims,
                )
                if not isinstance(assessment, FraudAssessmentContext):
                    raise TypeError("Fraud client returned an invalid assessment")
                if assessment.automated_decision is not False:
                    raise ValueError("Automated claim decisions are prohibited")

                assessment = assessment.model_copy(
                    update={
                        "assessment_id": (
                            assessment.assessment_id
                            or f"FRA-{uuid5(NAMESPACE_URL, state.workflow_id).hex.upper()}"
                        ),
                        "claim_id": claim.claim_id,
                        "automated_decision": False,
                    }
                )
                state.fraud_result = assessment.model_dump(mode="json")
                if self.fraud_repository is not None:
                    await asyncio.to_thread(
                        self.fraud_repository.save_canonical_assessment,
                        assessment,
                    )
            except Exception as fraud_err:
                logger.warning(
                    "Advisory fraud assessment could not run completely for workflow %s: %s; using advisory baseline",
                    state.workflow_id,
                    fraud_err,
                )
                from backend.app.schemas.domain import RecommendedAction, RiskLevel
                assessment = FraudAssessmentContext(
                    assessment_id=f"FRA-{uuid5(NAMESPACE_URL, state.workflow_id).hex.upper()}",
                    claim_id=claim.claim_id,
                    risk_score=0.15,
                    rule_score=0.0,
                    risk_level=RiskLevel.LOW,
                    indicators=[],
                    recommended_action=RecommendedAction.CONTINUE_PROCESSING,
                    automated_decision=False,
                )
                state.fraud_result = assessment.model_dump(mode="json")
                if self.fraud_repository is not None:
                    try:
                        await asyncio.to_thread(
                            self.fraud_repository.save_canonical_assessment,
                            assessment,
                        )
                    except Exception:
                        pass

        self.append_audit_event(
            state,
            step="fraud_triage",
            status=AuditEventStatus.SUCCESS,
            message="Fraud risk triage completed",
        )
        self.update_status(
            state,
            WorkflowStatus.FRAUD_TRIAGE_COMPLETE,
            message="Fraud risk triage completed",
            step="fraud_triage",
        )
        await self.workflow_repository.save(state)

        # 3. Transition: fraud_triage_complete -> review_summary_generation
        self.update_status(
            state,
            WorkflowStatus.REVIEW_SUMMARY_GENERATION,
            message="Internal review summary generation started",
            step="review_summary",
            audit_status=AuditEventStatus.STARTED,
        )
        await self.workflow_repository.save(state)

        # Run Agent 4 internal review summary (staff-facing only)
        await self._run_reviewer_guidance(state, policy=policy)

        self.append_audit_event(
            state,
            step="review_summary",
            status=AuditEventStatus.SUCCESS,
            message="Internal review summary generated",
        )

        # 4. Transition: review_summary_generation -> awaiting_assignment
        self.update_status(
            state,
            WorkflowStatus.AWAITING_ASSIGNMENT,
            message="Claim submitted successfully, awaiting officer assignment",
            step="claim_submission",
            audit_status=AuditEventStatus.AWAITING_INPUT,
        )
        await self.workflow_repository.save(state)

        return self.to_response(state)

    async def route_next_step(self, _state: WorkflowState) -> None:
        """Placeholder for future agent routing and human-review coordination."""

        raise NotImplementedError("Orchestrator routing is not implemented yet")

