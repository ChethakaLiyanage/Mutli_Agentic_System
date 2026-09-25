"""Deterministic customer-safe language owned by Agent 4."""

from __future__ import annotations

from backend.app.core.time import get_time_aware_greeting
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
    """Return a natural, timezone-aware greeting with dynamic phrasing."""
    salutation = get_time_aware_greeting(user_text)
    variations = [
        f"{salutation} How can I help with your motor insurance claims or questions today?",
        f"{salutation} What can I assist you with regarding your policy or claims?",
        f"{salutation} I'm here to help with your insurance questions or claims. What's on your mind?",
        f"Hello! {salutation} How may I assist you with your motor insurance questions or claims today?",
    ]
    idx = (len(user_text or "") + int(get_time_aware_greeting(user_text).count("!"))) % len(variations)
    return variations[idx]


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
    context = request.safe_customer_context
    safe_status = context.get("customer_safe_status")
    event = context.get("event")
    if safe_status == "documents_required":
        return "Your claim draft still needs the required supporting documents before it can be submitted."
    if safe_status in {"submitted", "processing", "awaiting_officer_assignment"}:
        prefix = "Your claim has been submitted successfully. " if event == "claim_submitted" else "Your claim is submitted. "
        return prefix + "No action is needed from you now; it is waiting to be assigned to a claims officer."
    if safe_status == "awaiting_officer_review":
        return "Your claim is waiting for a claims officer to review it. No action is needed from you right now."
    if safe_status == "under_officer_review":
        return "A claims officer is reviewing your claim. No action is needed from you right now."
    if safe_status == "more_information_required":
        return "A claims officer needs more information before the review can continue. Please provide the requested information."
    if safe_status == "additional_review":
        return "Your claim needs additional specialist review. No approval or rejection has been recorded."
    if safe_status == "approved":
        return "A claims officer has approved your claim."
    if safe_status == "rejected":
        return "A claims officer has rejected your claim."

    status = request.workflow_status
    location = request.known_fields.get("location")
    if status in {"awaiting_human_review", "awaiting_assignment", "under_human_review", "documents_submitted", "fraud_triage_complete", "review_summary_generation"}:
        return "Your claim has been submitted successfully and is waiting for review."
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


def _claim_information_message(request: GuidanceRequest) -> str:
    claim = request.safe_customer_context.get("claim")
    if not isinstance(claim, dict):
        return "I couldn't retrieve accessible claim information for this request."

    labels = (
        ("claim_id", "Claim ID"),
        ("claim_reference", "Claim reference"),
        ("incident_type", "Incident type"),
        ("incident_date", "Incident date"),
        ("incident_time", "Incident time"),
        ("incident_location", "Incident location"),
        ("incident_description", "Incident description"),
        ("damage_areas", "Damage"),
        ("vehicle_registration", "Vehicle registration"),
        ("claim_status", "Claim status"),
    )
    details: list[str] = []
    for key, label in labels:
        value = claim.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item).replace("_", " ") for item in value)
        elif key in {"incident_type", "claim_status"}:
            value = str(value).replace("_", " ")
        details.append(f"{label}: {value}")
    return "Here is the claim information available on your account:\n" + "\n".join(
        f"- {item}" for item in details
    )


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


def _reviewer_summary_message(request: GuidanceRequest) -> str:
    claim = request.claim_data or {}
    incident = claim.get("incident_type") or "Not specified"
    date_val = claim.get("incident_date") or "Not specified"
    loc = claim.get("incident_location") or "Not specified"
    desc = claim.get("incident_description") or ""
    damage = claim.get("damage_areas") or []
    damage_str = ", ".join(damage) if damage else "Not specified"

    fraud = request.fraud_assessment
    risk_level = (fraud.risk_level if hasattr(fraud, "risk_level") else "Unknown") if fraud else "Unknown"
    if hasattr(risk_level, "value"):
        risk_level = risk_level.value
    indicators = [ind.title for ind in (fraud.indicators if fraud else [])]
    ind_str = ", ".join(indicators) if indicators else "None"

    return (
        "Claim Review Summary\n\n"
        f"Incident:\nCustomer reported {incident} on {date_val} in {loc}.\n"
        + (f"Description: {desc}\n" if desc else "")
        + f"\nReported Damage:\n- {damage_str}\n\n"
        "Fraud Triage:\n"
        f"Automated fraud triage classified the case as {risk_level} risk.\n"
        f"Relevant indicators: {ind_str}\n\n"
        "Important:\n"
        "This assessment is advisory only. No automated claim decision has been made.\n\n"
        "Human Action:\n"
        "A claims officer must review the claim and make the final decision."
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
    elif request.task_type == "sensitive_context_recall":
        message = (
            "I avoid reproducing a collection of personal or identifying details. "
            "I use customer information only when it is relevant to the insurance "
            "task you are working on. I can still help with your current request, "
            "your own policy information, or your own claim information."
        )
    elif request.task_type == "sensitive_context_notice":
        message = (
            "I will use personal details only when they are relevant to a specific "
            "insurance task, without repeating them unnecessarily. Tell me whether "
            "you want help with a claim, your policy, or another motor-insurance question."
        )
    elif request.task_type == "authorization_denied":
        resource_type = request.safe_customer_context.get(
            "requested_resource_type", "information"
        )
        own_resource = {
            "policy": "your own policy and coverage",
            "claim": "your own claim and its status",
            "claim_documents": "your own claim and submitted documents",
            "personal_information": "information linked to your own account",
            "customer_information": "your own account, policy, or claim information",
        }.get(str(resource_type), "information linked to your own account")
        if request.safe_customer_context.get("ownership") == "not_accessible":
            message = (
                "I can't provide information for that record because customer "
                f"information is private. I can help you with {own_resource} instead."
            )
        else:
            message = (
                "I can't provide protected information belonging to another customer. "
                f"I can help you with {own_resource} instead."
            )
    elif request.task_type == "claim_information":
        message = _claim_information_message(request)
    elif request.task_type in {
        "final_decision_explanation",
        "final_claim_decision",
        "human_decision",
    }:
        message = _decision_message(request)
    elif request.task_type in {
        "reviewer_summary",
        "internal_claim_review_summary",
    }:
        message = _reviewer_summary_message(request)

    elif request.task_type == "safe_error":
        message = "I'm sorry, I couldn't continue this request safely. Please try again."
    elif request.task_type == "insufficient_evidence":
        message = (
            "I couldn't find enough information in the available documents to "
            "answer that confidently."
        )
    elif request.task_type == "coverage_answer":
        grounded_sections = []
        for item in request.retrieved_evidence[:3]:
            content = " ".join(item.content.split())
            if content:
                label = item.section or item.document_name
                grounded_sections.append(f"{label}: {content}")
        if "specific_policy_not_available" in request.retrieval_warnings:
            message = (
                "This is general policy information and does not confirm coverage "
                "under your specific policy.\n\n" + "\n\n".join(grounded_sections)
            )
        else:
            message = (
                "Your active policy document contains the following relevant coverage terms:\n\n"
                + "\n\n".join(grounded_sections)
                + "\n\nCoverage remains subject to the policy's conditions, exclusions, excess, and endorsements."
                if grounded_sections
                else "I couldn't find grounded coverage terms in the active policy document."
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
        top_item = request.retrieved_evidence[0]
        clean_title = (top_item.document_name or "Official Policy Documentation").replace("_", " ").title()
        message = (
            f"Relevant controlled policy information from the active documentation ({clean_title}):\n\n"
            f"{top_item.content}"
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
    summary_sec = None
    if request.task_type in {"reviewer_summary", "internal_claim_review_summary"}:
        claim = request.claim_data or {}
        incident = claim.get("incident_type") or "Not specified"
        date_val = claim.get("incident_date") or "Not specified"
        fraud = request.fraud_assessment
        obs = [ind.title for ind in (fraud.indicators if fraud else [])]
        summary_sec = ReviewerSummarySection(
            claim_overview=f"Reported {incident} on {date_val}",
            policy_findings=[],
            risk_observations=obs,
            missing_items=[
                item.value if hasattr(item, "value") else str(item)
                for item in (fraud.missing_documents if fraud else [])
            ],
            reviewer_action_points=["Claims officer review required"],
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
                request.workflow_status in {"awaiting_human_review", "under_human_review", "awaiting_assignment"}
                or (
                    request.human_decision is not None
                    and request.human_decision.decision == "escalated"
                )
            ),
            insufficient_evidence=(request.task_type == "insufficient_evidence"),
            automated_decision=False,
            grounded=grounded,
            reviewer_summary=summary_sec,
        ),
        warnings=[warning] if warning else [],
        provider="deterministic_fallback",
    )

