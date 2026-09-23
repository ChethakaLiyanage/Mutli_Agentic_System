"""Pure adapters between existing agent schemas and canonical contracts."""

from __future__ import annotations

import re
from typing import Literal

from backend.app.fraud.schemas import FraudAssessment
from backend.app.guidance.schemas import (
    EvidenceItem as GuidanceEvidenceItem,
    FraudAssessmentContext as GuidanceFraudAssessmentContext,
    GuidanceRequest,
    GuidanceTaskType,
    HumanDecisionContext as GuidanceHumanDecisionContext,
    RiskIndicatorContext as GuidanceRiskIndicatorContext,
)
from backend.app.retrieval.schemas import (
    ClaimContext as RetrievalClaimContext,
    ClaimLookupContext,
    DocumentEvidence,
    DocumentReference as RetrievalDocumentReference,
    IntentContext,
    KnowledgeEvidence,
    PolicyLookupContext,
    RetrievalRequest,
    RetrievalResponse,
    UserContext,
)
from backend.app.schemas.domain import (
    ClaimContext,
    DocumentFact,
    DocumentType,
    EvidenceItem,
    FraudAssessmentContext,
    HumanDecision,
    HumanDecisionContext,
    PolicyContext,
    RiskIndicator,
    normalize_incident_type,
    to_legacy_fraud_claim_type,
)
from backend.app.schemas.intake import IntakeResponse


_CLAIM_REQUIRED_FIELDS = ("incident_type", "incident_date", "location")


def merge_claim_intake_results(
    previous: IntakeResponse | None,
    latest: IntakeResponse,
    *,
    confidence_threshold: float = 0.50,
) -> IntakeResponse:
    """Merge grounded claim facts across a clarification turn.

    The latest analysis is authoritative for newly supplied values, while
    previously grounded facts remain available when the customer answers with
    only one missing field.
    """

    if (
        previous is None
        or previous.status != "success"
        or latest.status != "success"
        or previous.data.intent.label != "claim_submission"
    ):
        return latest

    merged = latest.model_copy(deep=True)
    if latest.data.intent.label != "claim_submission":
        merged.data.intent = previous.data.intent.model_copy(deep=True)

    old_incident = previous.data.incident
    new_incident = merged.data.incident
    new_incident.type = new_incident.type or old_incident.type
    if (
        new_incident.date_text is None
        and new_incident.normalized_date is None
    ):
        new_incident.date_text = old_incident.date_text
        new_incident.normalized_date = old_incident.normalized_date
    new_incident.location = new_incident.location or old_incident.location

    merged.data.damage.areas = list(
        dict.fromkeys(previous.data.damage.areas + merged.data.damage.areas)
    )
    merged.data.damage.description = (
        merged.data.damage.description or previous.data.damage.description
    )

    entity_keys: set[tuple[str, str, int | None, int | None]] = set()
    merged_entities = []
    for entity in previous.data.entities + merged.data.entities:
        key = (entity.entity_type, entity.value, entity.start, entity.end)
        if key not in entity_keys:
            entity_keys.add(key)
            merged_entities.append(entity)
    merged.data.entities = merged_entities

    available = {
        "incident_type": bool(new_incident.type),
        "incident_date": bool(
            new_incident.date_text or new_incident.normalized_date
        ),
        "location": bool(new_incident.location),
    }
    has_grounded_claim_fact = any(available.values())
    if has_grounded_claim_fact:
        merged.data.missing_fields = [
            field for field in _CLAIM_REQUIRED_FIELDS if not available[field]
        ]
    else:
        # Preserve compatibility with remote/mock Agent 1 implementations that
        # communicate only their missing-field list and no structured facts.
        merged.data.missing_fields = list(
            dict.fromkeys(latest.data.missing_fields)
        )
    merged.data.requires_clarification = bool(
        merged.data.missing_fields
    ) or merged.data.intent.confidence < confidence_threshold
    return merged


def intake_to_claim_context(
    response: IntakeResponse,
    *,
    customer_id: str | None,
) -> ClaimContext:
    """Map grounded Agent 1 facts and separately trusted identity into a claim."""

    incident = response.data.incident
    damage = response.data.damage
    return ClaimContext(
        customer_id=customer_id,
        incident_type=normalize_incident_type(incident.type),
        incident_date=incident.normalized_date,
        incident_location=incident.location,
        incident_description=damage.description,
        damage_areas=list(damage.areas),
    )


def build_retrieval_request(
    *,
    request_id: str,
    authenticated_user_id: str,
    original_query: str,
    intake: IntakeResponse,
    claim: ClaimContext | None = None,
    policy_context: PolicyLookupContext | None = None,
) -> RetrievalRequest:
    """Create Agent 2 input without synthesizing unsupported identifiers."""
    intent = intake.data.intent.label
    if intent is None:
        raise ValueError("Retrieval requires a determined intake intent")
    claim = claim or intake_to_claim_context(
        intake, customer_id=authenticated_user_id
    )
    resolved_policy_context = policy_context or (
        PolicyLookupContext(
            policy_id=claim.policy_id, policy_number=claim.policy_number
        )
        if claim.policy_id or claim.policy_number
        else None
    )
    return RetrievalRequest(
        request_id=request_id,
        query=original_query,
        user_context=UserContext(user_id=authenticated_user_id),
        intent_context=IntentContext(
            intent=intent, confidence=intake.data.intent.confidence
        ),
        claim_context=RetrievalClaimContext(
            incident_type=(claim.incident_type.value if claim.incident_type else None),
            incident_date=(claim.incident_date.isoformat() if claim.incident_date else None),
            incident_location=claim.incident_location,
            damage_areas=list(claim.damage_areas),
        ),
        policy_context=resolved_policy_context,
        claim_lookup=(
            ClaimLookupContext(
                claim_id=claim.claim_id, claim_reference=claim.claim_reference
            )
            if claim.claim_id or claim.claim_reference
            else None
        ),
        document_references=[
            RetrievalDocumentReference(
                document_id=item.document_id,
                document_type=(item.document_type.value if item.document_type else None),
            )
            for item in claim.document_references
        ],
    )


def retrieval_to_policy_context(
    response: RetrievalResponse,
) -> PolicyContext | None:
    policy = response.result.policy_data
    if policy is None:
        return None
    return PolicyContext(
        policy_id=policy.policy_id,
        policy_number=policy.policy_number,
        customer_id=policy.customer_id,
        status=policy.status,
        coverage_type=policy.coverage_type,
        start_date=policy.start_date,
        end_date=policy.end_date,
        coverage_details=dict(policy.coverage_details),
    )


def retrieval_to_claim_context(
    response: RetrievalResponse,
) -> ClaimContext | None:
    claim = response.result.claim_record
    if claim is None:
        return None
    return ClaimContext(
        claim_id=claim.claim_id,
        claim_reference=claim.claim_reference,
        customer_id=claim.customer_id,
        policy_id=claim.policy_id,
        incident_type=normalize_incident_type(claim.claim_type),
        incident_date=claim.incident_date,
        incident_location=claim.incident_location,
        claimed_amount=claim.claimed_amount,
        claim_status=claim.status,
    )


def retrieval_document_to_fact(document: DocumentEvidence) -> DocumentFact:
    return DocumentFact(
        document_id=document.document_id,
        document_type=DocumentType(document.document_type),
        file_name=document.file_name,
        incident_date=document.incident_date,
        claim_amount=document.claim_amount,
        incident_type=normalize_incident_type(document.incident_type),
        police_report_number=document.police_report_number,
        extracted_text=document.extracted_text,
    )


def retrieval_to_document_facts(
    response: RetrievalResponse,
) -> list[DocumentFact]:
    return [
        retrieval_document_to_fact(document)
        for document in response.result.document_facts
    ]


def retrieval_evidence_to_canonical(
    evidence: KnowledgeEvidence,
) -> EvidenceItem:
    metadata = dict(evidence.metadata)
    metadata.setdefault("source_id", evidence.source_id)
    if evidence.document_type is not None:
        metadata.setdefault("document_type", evidence.document_type)
    return EvidenceItem(
        evidence_id=evidence.evidence_id,
        source_title=evidence.source_title,
        section=evidence.section,
        content=evidence.content,
        score=evidence.relevance_score,
        metadata=metadata,
    )


def retrieval_to_evidence_items(
    response: RetrievalResponse,
) -> list[EvidenceItem]:
    return [
        retrieval_evidence_to_canonical(item)
        for item in response.result.knowledge_evidence
    ]


def select_relevant_evidence(
    evidence: list[EvidenceItem],
    *,
    query: str,
    limit: int = 3,
) -> list[EvidenceItem]:
    """Keep the small set of evidence items most relevant to a customer turn.

    Agent 2 remains the retrieval authority. This pass filters out irrelevant
    chunks (e.g. windscreen chunks when asking about flood damage) so Agent 4
    narrates only genuinely relevant evidence.
    """

    if limit < 1:
        raise ValueError("limit must be at least 1")

    all_query_tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z]{3,}", query)
    }
    generic_scaffolding = {
        "about", "claim", "claims", "does", "have", "help", "insurance",
        "motor", "please", "tell", "that", "the", "what", "with", "would",
        "your", "can", "know", "policy", "cover", "coverage", "details",
        "information", "question", "comprehensive", "need", "give", "want",
        "much", "which", "when", "where", "how", "apply", "available",
    }
    topic_terms = all_query_tokens - generic_scaffolding

    def get_terms_overlap(item: EvidenceItem, terms: set[str]) -> int:
        if not terms:
            return 0
        searchable = " ".join(
            (item.source_title, item.section or "", item.content)
        ).casefold()
        return sum(term in searchable for term in terms)

    def rank(item: EvidenceItem) -> tuple[int, int, float]:
        topic_overlap = get_terms_overlap(item, topic_terms)
        generic_overlap = get_terms_overlap(item, all_query_tokens & generic_scaffolding)
        return topic_overlap, generic_overlap, item.score or 0.0

    ranked = sorted(evidence, key=rank, reverse=True)
    if not topic_terms:
        relevant = [item for item in ranked if rank(item)[1] > 0]
        return (relevant or ranked[:1])[:limit]

    topic_relevant = [item for item in ranked if rank(item)[0] > 0]
    if topic_relevant:
        return topic_relevant[:limit]

    return ranked[:1]


def retrieval_missing_evidence(response: RetrievalResponse) -> list[str]:
    """Preserve Retrieval's explicit missing-evidence signals for orchestration."""

    return list(response.result.missing_evidence)


def fraud_to_canonical(
    assessment: FraudAssessment,
    *,
    assessment_id: str | None = None,
    claim_id: str | None = None,
) -> FraudAssessmentContext:
    return FraudAssessmentContext(
        assessment_id=assessment_id,
        claim_id=claim_id,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        indicators=[
            RiskIndicator(
                rule_id=item.rule_id,
                severity=item.severity,
                weight=item.weight,
                title=item.title,
                explanation=item.explanation,
                evidence=dict(item.evidence),
            )
            for item in assessment.risk_indicators
        ],
        recommended_action=assessment.recommended_action,
        missing_documents=[DocumentType(item) for item in assessment.missing_documents],
        rule_score=assessment.rule_score,
        anomaly_score=assessment.ml_anomaly_score,
        automated_decision=assessment.automated_decision,
        rules_version=assessment.rules_version,
        model_version=assessment.model_version,
        warnings=list(assessment.warnings),
    )


def canonical_to_fraud_inputs(
    claim: ClaimContext,
    policy: PolicyContext,
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate and map canonical contexts to the tested fraud-engine inputs.

    Missing required facts are reported together. No dates, identifiers,
    descriptions, or monetary amounts are synthesized.
    """

    policy_id = claim.policy_id or policy.policy_id
    policy_number = claim.policy_number or policy.policy_number
    customer_id = claim.customer_id or policy.customer_id
    required_claim_values = {
        "claim_id": claim.claim_id,
        "policy_id": policy_id,
        "customer_id": customer_id,
        "policy_number": policy_number,
        "incident_type": claim.incident_type,
        "incident_date": claim.incident_date,
    }
    required_policy_values = {
        "policy_id": policy.policy_id,
        "policy_number": policy.policy_number,
        "customer_id": policy.customer_id,
        "status": policy.status,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
    }
    missing = [
        f"claim.{name}"
        for name, value in required_claim_values.items()
        if value is None
    ]
    missing.extend(
        f"policy.{name}"
        for name, value in required_policy_values.items()
        if value is None
    )
    if missing:
        raise ValueError(
            "Fraud evaluation requires missing fields: " + ", ".join(missing)
        )
    if claim.customer_id and policy.customer_id != claim.customer_id:
        raise ValueError("Claim and policy customer identities do not match")
    if claim.policy_id and policy.policy_id != claim.policy_id:
        raise ValueError("Claim and policy identifiers do not match")
    if claim.policy_number and policy.policy_number != claim.policy_number:
        raise ValueError("Claim and policy numbers do not match")

    assert claim.incident_type is not None
    claim_data: dict[str, object] = {
        "claim_id": claim.claim_id,
        "policy_id": policy_id,
        "customer_id": customer_id,
        "policy_number": policy_number,
        "claim_type": to_legacy_fraud_claim_type(claim.incident_type),
        "incident_date": claim.incident_date,
        "incident_location": claim.incident_location,
        "claimed_amount": claim.claimed_amount,
        "incident_description": claim.incident_description,
        "police_report_number": claim.police_report_number,
    }
    policy_data: dict[str, object] = {
        "policy_id": policy.policy_id,
        "policy_number": policy.policy_number,
        "customer_id": policy.customer_id,
        "status": policy.status,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
        "coverage_details": dict(policy.coverage_details),
    }
    return claim_data, policy_data


def canonical_evidence_to_guidance(
    evidence: EvidenceItem,
) -> GuidanceEvidenceItem:
    return GuidanceEvidenceItem(
        document_id=evidence.evidence_id,
        document_name=evidence.source_title,
        section=evidence.section,
        content=evidence.content,
        relevance_score=evidence.score,
    )


def _fraud_to_guidance(
    assessment: FraudAssessmentContext | None,
) -> GuidanceFraudAssessmentContext | None:
    if assessment is None:
        return None
    return GuidanceFraudAssessmentContext(
        risk_level=assessment.risk_level.value,
        risk_score=assessment.risk_score,
        rule_score=assessment.rule_score,
        ml_anomaly_score=assessment.anomaly_score,
        risk_indicators=[
            GuidanceRiskIndicatorContext(
                rule_id=item.rule_id,
                severity=item.severity.value,
                weight=item.weight,
                title=item.title,
                explanation=item.explanation,
                evidence=dict(item.evidence),
            )
            for item in assessment.indicators
        ],
        missing_documents=[item.value for item in assessment.missing_documents],
        recommended_action=assessment.recommended_action.value,
        automated_decision=assessment.automated_decision,
        rules_version=assessment.rules_version,
        model_version=assessment.model_version,
    )


def _human_decision_to_guidance(
    decision: HumanDecisionContext | None,
) -> GuidanceHumanDecisionContext | None:
    if decision is None:
        return None
    decision_mapping = {
        HumanDecision.APPROVE: "approved",
        HumanDecision.REJECT: "rejected",
        HumanDecision.REQUEST_MORE_INFORMATION: "info_requested",
        HumanDecision.ESCALATE: "escalated",
    }
    return GuidanceHumanDecisionContext(
        decision=decision_mapping[decision.decision],
        officer_id=None,
        officer_notes=decision.reason,
        decision_date=(decision.decided_at.date() if decision.decided_at else None),
        settlement_amount=decision.settlement_amount,
    )


def build_guidance_request(
    *,
    request_id: str,
    audience: Literal["customer", "reviewer"],
    task_type: GuidanceTaskType,
    claim: ClaimContext | None = None,
    policy: PolicyContext | None = None,
    evidence: list[EvidenceItem] | None = None,
    fraud_assessment: FraudAssessmentContext | None = None,
    human_decision: HumanDecisionContext | None = None,
    intent: str | None = None,
    workflow_status: str | None = None,
    known_fields: dict[str, object] | None = None,
    safe_customer_context: dict[str, object] | None = None,
    missing_fields: list[str] | None = None,
    retrieval_warnings: list[str] | None = None,
) -> GuidanceRequest:
    """Build Agent 4 input without executing Guidance or inventing absent facts."""

    claim_data = claim.model_dump(mode="json") if claim is not None else None
    authorized_metadata = (
        {"policy_context": policy.model_dump(mode="json")}
        if policy is not None
        else {}
    )
    guidance_fraud = (
        _fraud_to_guidance(fraud_assessment)
        if audience == "reviewer"
        else None
    )
    return GuidanceRequest(
        request_id=request_id,
        audience=audience,
        task_type=task_type,
        intent=intent,
        workflow_status=workflow_status,
        known_fields=dict(known_fields or {}),
        safe_customer_context=dict(safe_customer_context or {}),
        claim_data=claim_data,
        retrieved_evidence=[
            canonical_evidence_to_guidance(item) for item in (evidence or [])
        ],
        fraud_assessment=guidance_fraud,
        missing_documents=(
            [item.value for item in fraud_assessment.missing_documents]
            if fraud_assessment is not None
            else []
        ),
        missing_fields=list(missing_fields or []),
        claim_status=claim.claim_status if claim is not None else None,
        human_decision=_human_decision_to_guidance(human_decision),
        authorized_metadata=authorized_metadata,
        retrieval_warnings=list(retrieval_warnings or []),
    )
