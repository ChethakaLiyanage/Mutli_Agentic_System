from datetime import date
from decimal import Decimal

from backend.app.fraud.schemas import ClaimData, RiskIndicator


def flag_duplicate_claim(
    claim: ClaimData,
    historical_claims: list[dict],
) -> RiskIndicator | None:
    for old_claim in historical_claims:
        if old_claim.get("claim_type") != claim.claim_type:
            continue

        old_incident_date = old_claim.get("incident_date")
        old_claimed_amount = old_claim.get("claimed_amount")

        if not old_incident_date or old_claimed_amount is None:
            continue

        date_difference = abs(
            (
                date.fromisoformat(old_incident_date)
                - claim.incident_date
            ).days
        )

        amount_difference = abs(
            Decimal(str(old_claimed_amount))
            - claim.claimed_amount
        )

        amount_similarity = (
            amount_difference
            / max(claim.claimed_amount, Decimal("1"))
        ) <= Decimal("0.10")

        if date_difference <= 7 and amount_similarity:
            return RiskIndicator(
                rule_id="DUPLICATE_CLAIM",
                severity="high",
                weight=35,
                title="Possible duplicate claim",
                explanation=(
                    "A materially similar claim was found for the "
                    "same policy within a short time period."
                ),
                evidence={
                    "existing_claim_id": old_claim.get("id"),
                    "existing_claim_reference": old_claim.get(
                        "claim_reference"
                    ),
                    "existing_incident_date": old_incident_date,
                    "existing_claimed_amount": str(
                        old_claimed_amount
                    ),
                },
            )

    return None


def flag_repeated_claims(
    historical_claims: list[dict],
    threshold: int = 3,
) -> RiskIndicator | None:
    if len(historical_claims) < threshold:
        return None

    return RiskIndicator(
        rule_id="REPEATED_CLAIMS",
        severity="medium",
        weight=20,
        title="Repeated claims under policy",
        explanation=(
            "Multiple previous claims exist under this policy and "
            "should be considered during manual review."
        ),
        evidence={
            "historical_claim_count": len(historical_claims),
            "threshold": threshold,
        },
    )


def flag_duplicate_police_report(
    claim: ClaimData,
    matching_claims: list[dict],
) -> RiskIndicator | None:
    if not claim.police_report_number or not matching_claims:
        return None

    return RiskIndicator(
        rule_id="REPORT_REFERENCE_DUPLICATE",
        severity="high",
        weight=40,
        title="Police-report reference reused",
        explanation=(
            "The submitted police-report number appears in another "
            "claim record and requires manual verification."
        ),
        evidence={
            "police_report_number": claim.police_report_number,
            "matching_claim_references": [
                row.get("claim_reference")
                for row in matching_claims
            ],
        },
    )
