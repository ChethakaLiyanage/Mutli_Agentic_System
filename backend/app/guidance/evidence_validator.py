"""Evidence validator and pre-LLM sufficiency checks for Agent 4.

Implements Sections 4, 7.4, 11.4, and 11.5 of the Agent 4 Design Guide.
Enforces the core design principle: IR retrieves first -> LLM explains second.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from backend.app.guidance.schemas import EvidenceItem, GuidanceRequest, GuidanceTaskType


# Tasks that strictly require authoritative evidence from retrieval
EVIDENCE_REQUIRING_TASKS: set[GuidanceTaskType] = {
    "coverage_explanation",
    "policy_explanation",
    "required_documents",
}

# Suspicious prompt injection patterns that may be embedded in documents or inputs
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:an?\s+)?(?:admin|root|developer|jailbroken)", re.IGNORECASE),
    re.compile(r"system\s+prompt\s*:\s*", re.IGNORECASE),
    re.compile(r"disregard\s+(?:the\s+)?(?:rules|policy|safety)", re.IGNORECASE),
    re.compile(r"approve\s+(?:this\s+)?claim\s+immediately", re.IGNORECASE),
    re.compile(r"bypass\s+(?:human|security|reviewer|check)", re.IGNORECASE),
]


class EvidenceValidationResult(NamedTuple):
    """Outcome of pre-LLM evidence validation."""

    is_sufficient: bool
    reason: str | None = None
    sanitized_evidence: list[EvidenceItem] = []
    injection_detected: bool = False
    warning: str | None = None


def sanitize_text(text: str) -> tuple[str, bool]:
    """Sanitize retrieved or user text by neutralizing potential prompt injections."""
    has_injection = False
    sanitized = text

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sanitized):
            has_injection = True
            sanitized = pattern.sub("[UNTRUSTED_CONTENT_FILTERED]", sanitized)

    return sanitized, has_injection


def validate_evidence(request: GuidanceRequest) -> EvidenceValidationResult:
    """Validate whether the request contains sufficient trusted evidence to proceed to the LLM.

    If a task strictly requires retrieval evidence (e.g. coverage or policy clauses)
    and none is supplied, short-circuits immediately to prevent LLM hallucinations.
    """
    task = request.task_type
    evidence_items = request.retrieved_evidence

    # Check if task requires policy evidence
    if task in EVIDENCE_REQUIRING_TASKS:
        if not evidence_items:
            return EvidenceValidationResult(
                is_sufficient=False,
                reason=(
                    f"Task '{task}' requires retrieved policy evidence, but none was provided. "
                    "Short-circuiting to safe insufficient-evidence response."
                ),
                sanitized_evidence=[],
                injection_detected=False,
            )

        # Check that evidence items contain actual text content
        has_usable_content = any(item.content and item.content.strip() for item in evidence_items)
        if not has_usable_content:
            return EvidenceValidationResult(
                is_sufficient=False,
                reason="Retrieved evidence items contain no usable text content.",
                sanitized_evidence=[],
                injection_detected=False,
            )

    # Sanitize each evidence item to prevent prompt injection from document text
    sanitized_items: list[EvidenceItem] = []
    any_injection = False

    for item in evidence_items:
        clean_content, injection_found = sanitize_text(item.content)
        if injection_found:
            any_injection = True

        sanitized_items.append(
            EvidenceItem(
                document_id=item.document_id,
                document_name=item.document_name,
                section=item.section,
                content=clean_content,
                relevance_score=item.relevance_score,
            )
        )

    warning = (
        "Security warning: Suspicious prompt-injection instructions detected in retrieved evidence and neutralized."
        if any_injection
        else None
    )

    return EvidenceValidationResult(
        is_sufficient=True,
        reason=None,
        sanitized_evidence=sanitized_items,
        injection_detected=any_injection,
        warning=warning,
    )
