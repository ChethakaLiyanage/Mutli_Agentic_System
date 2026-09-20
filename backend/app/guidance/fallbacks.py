"""Deterministic customer-safe language owned by Agent 4."""

from __future__ import annotations

from datetime import datetime

from backend.app.guidance.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    GuidanceResponseData,
)


def _format_friendly_incident_type(incident_type: str | None) -> str:
    if not incident_type:
        return "motor insurance incident"
    raw = str(incident_type).replace("_", " ").lower().strip()
    mapping = {
        "vehicle collision": "vehicle collision",
        "collision": "vehicle collision",
        "theft or break in": "vehicle theft or break-in",
        "theft": "vehicle theft",
        "flood damage": "flood damage",
        "flood": "flood damage",
        "windscreen damage": "windscreen damage",
        "windscreen": "windscreen damage",
        "vandalism or malicious damage": "vandalism",
        "fire damage": "fire damage",
        "animal strike": "animal collision",
        "weather damage": "weather damage",
    }
    return mapping.get(raw, raw)


def _get_time_aware_greeting(user_text: str | None = None) -> str:
    """Return a natural, time-aware or time-matched greeting."""
    if user_text:
        lowered = user_text.casefold()
        if "good afternoon" in lowered:
            return "Good afternoon! How can I help with your motor insurance today?"
        if "good evening" in lowered:
            return "Good evening! How can I help with your motor insurance today?"
        if "good morning" in lowered:
            return "Good morning! How can I help with your motor insurance today?"

    current_hour = datetime.now().hour
    if 4 <= current_hour < 12:
        salutation = "Good morning!"
    elif 12 <= current_hour < 17:
        salutation = "Good afternoon!"
    else:
        salutation = "Good evening!"
    return f"{salutation} How can I help with your motor insurance today?"


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
        user_text = None
        if request.safe_customer_context:
            user_text = request.safe_customer_context.get("customer_message")
        message = _get_time_aware_greeting(user_text)
    elif request.task_type == "thanks":
        message = "You're welcome! Let me know if you need anything else."
    elif request.task_type == "goodbye":
        message = "Goodbye! Take care."
    elif request.task_type == "acknowledgement":
        message = "Sure. What would you like to do next?"
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
    elif request.task_type == "coverage_answer":
        evidence_text = " ".join(item.content for item in request.retrieved_evidence).casefold()
        if "flood" in evidence_text or "water" in evidence_text:
            message = (
                "Some comprehensive motor policies may cover accidental flood or water-ingress "
                "damage. However, coverage depends on your specific policy terms, exclusions, "
                "excess, and endorsements, so the general guidance alone cannot confirm "
                "whether your own policy covers it."
            )
        elif "windscreen" in evidence_text or "glass" in evidence_text:
            message = (
                "Windscreen and window glass damage is often covered under comprehensive motor "
                "policies, subject to specific excess and repair conditions. Please refer to "
                "your policy schedule for exact limits."
            )
        else:
            message = (
                "Coverage depends on your specific policy terms, exclusions, and endorsements. "
                "Please check your policy schedule or contact a claims officer to verify "
                "your individual cover."
            )
    elif request.task_type == "policy_answer":
        evidence_text = " ".join(item.content for item in request.retrieved_evidence).casefold()
        if "exclusion" in evidence_text or "deliberate" in evidence_text:
            message = (
                "Common exclusions may include loss outside the policy period, use of the "
                "vehicle outside permitted conditions, intentional damage, certain unauthorized "
                "commercial use, driving without the required legal authorization, and some "
                "mechanical or electrical failures. Exact exclusions depend on the customer's "
                "actual policy wording."
            )
        else:
            message = (
                "Policy terms, excesses, and limits are set out in your policy schedule. "
                "Please review the relevant section or contact support for assistance with your wording."
            )
    elif request.task_type in {"required_documents_information", "required_documents"} and not (request.safe_customer_context or {}).get("has_claim"):
        evidence_text = " ".join(item.content for item in request.retrieved_evidence)
        possible_docs = [
            "Completed claim form",
            "Police report or police reference",
            "Vehicle registration document",
            "Driving licence copy",
            "Repair estimate",
            "Photographs of vehicle damage",
            "Information about keys",
        ]
        supported = [
            doc for doc in possible_docs
            if any(w in evidence_text.lower() for w in doc.lower().split()[:2])
        ]
        docs = supported or possible_docs[:5]
        doc_bullets = "\n".join(f"- {d}" for d in docs)

        raw_incident = (
            (request.safe_customer_context or {}).get("incident_type")
            or (request.known_fields or {}).get("incident_type")
        )
        if raw_incident:
            friendly_incident = _format_friendly_incident_type(str(raw_incident))
            message = (
                f"For a {friendly_incident} claim, the documents required depend on the terms of your policy. "
                f"According to the available claim information, the following documents may be required:\n\n{doc_bullets}\n\n"
                "If you want to submit a claim, tell me what happened to your vehicle, when it happened, and where it happened."
            )
        else:
            message = (
                f"For a motor claim, the documents required depend on the type of incident and your policy. "
                f"According to the available claim information, the following documents may be required:\n\n{doc_bullets}\n\n"
                "If you want to submit a claim, tell me what happened to your vehicle, when it happened, and where it happened."
            )
    elif request.task_type in {"claim_document_requirements", "required_documents"}:
        evidence_text = " ".join(item.content for item in request.retrieved_evidence)
        possible_docs = [
            "Completed claim form",
            "Police report or police reference",
            "Vehicle registration document",
            "Driving licence copy",
            "Repair estimate",
            "Photographs of vehicle damage",
            "Information about keys",
        ]
        supported = [
            doc for doc in possible_docs
            if any(w in evidence_text.lower() for w in doc.lower().split()[:2])
        ]
        docs = supported or possible_docs[:5]
        doc_bullets = "\n".join(f"- {d}" for d in docs)

        raw_incident = (
            (request.safe_customer_context or {}).get("incident_type")
            or (request.known_fields or {}).get("incident_type")
            or ((request.claim_data or {}).get("incident_type"))
        )
        friendly_incident = _format_friendly_incident_type(str(raw_incident)) if raw_incident else "vehicle collision"
        message = (
            f"According to the details you provided, this appears to be a {friendly_incident}. "
            f"If you want to make a claim, we need the following documents:\n\n{doc_bullets}\n\n"
            "Please upload these documents using the button below so our claims team can process your claim."
        )
    elif request.retrieved_evidence:
        message = (
            "I found relevant controlled policy information, but I couldn't "
            "generate a fuller explanation right now. Please review the cited source."
        )
    else:
        message = (
            "I am an AI assistant specialized in motor insurance claims, policy questions, "
            "coverage details, and required documents. I don't have information on that topic, "
            "but please let me know if you have any questions related to motor insurance!"
        )

    grounded = bool(
        request.retrieved_evidence
        or request.human_decision
        or request.workflow_status
        or request.known_fields
        or request.task_type in {
            "greeting", "thanks", "goodbye", "acknowledgement",
            "claim_submission_start", "information_answer",
        }
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
