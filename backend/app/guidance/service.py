"""GuidanceService orchestrating the complete 10-step Agent 4 pipeline.

Implements Sections 4, 5, 7, 8, 12, and 13 of the Agent 4 Design Guide.
Enforces: IR retrieves first -> LLM explains second.
"""

from __future__ import annotations

import logging
from typing import Any
from backend.app.guidance.evidence_validator import validate_evidence
from backend.app.guidance.prompt_builder import build_prompt
from backend.app.guidance.response_validator import validate_guidance_response
from backend.app.guidance.safety import build_insufficient_evidence_fallback
from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
    ResponseStatus,
)
from backend.app.llm import BaseLLMClient, get_llm_client
from backend.app.services.audit_service import get_audit_service

logger = logging.getLogger(__name__)


class GuidanceService:
    """Core service implementing the internal controls of Agent 4."""

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.audit_service = get_audit_service()

    def process_request(self, request: GuidanceRequest) -> GuidanceResponse:
        """Execute the end-to-end Guidance Agent pipeline."""
        warnings: list[str] = []

        # 1. Pre-LLM Evidence Validation & Sufficiency check
        evidence_result = validate_evidence(request)
        if evidence_result.warning:
            warnings.append(evidence_result.warning)

        if not evidence_result.is_sufficient:
            fallback_data = build_insufficient_evidence_fallback(
                request=request,
                custom_reason=evidence_result.reason,
            )
            self._record_audit(request, fallback_data)
            evidence_warnings = list(warnings)
            if evidence_result.reason:
                evidence_warnings.append(
                    "The available policy material was insufficient for a reliable answer."
                    if request.audience == "customer"
                    else evidence_result.reason
                )
            return GuidanceResponse(
                status="insufficient_evidence",
                response_type=request.task_type,
                data=fallback_data,
                warnings=evidence_warnings,
                provider=getattr(self.llm_client.settings, "provider", "unknown"),
            )

        # Update request with sanitized evidence (injections neutralized)
        sanitized_request = request.model_copy(
            update={"retrieved_evidence": evidence_result.sanitized_evidence}
        )

        # 2. Prompt Building
        built_prompt = build_prompt(sanitized_request)

        # 3. LLM Generation
        raw_output: dict[str, Any]
        try:
            raw_output = self.llm_client.generate_json(
                system_instruction=built_prompt.system_instruction,
                user_prompt=built_prompt.user_prompt,
            )
        except Exception as err:
            logger.error("LLM generation failed for request %s: %s", request.request_id, err)
            fallback_data = GuidanceResponseData(
                message=(
                    "An error occurred while generating the explanation. "
                    "A claims officer will review your request directly."
                ),
                next_steps=["Wait for claims officer follow-up"],
                evidence_used=[],
                requires_human_review=True,
                insufficient_evidence=False,
                automated_decision=False,
            )
            self._record_audit(request, fallback_data)
            return GuidanceResponse(
                status="error",
                response_type=request.task_type,
                data=fallback_data,
                warnings=warnings + ["Guidance provider failed"],
                provider=getattr(self.llm_client.settings, "provider", "unknown"),
            )

        # 4. Parse Structured Output
        try:
            parsed_data = GuidanceResponseData.model_validate(raw_output)
        except Exception as parse_err:
            logger.warning(
                "LLM output did not strictly match GuidanceResponseData: %s. Raw: %s",
                parse_err,
                raw_output,
            )
            # Create safe fallback preserving raw text if possible
            msg = str(raw_output.get("message") or "Information processed; please consult with a claims officer.")
            parsed_data = GuidanceResponseData(
                message=msg,
                next_steps=raw_output.get("next_steps", []),
                evidence_used=raw_output.get("evidence_used", []),
                requires_human_review=True,
                insufficient_evidence=False,
                automated_decision=False,
            )

        # 5. Output Validation, Safety & Grounding Checks
        validation = validate_guidance_response(data=parsed_data, request=sanitized_request)
        if not validation.is_valid:
            logger.warning(
                "Safety/Response validation detected violations: %s. Applying safe boundary fallback.",
                validation.errors,
            )
            # If forbidden decision or fraud accusation occurred, replace with safe fallback
            safe_data = build_insufficient_evidence_fallback(
                request=sanitized_request,
                custom_reason="Safety guardrail triggered due to unauthorized decision or ungrounded statements.",
            )
            self._record_audit(request, safe_data)
            return GuidanceResponse(
                status="insufficient_evidence",
                response_type=request.task_type,
                data=safe_data,
                warnings=warnings + validation.errors,
                provider=getattr(self.llm_client.settings, "provider", "unknown"),
            )

        # 6. Audit Trail Recording
        final_data = (validation.validated_data or parsed_data).model_copy(
            update={
                "grounded": bool(sanitized_request.retrieved_evidence)
                or sanitized_request.human_decision is not None
            }
        )
        self._record_audit(request, final_data)

        return GuidanceResponse(
            status="success",
            response_type=request.task_type,
            data=final_data,
            warnings=warnings,
            provider=getattr(self.llm_client.settings, "provider", "unknown"),
        )

    def _record_audit(self, request: GuidanceRequest, data: GuidanceResponseData) -> None:
        """Helper to log audit event."""
        has_risk = bool(request.fraud_assessment and request.fraud_assessment.risk_indicators)
        human_dec = request.human_decision.decision if request.human_decision else None

        self.audit_service.record_event(
            request_id=request.request_id,
            audience=request.audience,
            task_type=request.task_type,
            model_name=getattr(self.llm_client.settings, "model_name", "unknown"),
            evidence_references=data.evidence_used,
            has_risk_indicators=has_risk,
            insufficient_evidence=data.insufficient_evidence,
            requires_human_review=data.requires_human_review,
            message=data.message,
            human_decision=human_dec,
        )
