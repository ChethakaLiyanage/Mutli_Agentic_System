from app.fraud.schemas import RiskIndicator


def calculate_rule_score(
    indicators: list[RiskIndicator]
) -> float:
    total_weight = sum(
        indicator.weight for indicator in indicators
    )

    return round(min(total_weight / 100, 1.0), 2)


def get_risk_level(score: float) -> str:
    if score >= 0.70:
        return "high"

    if score >= 0.35:
        return "medium"

    return "low"


def get_recommended_action(
    risk_level: str,
    missing_documents: list[str]
) -> str:
    if risk_level == "high":
        return "escalate"

    if risk_level == "medium":
        return "manual_review"

    if missing_documents:
        return "request_documents"

    return "continue_processing"