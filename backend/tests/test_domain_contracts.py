"""Contract tests for the canonical cross-agent integration boundary."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.app.fraud.schemas import FraudAssessment, RiskIndicator as FraudRiskIndicator
from backend.app.orchestrator.adapters import (
    build_guidance_request,
    canonical_to_fraud_inputs,
    fraud_to_canonical,
    intake_to_claim_context,
    retrieval_missing_evidence,
    retrieval_to_claim_context,
    retrieval_to_document_facts,
    retrieval_to_evidence_items,
    retrieval_to_policy_context,
)
from backend.app.retrieval.schemas import (
    ClaimRecord,
    DocumentEvidence,
    KnowledgeEvidence,
    PolicyRecord,
    RetrievalResponse,
    RetrievalResult,
)
from backend.app.schemas.domain import (
    ClaimContext,
    DocumentType,
    EvidenceItem,
    HumanDecision,
    HumanDecisionContext,
    IncidentType,
    PolicyContext,
    normalize_incident_type,
    to_legacy_fraud_claim_type,
)
from backend.app.schemas.intake import (
    DamageInformation,
    IncidentInformation,
    IntakeData,
    IntakeResponse,
    IntentResult,
)


def test_intake_response_maps_to_canonical_claim_without_inventing_values() -> None:
    intake = IntakeResponse(
        request_id="REQ-001",
        status="success",
        data=IntakeData(
            intent=IntentResult(label="claim_submission", confidence=0.91),
            incident=IncidentInformation(
                type="vehicle_collision",
                date_text="yesterday",
                normalized_date="2026-09-16",
                location="Kandy",
            ),
            damage=DamageInformation(areas=["left door", "rear bumper"]),
        ),
    )

    claim = intake_to_claim_context(intake, customer_id="USR-001")

    assert claim.customer_id == "USR-001"
    assert claim.incident_type is IncidentType.VEHICLE_COLLISION
    assert claim.incident_date.isoformat() == "2026-09-16"
    assert claim.incident_location == "Kandy"
    assert claim.damage_areas == ["left door", "rear bumper"]
    assert claim.claim_id is None
    assert claim.policy_number is None
    assert claim.claimed_amount is None
    assert claim.police_report_number is None


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_canonical_incident_types_round_trip(incident_type: IncidentType) -> None:
    assert normalize_incident_type(incident_type.value) is incident_type


def test_legacy_incident_types_use_explicit_central_mapping() -> None:
    assert normalize_incident_type("motor_accident") is IncidentType.VEHICLE_COLLISION
    assert normalize_incident_type("vehicle_theft") is IncidentType.THEFT_OR_BREAK_IN
    assert to_legacy_fraud_claim_type(IncidentType.VEHICLE_COLLISION) == "motor_accident"
    assert to_legacy_fraud_claim_type(IncidentType.THEFT_OR_BREAK_IN) == "vehicle_theft"
    with pytest.raises(ValueError, match="Unsupported incident type"):
        normalize_incident_type("unknown_incident")


def test_document_enum_accepts_every_current_retrieval_and_fraud_value() -> None:
    expected = {
        "police_report",
        "repair_estimate",
        "claim_form",
        "vehicle_registration",
        "damage_photo",
        "identity_document",
        "policy_document",
        "invoice",
        "photo",
        "policy_manual",
        "procedure_guide",
        "guideline",
        "manual",
        "other",
    }
    assert {item.value for item in DocumentType} == expected


def _retrieval_response() -> RetrievalResponse:
    return RetrievalResponse(
        request_id="REQ-RET-001",
        status="partial_success",
        result=RetrievalResult(
            policy_data=PolicyRecord(
                policy_id="POL-001",
                policy_number="MTR-001",
                customer_id="USR-001",
                status="active",
                start_date="2026-01-01",
                end_date="2026-12-31",
                coverage_details={"collision": True},
            ),
            claim_record=ClaimRecord(
                claim_id="CLM-001",
                claim_reference="CLM-REF-001",
                customer_id="USR-001",
                policy_id="POL-001",
                claim_type="motor_accident",
                incident_date="2026-09-16",
                incident_location="Kandy",
                claimed_amount=125000,
                status="under_review",
            ),
            document_facts=[
                DocumentEvidence(
                    document_id="DOC-001",
                    document_type="repair_estimate",
                    file_name="estimate.pdf",
                    incident_date="2026-09-16",
                    claim_amount=125000,
                    incident_type="vehicle_collision",
                )
            ],
            knowledge_evidence=[
                KnowledgeEvidence(
                    evidence_id="EVD-001",
                    source_id="SRC-001",
                    source_title="Motor Policy",
                    section=None,
                    document_type="policy_document",
                    content="Collision cover is subject to policy terms.",
                    relevance_score=0.88,
                    metadata={"page": 4},
                )
            ],
            missing_evidence=["police_report"],
        ),
    )


def test_retrieval_response_maps_to_canonical_contexts() -> None:
    response = _retrieval_response()

    policy = retrieval_to_policy_context(response)
    claim = retrieval_to_claim_context(response)
    documents = retrieval_to_document_facts(response)
    evidence = retrieval_to_evidence_items(response)

    assert policy is not None and policy.policy_id == "POL-001"
    assert policy.start_date.isoformat() == "2026-01-01"
    assert claim is not None and claim.incident_type is IncidentType.VEHICLE_COLLISION
    assert claim.claimed_amount == Decimal("125000.0")
    assert documents[0].document_type is DocumentType.REPAIR_ESTIMATE
    assert documents[0].claim_amount == Decimal("125000.0")
    assert evidence[0].evidence_id == "EVD-001"
    assert evidence[0].source_title == "Motor Policy"
    assert evidence[0].section is None
    assert evidence[0].content.startswith("Collision cover")
    assert evidence[0].score == 0.88
    assert evidence[0].metadata["source_id"] == "SRC-001"
    assert retrieval_missing_evidence(response) == ["police_report"]


def test_empty_retrieval_result_preserves_absence() -> None:
    response = RetrievalResponse(
        request_id="REQ-NONE",
        status="no_results",
        result=RetrievalResult(missing_evidence=["policy_not_found"]),
    )
    assert retrieval_to_policy_context(response) is None
    assert retrieval_to_claim_context(response) is None
    assert retrieval_to_document_facts(response) == []
    assert retrieval_to_evidence_items(response) == []


def test_fraud_assessment_maps_without_losing_rule_or_anomaly_details() -> None:
    assessment = FraudAssessment(
        risk_level="medium",
        risk_score=0.52,
        rule_score=0.45,
        ml_anomaly_score=0.72,
        risk_indicators=[
            FraudRiskIndicator(
                rule_id="DATE_CONFLICT",
                severity="high",
                weight=30,
                title="Incident-date inconsistency",
                explanation="Dates require verification.",
                evidence={"document_id": "DOC-001"},
            )
        ],
        missing_documents=["police_report"],
        recommended_action="manual_review",
        automated_decision=False,
        rules_version="1.0.0",
        model_version="isolation_forest_v1",
    )

    canonical = fraud_to_canonical(assessment)

    assert canonical.risk_level.value == "medium"
    assert canonical.risk_score == 0.52
    assert canonical.rule_score == 0.45
    assert canonical.anomaly_score == 0.72
    assert canonical.indicators[0].rule_id == "DATE_CONFLICT"
    assert canonical.missing_documents == [DocumentType.POLICE_REPORT]
    assert canonical.automated_decision is False


def test_missing_fraud_inputs_are_reported_instead_of_defaulted() -> None:
    with pytest.raises(ValueError, match="claim.claim_id") as error:
        canonical_to_fraud_inputs(
            ClaimContext(
                customer_id="USR-001",
                incident_type=IncidentType.VEHICLE_COLLISION,
            ),
            PolicyContext(customer_id="USR-001"),
        )
    assert "claim.incident_date" in str(error.value)
    assert "claim.claimed_amount" not in str(error.value)
    assert "policy.start_date" in str(error.value)


def test_complete_canonical_context_maps_to_fraud_engine_input() -> None:
    claim_data, policy_data = canonical_to_fraud_inputs(
        ClaimContext(
            claim_id="CLM-001",
            customer_id="USR-001",
            policy_id="POL-001",
            policy_number="MTR-001",
            incident_type=IncidentType.VEHICLE_COLLISION,
            incident_date="2026-09-16",
            incident_description="A bus collided with the insured vehicle.",
            claimed_amount=Decimal("125000"),
        ),
        PolicyContext(
            policy_id="POL-001",
            policy_number="MTR-001",
            customer_id="USR-001",
            status="active",
            start_date="2026-01-01",
            end_date="2026-12-31",
        ),
    )
    assert claim_data["claim_type"] == "motor_accident"
    assert claim_data["incident_date"].isoformat() == "2026-09-16"
    assert claim_data["claimed_amount"] == Decimal("125000")
    assert policy_data["status"] == "active"


def test_canonical_contexts_build_valid_guidance_request() -> None:
    claim = ClaimContext(
        customer_id="USR-001",
        incident_type=IncidentType.FLOOD_DAMAGE,
        incident_location="Colombo",
        claim_status="under_review",
    )
    policy = PolicyContext(policy_id="POL-001", policy_number="MTR-001")
    evidence = EvidenceItem(
        evidence_id="EVD-001",
        source_title="Motor Policy",
        section=None,
        content="Flood cover depends on the applicable policy schedule.",
        score=0.91,
    )
    human_decision = HumanDecisionContext(
        decision=HumanDecision.REQUEST_MORE_INFORMATION,
        reviewer_id="OFF-001",
        notes=None,
        decided_at=None,
        requested_information=["police report"],
    )

    request = build_guidance_request(
        request_id="REQ-GUIDE-001",
        audience="reviewer",
        task_type="reviewer_summary",
        claim=claim,
        policy=policy,
        evidence=[evidence],
        human_decision=human_decision,
        intent="claim_submission",
        missing_fields=["incident_date"],
    )

    assert request.claim_data is not None
    assert request.claim_data["incident_type"] == "flood_damage"
    assert request.claim_data["claimed_amount"] is None
    assert request.retrieved_evidence[0].document_id == "EVD-001"
    assert request.retrieved_evidence[0].section is None
    assert request.human_decision is not None
    assert request.human_decision.decision == "info_requested"
    assert request.human_decision.decision_date is None
    assert request.authorized_metadata["policy_context"]["policy_id"] == "POL-001"


def test_human_decision_timestamp_is_preserved_when_present() -> None:
    decided_at = datetime(2026, 9, 17, 10, 30, tzinfo=timezone.utc)
    request = build_guidance_request(
        request_id="REQ-GUIDE-002",
        audience="customer",
        task_type="final_decision_explanation",
        human_decision=HumanDecisionContext(
            decision=HumanDecision.APPROVE,
            reviewer_id="OFF-002",
            decided_at=decided_at,
        ),
    )
    assert request.human_decision is not None
    assert request.human_decision.decision_date.isoformat() == "2026-09-17"
