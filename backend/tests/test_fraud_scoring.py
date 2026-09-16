from app.fraud.schemas import RiskIndicator
from app.fraud.scoring import (
    calculate_rule_score,
    get_recommended_action,
    get_risk_level,
)


def test_rule_score_is_normalized():
    indicators = [
        RiskIndicator(
            rule_id="DATE_CONFLICT",
            severity="high",
            weight=30,
            title="Date conflict",
            explanation="Dates differ.",
        ),
        RiskIndicator(
            rule_id="DUPLICATE_CLAIM",
            severity="high",
            weight=35,
            title="Duplicate claim",
            explanation="Similar claim exists.",
        ),
    ]

    assert calculate_rule_score(indicators) == 0.65


def test_score_is_capped_at_one():
    indicators = [
        RiskIndicator(
            rule_id="TEST_1",
            severity="high",
            weight=70,
            title="Test",
            explanation="Test rule.",
        ),
        RiskIndicator(
            rule_id="TEST_2",
            severity="high",
            weight=70,
            title="Test",
            explanation="Test rule.",
        ),
    ]

    assert calculate_rule_score(indicators) == 1.0


def test_risk_level():
    assert get_risk_level(0.10) == "low"
    assert get_risk_level(0.35) == "medium"
    assert get_risk_level(0.70) == "high"


def test_recommended_action():
    assert (
        get_recommended_action("high", [])
        == "escalate"
    )

    assert (
        get_recommended_action("medium", [])
        == "manual_review"
    )

    assert (
        get_recommended_action(
            "low",
            ["repair_estimate"],
        )
        == "request_documents"
    )

    assert (
        get_recommended_action("low", [])
        == "continue_processing"
    )