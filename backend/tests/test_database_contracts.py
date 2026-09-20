"""Compatibility tests for canonical database and repository boundaries."""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.fraud.repository import FraudRepository
from backend.app.fraud.schemas import FraudAssessment, RiskIndicator
from backend.app.orchestrator.constants import WorkflowStatus, WorkflowType
from backend.app.orchestrator.supabase_workflow_repository import (
    SupabaseWorkflowRepository,
)
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.schemas.domain import (
    ClaimContext,
    DocumentFact,
    DocumentType,
    EvidenceItem,
    HumanDecision,
    HumanDecisionContext,
    IncidentType,
    PolicyContext,
    RecommendedAction,
    RiskLevel,
)
from backend.app.security.roles import UserRole
from backend.app.security.supabase_user_repository import SupabaseUserRepository
from backend.app.security.user_repository import UserRecord
from backend.app.graph.state import WorkflowState
from backend.app.services.domain_row_mappers import (
    claim_from_row,
    claim_to_row,
    document_fact_from_row,
    document_fact_to_row,
    evidence_from_knowledge_row,
    human_decision_from_row,
    human_decision_to_row,
    policy_from_row,
    policy_to_row,
)


SCHEMA = Path("backend/db/schema.sql").read_text(encoding="utf-8").lower()


class RecordingQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.selected = None
        self.inserted = None

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self.filters.append(("neq", column, value))
        return self

    def limit(self, _value):
        return self

    def insert(self, row):
        self.inserted = row
        return self

    def execute(self):
        self.client.last_query = self
        if self.inserted is not None:
            return SimpleNamespace(data=[self.inserted])
        return SimpleNamespace(data=self.client.rows.get(self.table, []))


class RecordingClient:
    def __init__(self, **rows):
        self.rows = rows
        self.last_query = None

    def table(self, table):
        return RecordingQuery(self, table)


def test_schema_declares_all_required_tables_without_data_deletion():
    tables = {
        "users", "workflows", "policies", "claims", "claim_documents",
        "fraud_assessments", "knowledge_chunks", "human_decisions",
    }
    for table in tables:
        assert f"create table if not exists public.{table}" in SCHEMA
    assert "drop table" not in SCHEMA
    assert "truncate " not in SCHEMA
    assert "delete from" not in SCHEMA


@pytest.mark.parametrize(
    "enum_type",
    [IncidentType, DocumentType, RiskLevel, RecommendedAction, HumanDecision,
     WorkflowType, WorkflowStatus, UserRole],
)
def test_schema_contains_every_controlled_domain_value(enum_type):
    for item in enum_type:
        assert f"'{item.value}'" in SCHEMA


def test_schema_uses_canonical_identifiers_and_timezone_columns():
    for column in ("policy_id", "claim_id", "document_id", "assessment_id", "chunk_id", "decision_id"):
        assert column in SCHEMA
    assert "timestamptz" in SCHEMA
    assert "ml_anomaly_score" not in SCHEMA
    assert "risk_indicators" not in SCHEMA


def test_user_row_serialization_uses_canonical_fields():
    user = UserRecord(
        user_id="USR-1", email="owner@example.com", password_hash="hash",
        role=UserRole.CUSTOMER, created_at=datetime.now(timezone.utc),
    )
    row = SupabaseUserRepository.user_to_row(user)
    assert set(row) == {"user_id", "email", "password_hash", "role", "created_at"}
    assert row["role"] == "customer"


def test_workflow_row_serialization_matches_schema_contract():
    state = WorkflowState(
        workflow_id="WF-1", request_id="REQ-1", last_request_id="REQ-1",
        raw_text="Help with my claim", original_text="Help with my claim",
        accumulated_text="Help with my claim", authenticated_user_id="USR-1",
        authenticated_user_role="customer",
    )
    row = SupabaseWorkflowRepository.state_to_row(state)
    expected = {
        "workflow_id", "request_id", "last_request_id", "raw_text",
        "original_text", "accumulated_text", "clarification_count",
            "authenticated_user_id", "authenticated_user_role", "intake_result",
            "claim_context",
        "retrieval_result", "fraud_result", "human_review_result",
            "guidance_result", "reviewer_guidance_result", "workflow_type",
            "current_status", "missing_fields",
        "requires_clarification", "errors", "audit_trail", "created_at",
        "updated_at",
    }
    assert set(row) == expected
    assert row["current_status"] == "received"


def test_policy_and_claim_rows_round_trip_without_ambiguous_ids():
    policy = PolicyContext(
        policy_id="POL-1", policy_number="MTR-1", customer_id="USR-1",
        status="active", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        coverage_details={"category": "motor"},
    )
    assert policy_from_row(policy_to_row(policy)) == policy
    claim = ClaimContext(
        claim_id="CLM-1", policy_id="POL-1", customer_id="USR-1",
        incident_type=IncidentType.VEHICLE_COLLISION,
        incident_date=date(2026, 9, 16), damage_areas=["left door"],
        claimed_amount=Decimal("1200.00"),
    )
    row = claim_to_row(claim)
    assert "id" not in row and "claim_type" not in row and "status" not in row
    assert claim_from_row(row) == claim


def test_document_human_decision_and_knowledge_row_mapping():
    fact = DocumentFact(
        document_id="DOC-1", document_type=DocumentType.POLICE_REPORT,
        incident_date=date(2026, 9, 16), metadata={"verified": False},
    )
    row = document_fact_to_row(fact, claim_id="CLM-1", customer_id="USR-1")
    assert row["document_id"] == "DOC-1"
    assert document_fact_from_row(row) == fact

    decision = HumanDecisionContext(
        decision=HumanDecision.REQUEST_MORE_INFORMATION,
        reviewer_id="USR-R", requested_information=["repair estimate"],
        decided_at=datetime.now(timezone.utc),
    )
    decision_row = human_decision_to_row(
        decision, decision_id="DEC-1", workflow_id="WF-1"
    )
    assert decision_row["workflow_id"] == "WF-1"
    restored_decision = human_decision_from_row(decision_row)
    assert restored_decision.decision == decision.decision
    assert restored_decision.reviewer_id == decision.reviewer_id
    assert restored_decision.decision_id == "DEC-1"
    assert restored_decision.workflow_id == "WF-1"

    evidence = evidence_from_knowledge_row({
        "chunk_id": "CHK-1", "source_title": "Claims guide",
        "section": "Documents", "content": "Submit supporting documents.",
        "score": 0.8, "metadata": {"page": 2},
    })
    assert evidence == EvidenceItem(
        evidence_id="CHK-1", source_title="Claims guide", section="Documents",
        content="Submit supporting documents.", score=0.8, metadata={"page": 2},
    )


def test_human_decision_rejects_missing_owner_and_naive_timestamp():
    decision = HumanDecisionContext(
        decision=HumanDecision.APPROVE, reviewer_id="USR-R",
        decided_at=datetime(2026, 9, 17),
    )
    with pytest.raises(ValueError, match="workflow_id or claim_id"):
        human_decision_to_row(decision, decision_id="DEC-1")
    with pytest.raises(ValueError, match="timezone"):
        human_decision_to_row(decision, decision_id="DEC-1", claim_id="CLM-1")


def test_retrieval_repository_parses_canonical_rows_and_filters_canonical_id():
    client = RecordingClient(policies=[{
        "policy_id": "POL-1", "policy_number": "MTR-1", "customer_id": "USR-1",
        "status": "active", "start_date": "2026-01-01", "end_date": "2026-12-31",
        "coverage_details": {},
    }])
    record = RetrievalRepository(client).get_policy_by_id("POL-1", "USR-1")
    assert record.policy_id == "POL-1"
    assert ("eq", "policy_id", "POL-1") in client.last_query.filters


def test_fraud_repository_translates_canonical_rows_and_payload_columns():
    client = RecordingClient(claims=[{
        "claim_id": "CLM-1", "claim_reference": "REF-1",
        "incident_type": "vehicle_collision", "incident_date": "2026-09-16",
        "claimed_amount": 1000, "claim_status": "submitted",
    }])
    repository = FraudRepository(client)
    history = repository.get_policy_claim_history("POL-1", "CLM-2")
    assert history[0]["id"] == "CLM-1"
    assert history[0]["claim_type"] == "vehicle_collision"
    assert ("neq", "claim_id", "CLM-2") in client.last_query.filters

    assessment = FraudAssessment(
        risk_level="low", risk_score=0.1, rule_score=0.1, ml_anomaly_score=0.2,
        risk_indicators=[RiskIndicator(
            rule_id="R1", severity="low", weight=5, title="Check",
            explanation="No material concern", evidence={},
        )], missing_documents=[], recommended_action="continue_processing",
    )
    row = repository.save_fraud_assessment("CLM-1", assessment)
    assert row["anomaly_score"] == 0.2
    assert "indicators" in row
    assert "ml_anomaly_score" not in row and "risk_indicators" not in row
