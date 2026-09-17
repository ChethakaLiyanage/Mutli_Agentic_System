from decimal import Decimal

from backend.app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    RiskIndicator,
)

REQUIRED_DOCUMENTS = {
    "motor_accident": [
        "police_report",
        "repair_estimate",
    ],
    "windscreen_damage": [
        "repair_estimate",
    ],
    "vehicle_theft": [
        "police_report",
        "vehicle_registration",
    ],
    "property_damage": [
        "damage_photo",
        "repair_estimate",
    ],
    "medical": [
        "invoice",
    ],
}


def get_missing_documents(
    claim_type: str,
    documents: list[DocumentFacts]
) -> list[str]:
    submitted = {
        document.document_type
        for document in documents
    }

    required = REQUIRED_DOCUMENTS.get(
        claim_type,
        []
    )

    return [
        item for item in required
        if item not in submitted
    ]

def flag_date_conflicts(
    claim: ClaimData,
    documents: list[DocumentFacts],
) -> list[RiskIndicator]:
    indicators = []

    for document in documents:
        if (
            document.incident_date is not None
            and document.incident_date != claim.incident_date
        ):
            indicators.append(
                RiskIndicator(
                    rule_id="DATE_CONFLICT",
                    severity="high",
                    weight=30,
                    title="Incident-date inconsistency",
                    explanation=(
                        "The incident date in the claim differs from "
                        "the date extracted from a supporting document."
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

    return indicators


def flag_amount_conflicts(
    claim: ClaimData,
    documents: list[DocumentFacts],
    tolerance: Decimal = Decimal("0.20"),
) -> list[RiskIndicator]:
    indicators = []

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
            indicators.append(
                RiskIndicator(
                    rule_id="AMOUNT_CONFLICT",
                    severity="medium",
                    weight=25,
                    title="Claimed-amount inconsistency",
                    explanation=(
                        "The requested amount differs materially from "
                        "the repair estimate."
                    ),
                    evidence={
                        "claimed_amount": float(
                            claim.claimed_amount
                        ),
                        "repair_estimate_amount": float(
                            document.claim_amount
                        ),
                        "difference_ratio": round(
                            float(difference_ratio),
                            2,
                        ),
                        "document_id": document.document_id,
                    },
                )
            )

    return indicators
