from datetime import date
from decimal import Decimal

import pandas as pd


FEATURE_COLUMNS = [
    "claimed_amount",
    "days_since_policy_start",
    "days_to_report",
    "historical_claim_count",
    "document_count",
    "missing_document_count",
    "date_conflict_count",
    "amount_conflict_count",
    "amount_vs_repair_estimate_ratio",
]


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def build_feature_row(
    claim_data: dict,
    policy_data: dict,
    document_facts: list[dict],
    historical_claims: list[dict],
    missing_documents: list[str],
    risk_indicators: list,
) -> pd.DataFrame:
    incident_date = _parse_date(
        claim_data["incident_date"]
    )

    policy_start_date = _parse_date(
        policy_data["start_date"]
    )

    submitted_date = _parse_date(
        claim_data.get("submitted_date")
        or date.today()
    )

    claimed_amount = Decimal(
        str(claim_data["claimed_amount"])
    )

    repair_estimates = [
        Decimal(str(document["claimed_amount"]))
        for document in document_facts
        if (
            document.get("document_type")
            == "repair_estimate"
            and document.get("claimed_amount") is not None
        )
    ]

    repair_estimate_amount = (
        repair_estimates[0]
        if repair_estimates
        else claimed_amount
    )

    rule_ids = [
        indicator.rule_id
        if hasattr(indicator, "rule_id")
        else indicator.get("rule_id")
        for indicator in risk_indicators
    ]

    feature_values = {
        "claimed_amount": float(claimed_amount),
        "days_since_policy_start": max(
            0,
            (incident_date - policy_start_date).days,
        ),
        "days_to_report": max(
            0,
            (submitted_date - incident_date).days,
        ),
        "historical_claim_count": len(historical_claims),
        "document_count": len(document_facts),
        "missing_document_count": len(missing_documents),
        "date_conflict_count": rule_ids.count(
            "DATE_CONFLICT"
        ),
        "amount_conflict_count": rule_ids.count(
            "AMOUNT_CONFLICT"
        ),
        "amount_vs_repair_estimate_ratio": float(
            claimed_amount / max(
                repair_estimate_amount,
                Decimal("1"),
            )
        ),
    }

    return pd.DataFrame(
        [feature_values],
        columns=FEATURE_COLUMNS,
    )