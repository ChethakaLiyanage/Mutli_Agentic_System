"""Audit logging service for Agent 4 operations.

Implements Sections 6.2, 7.3, and Phase 13 of the Agent 4 Design Guide.
Records model parameters, prompt version, evidence references, output metadata, and PII masking.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0.0"

_POLICY_NUM_PATTERN = re.compile(r"\b(POL|MOT|CLM)[-_]?[A-Z0-9]{4,10}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"\b(?:\+?94|0)?7[0-9]{8}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def mask_pii(text: str) -> str:
    """Mask sensitive PII identifiers (policy numbers, phones, emails) in audit logs."""
    if not text:
        return text

    masked = _POLICY_NUM_PATTERN.sub(lambda m: m.group(0)[:3] + "****", text)
    masked = _PHONE_PATTERN.sub("07********", masked)
    masked = _EMAIL_PATTERN.sub("****@***.***", masked)
    return masked


class AuditRecord(BaseModel):
    """Structured audit trail record for an Agent 4 execution."""

    audit_id: str
    request_id: str
    audience: str
    task_type: str
    model_name: str
    prompt_version: str = PROMPT_VERSION
    evidence_references: list[str] = Field(default_factory=list)
    has_risk_indicators: bool = False
    insufficient_evidence: bool = False
    requires_human_review: bool = False
    automated_decision: bool = False
    human_decision_recorded: str | None = None
    sanitized_response_summary: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AuditService:
    """Service for recording immutable audit events for Agent 4."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record_event(
        self,
        request_id: str,
        audience: str,
        task_type: str,
        model_name: str,
        evidence_references: list[str],
        has_risk_indicators: bool,
        insufficient_evidence: bool,
        requires_human_review: bool,
        message: str,
        human_decision: str | None = None,
    ) -> AuditRecord:
        """Create and store a masked audit event."""
        import uuid

        masked_summary = mask_pii(message[:200]) + ("..." if len(message) > 200 else "")

        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            request_id=request_id,
            audience=audience,
            task_type=task_type,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            evidence_references=evidence_references,
            has_risk_indicators=has_risk_indicators,
            insufficient_evidence=insufficient_evidence,
            requires_human_review=requires_human_review,
            automated_decision=False,
            human_decision_recorded=human_decision,
            sanitized_response_summary=masked_summary,
        )

        self._records.append(record)
        logger.info(
            "Agent 4 Audit Event: request_id=%s audience=%s task=%s insufficient_evidence=%s",
            request_id,
            audience,
            task_type,
            insufficient_evidence,
        )
        return record

    def get_records(self, request_id: str | None = None) -> list[AuditRecord]:
        """Retrieve recorded audit events."""
        if request_id:
            return [r for r in self._records if r.request_id == request_id]
        return list(self._records)


_audit_service_instance: AuditService | None = None


def get_audit_service() -> AuditService:
    """Singleton getter for AuditService."""
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService()
    return _audit_service_instance
