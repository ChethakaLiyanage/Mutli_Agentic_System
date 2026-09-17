from typing import Literal

from backend.app.fraud.schemas import RiskIndicator


def calculate_rule_score(
    indicators: list[RiskIndicator]
) -> float:
    total_weight = sum(
        indicator.weight for indicator in indicators
    )

    return round(min(total_weight / 100, 1.0), 2)


def get_risk_level(score: float) -> Literal["low", "medium", "high"]:
    if score >= 0.70:
        return "high"

    if score >= 0.35:
        return "medium"

    return "low"


def get_recommended_action(
    risk_level: str,
    missing_documents: list[str]
) -> Literal[
    "continue_processing",
    "request_documents",
    "manual_review",
    "escalate",
]:
    if risk_level == "high":
        return "escalate"

    if risk_level == "medium":
        return "manual_review"

    if missing_documents:
        return "request_documents"

    return "continue_processing"

def combine_hybrid_scores(
    rule_score: float,
    ml_anomaly_score: float | None,
) -> float:
    if ml_anomaly_score is None:
        return rule_score

    hybrid_score = (
        0.75 * rule_score
        + 0.25 * ml_anomaly_score
    )

    return round(
        min(hybrid_score, 1.0),
        2,
    )


def apply_ml_override(
    risk_level: str,
    ml_anomaly_score: float | None,
) -> str:
    if (
        ml_anomaly_score is not None
        and ml_anomaly_score >= 0.80
        and risk_level == "low"
    ):
        return "medium"

    return risk_level
