from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from backend.app.fraud.engine import FraudDetectionEngine
from backend.app.orchestrator.agent_clients import LocalFraudClient
from backend.app.retrieval.schemas import HistoricalClaim
from backend.app.schemas.domain import (
    ClaimContext,
    IncidentType,
    PolicyContext,
)


def _claim(amount=Decimal("50000")) -> ClaimContext:
    return ClaimContext(
        claim_id="CLM-CLIENT",
        claim_reference="REF-CLIENT",
        customer_id="USR-CLIENT",
        policy_id="POL-CLIENT",
        policy_number="MTR-CLIENT",
        incident_type=IncidentType.VEHICLE_COLLISION,
        incident_date=date.today(),
        incident_location="Kandy",
        incident_description="A collision damaged the vehicle.",
        claimed_amount=amount,
    )


def _policy(status="active") -> PolicyContext:
    return PolicyContext(
        policy_id="POL-CLIENT",
        policy_number="MTR-CLIENT",
        customer_id="USR-CLIENT",
        status=status,
        start_date="2026-01-01",
        end_date="2027-01-01",
    )


def test_local_fraud_client_is_async_and_returns_canonical_low_risk() -> None:
    result = asyncio.run(LocalFraudClient().assess(
        claim=_claim(), policy=_policy(), document_facts=[], historical_claims=[]
    ))
    assert result.risk_level.value in {"low", "medium"}
    assert 0 <= result.risk_score <= 1
    assert result.claim_id == "CLM-CLIENT"
    assert result.automated_decision is False


def test_local_fraud_client_preserves_high_risk_rule_indicators() -> None:
    result = asyncio.run(LocalFraudClient().assess(
        claim=_claim(Decimal("100000")),
        policy=_policy("expired"),
        document_facts=[],
        historical_claims=[
            HistoricalClaim(
                claim_id=f"OLD-{number}", claim_reference=f"REF-{number}",
                claim_type="motor_accident", incident_date=date.today().isoformat(),
                claimed_amount=100000,
            )
            for number in range(3)
        ],
    ))
    rule_ids = {item.rule_id for item in result.indicators}
    assert "POLICY_INACTIVE" in rule_ids
    assert "REPEATED_CLAIMS" in rule_ids
    assert result.automated_decision is False


def test_missing_amount_is_not_fabricated_and_ml_is_skipped() -> None:
    result = asyncio.run(LocalFraudClient().assess(
        claim=_claim(None), policy=_policy(), document_facts=[], historical_claims=[]
    ))
    assert result.anomaly_score is None
    assert result.model_version is None
    assert any("claimed amount missing" in item for item in result.warnings)
    assert result.automated_decision is False


class BrokenEngine:
    def evaluate(self, **_kwargs):
        raise RuntimeError("internal engine details")


def test_engine_failure_propagates_to_orchestrator_boundary() -> None:
    try:
        asyncio.run(LocalFraudClient(BrokenEngine()).assess(
            claim=_claim(), policy=_policy(), document_facts=[], historical_claims=[]
        ))
    except RuntimeError as error:
        assert str(error) == "internal engine details"
    else:
        raise AssertionError("Expected the client boundary to surface engine failure")


def test_production_model_loads_without_retraining() -> None:
    engine = FraudDetectionEngine()
    assert engine.anomaly_model.is_available()


def test_missing_model_falls_back_to_rules_with_warning() -> None:
    engine = FraudDetectionEngine()
    engine.anomaly_model.model = None
    result = asyncio.run(LocalFraudClient(engine).assess(
        claim=_claim(), policy=_policy(), document_facts=[], historical_claims=[]
    ))
    assert result.anomaly_score is None
    assert "ML anomaly model unavailable" in result.warnings
    assert result.automated_decision is False
