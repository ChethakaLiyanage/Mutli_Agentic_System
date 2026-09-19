"""Deterministic customer-safe language owned by Agent 4."""

from __future__ import annotations

from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
)


_MISSING_FIELD_QUESTIONS = {
    "incident_type": "What happened to your vehicle?",
    "incident_date": "When did the incident happen?",
    "location": "Where did it happen?",
}


def _clarification_message(request: GuidanceRequest) -> str:
    missing = list(dict.fromkeys(request.missing_fields))
    known = request.known_fields
    questions = [
        _MISSING_FIELD_QUESTIONS[field]
        for field in missing
        if field in _MISSING_FIELD_QUESTIONS
    ]
    if not questions:
        return (
            "Could you clarify whether you want to submit a claim, ask about "
            "coverage, check required documents, or check a claim status?"
        )

    prefix = ""
    date_text = known.get("date_text") or known.get("incident_date")
    if missing == ["location"] and date_text:
        prefix = f"I've got that the accident happened {date_text}. "
    elif missing == ["location"] and known.get("incident_type"):
        prefix = "I've got the incident details. "

    if len(questions) == 1:
        return prefix + questions[0]
    return "I need a few more details: " + " ".join(questions)


def _claim_progress_message(request: GuidanceRequest) -> str:
    status = request.workflow_status
    location = request.known_fields.get("location")
    if status == "awaiting_human_review":
        prefix = f"Thanks, I've recorded {location} as the incident location. " if location else ""
        return prefix + "Your claim is now waiting for review by a claims officer."
    if status == "manual_assistance_required":
        if request.safe_customer_context.get("policy_link_required"):
            return (
                "Your claim details were saved, but a claims officer needs to "
                "link the correct motor policy before processing can continue."
            )
        return "A claims officer needs to help with the next step of your claim."
    if status in {"intake_complete", "claim_information_retrieval", "fraud_triage"}:
        if location:
            return (
                f"Thanks, I've recorded {location} as the incident location. "
                "I now have the main details needed to continue your claim."
            )
        return (
            "Thanks, I have the main incident details and your claim can now "
            "continue for review."
        )
    if status == "failed":
        return "I'm sorry, I couldn't continue this request safely. Please try again."
    return "Your request has been updated."


def _decision_message(request: GuidanceRequest) -> str:
    decision = request.human_decision
    if decision is None:
        return "A claims officer has not recorded a final decision yet."
    reason = decision.officer_notes
    if decision.decision == "approved":
        return "A claims officer reviewed and approved your claim."
    if decision.decision == "rejected":
        message = "A claims officer reviewed and rejected your claim."
        return message + (f" The recorded reason is: {reason}" if reason else "")
    if decision.decision == "info_requested":
        message = "A claims officer requested additional information."
        return message + (f" The request is: {reason}" if reason else "")
    return (
        "A claims officer escalated your claim for specialist review. "
        "No approval or rejection has been recorded."
    )


def build_deterministic_guidance_response(
    request: GuidanceRequest,
    *,
    warning: str | None = None,
) -> GuidanceResponse:
    """Return safe language without changing any authoritative input state."""

    if request.task_type == "greeting":
        message = (
            "Hi! I can help with claims, policy questions, coverage, required "
            "documents, or claim status. What can I help you with?"
        )
    elif request.task_type == "claim_submission_start":
        message = (
            "Yes, you can report a motor claim here. Tell me what happened to "
            "your vehicle, when it happened, and where it happened."
        )
    elif request.task_type == "clarification_question":
        message = _clarification_message(request)
    elif request.task_type in {"claim_progress", "awaiting_human_review"}:
        message = _claim_progress_message(request)
    elif request.task_type == "manual_assistance_required":
        message = _claim_progress_message(request)
    elif request.task_type in {"final_decision_explanation", "human_decision"}:
        message = _decision_message(request)
    elif request.task_type == "safe_error":
        message = "I'm sorry, I couldn't continue this request safely. Please try again."
    elif request.task_type == "insufficient_evidence":
        message = (
            "I couldn't find enough information in the available documents to "
            "answer that confidently."
        )
    elif request.retrieved_evidence:
        message = (
            "I found relevant controlled policy information, but I couldn't "
            "generate a fuller explanation right now. Please review the cited source."
        )
    else:
        message = (
            "I couldn't find enough controlled policy information to answer "
            "that reliably."
        )

    grounded = bool(
        request.retrieved_evidence
        or request.human_decision
        or request.workflow_status
        or request.known_fields
        or request.task_type in {"greeting", "claim_submission_start"}
    )
    return GuidanceResponse(
        status=(
            "insufficient_evidence"
            if request.task_type == "insufficient_evidence"
            else "success"
        ),
        response_type=request.task_type,
        data=GuidanceResponseData(
            message=message,
            next_steps=[],
            evidence_used=[],
            requires_human_review=(
                request.workflow_status == "awaiting_human_review"
                or (
                    request.human_decision is not None
                    and request.human_decision.decision == "escalated"
                )
            ),
            insufficient_evidence=(request.task_type == "insufficient_evidence"),
            automated_decision=False,
            grounded=grounded,
        ),
        warnings=[warning] if warning else [],
        provider="deterministic_fallback",
    )
