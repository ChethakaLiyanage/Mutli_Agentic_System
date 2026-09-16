from datetime import date
from decimal import Decimal

from app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    PolicyData,
    RiskIndicator,
)


def flag_policy_inactive(
    claim: ClaimData,
    policy: PolicyData
) -> RiskIndicator | None:
    policy_valid_on_incident_date = (
        policy.status == "active"
        and policy.start_date <= claim.incident_date <= policy.end_date
    )

    if policy_valid_on_incident_date:
        return None

    return RiskIndicator(
        rule_id="POLICY_INACTIVE",
        severity="high",
        weight=40,
        title="Policy eligibility issue",
        explanation=(
            "The policy was not active for the reported incident date. "
            "This requires manual verification."
        ),
        evidence={
            "policy_status": policy.status,
            "policy_start_date": str(policy.start_date),
            "policy_end_date": str(policy.end_date),
            "incident_date": str(claim.incident_date),
        },
    )


def flag_late_reporting(
    claim: ClaimData,
    submitted_date: date,
    threshold_days: int = 30
) -> RiskIndicator | None:
    days_to_report = (
        submitted_date - claim.incident_date
    ).days

    if days_to_report <= threshold_days:
        return None

    return RiskIndicator(
        rule_id="LATE_REPORTING",
        severity="low",
        weight=10,
        title="Late claim reporting",
        explanation=(
            f"The claim was submitted {days_to_report} days after "
            "the reported incident."
        ),
        evidence={
            "incident_date": str(claim.incident_date),
            "submitted_date": str(submitted_date),
            "days_to_report": days_to_report,
            "threshold_days": threshold_days,
        },
    )


def flag_date_conflict(
    claim: ClaimData,
    documents: list[DocumentFacts]
) -> list[RiskIndicator]:
    flags = []

    for document in documents:
        if (
            document.incident_date
            and document.incident_date != claim.incident_date
        ):
            flags.append(
                RiskIndicator(
                    rule_id="DATE_CONFLICT",
                    severity="high",
                    weight=30,
                    title="Incident-date inconsistency",
                    explanation=(
                        "The incident date in the submitted claim "
                        "does not match the date extracted from a "
                        "supporting document."
                    ),
                    evidence={
                        "claim_incident_date": str(
                            claim.incident_date
                        ),
                        "document_incident_date": str(
                            document.incident_date
                        ),
                        "document_id": document.document_id,
                        "document_type": document.document_type,
                    },
                )
            )

    return flags


def flag_amount_conflict(
    claim: ClaimData,
    documents: list[DocumentFacts],
    tolerance: Decimal = Decimal("0.20")
) -> list[RiskIndicator]:
    flags = []

    for document in documents:
        if (
            document.document_type != "repair_estimate"
            or document.claim_amount is None
            or document.claim_amount <= 0
        ):
            continue

        difference_ratio = abs(
            claim.claimed_amount - document.claim_amount
        ) / document.claim_amount

        if difference_ratio > tolerance:
            flags.append(
                RiskIndicator(
                    rule_id="AMOUNT_CONFLICT",
                    severity="medium",
                    weight=25,
                    title="Claimed-amount inconsistency",
                    explanation=(
                        "The requested claim amount differs materially "
                        "from the submitted repair estimate."
                    ),
                    evidence={
                        "claimed_amount": float(
                            claim.claimed_amount
                        ),
                        "repair_estimate_amount": float(
                            document.claim_amount
                        ),
                        "difference_ratio": round(
                            float(difference_ratio), 2
                        ),
                        "document_id": document.document_id,
                    },
                )
            )

    return flags

