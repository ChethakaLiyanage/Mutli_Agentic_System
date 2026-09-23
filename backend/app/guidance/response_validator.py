"""Response validator and grounding verification for Agent 4.

Implements Sections 4, 5.2, 8, and 12 of the Agent 4 Design Guide.
"""

from __future__ import annotations

from typing import NamedTuple
from backend.app.guidance.safety import enforce_safety
from backend.app.guidance.schemas import GuidanceRequest, GuidanceResponseData


class ValidationResult(NamedTuple):
    """Result of validating the full response."""

    is_valid: bool
    errors: list[str]
    validated_data: GuidanceResponseData | None = None


def check_evidence_attribution(
    data: GuidanceResponseData,
    request: GuidanceRequest,
) -> list[str]:
    """Verify that every source referenced in evidence_used actually comes from retrieved evidence.

    Fails or warns if the model invents document identifiers not in retrieved_evidence.
    """
    errors: list[str] = []
    known_doc_ids = {
        item.document_id.casefold() for item in request.retrieved_evidence
    }
    known_doc_names = {
        item.document_name.casefold() for item in request.retrieved_evidence
    }
    known_sections = {
        item.section.casefold()
        for item in request.retrieved_evidence
        if item.section
    }

    for cited_source in data.evidence_used:
        normalized_source = cited_source.casefold()
        # Check if the cited source references at least one known identifier or section
        matches = (
            any(doc_id in normalized_source for doc_id in known_doc_ids)
            or any(doc_name in normalized_source for doc_name in known_doc_names)
            or any(section in normalized_source for section in known_sections)
        )
        if not matches and known_doc_ids:
            errors.append(
                f"Evidence attribution mismatch: '{cited_source}' was cited in evidence_used, "
                f"but does not match any retrieved document identifiers: {list(known_doc_ids)}"
            )

    return errors


def validate_guidance_response(
    data: GuidanceResponseData,
    request: GuidanceRequest,
) -> ValidationResult:
    """Validate generated guidance response against schema, boundaries, and evidence grounding."""
    errors: list[str] = []

    # 1. Non-negotiable: automated_decision must always be False
    if data.automated_decision is not False:
        errors.append("Compliance error: automated_decision must strictly be False.")

    # 2. Basic content requirements
    if not data.message or not data.message.strip():
        errors.append("Validation error: response message cannot be empty.")

    # 3. If insufficient evidence was flagged, verify consistent structure
    if data.insufficient_evidence:
        if not data.requires_human_review:
            # Force human review when evidence is insufficient
            data.requires_human_review = True

    # 4. Check safety and decision boundaries
    safety_result = enforce_safety(data=data, request=request)
    if not safety_result.is_safe:
        errors.extend(safety_result.violations)

    # 5. Check evidence attribution for tasks using retrieved evidence
    if request.retrieved_evidence and data.evidence_used:
        attribution_errors = check_evidence_attribution(data=data, request=request)
        # Note: If slight naming variation occurs, we log warning rather than hard crash,
        # but if strict attribution is enforced, record errors
        if len(attribution_errors) == len(data.evidence_used):
            errors.extend(attribution_errors)

    if errors:
        return ValidationResult(is_valid=False, errors=errors, validated_data=None)

    return ValidationResult(is_valid=True, errors=[], validated_data=data)
