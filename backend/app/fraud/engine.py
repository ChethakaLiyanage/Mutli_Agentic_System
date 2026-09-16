from datetime import date

from app.fraud.document_checks import (
    flag_amount_conflicts,
    flag_date_conflicts,
    get_missing_documents,
)
from app.fraud.history_checks import (
    flag_duplicate_claim,
    flag_duplicate_police_report,
    flag_repeated_claims,
)
from app.fraud.rules import (
    flag_late_reporting,
    flag_policy_inactive,
)
from app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    FraudAssessment,
    PolicyData,
)
from app.fraud.scoring import (
    calculate_rule_score,
    get_recommended_action,
    get_risk_level,
)


class FraudDetectionEngine:
    def evaluate(
        self,
        claim_data: dict,
        policy_data: dict,
        document_facts: list[dict],
        historical_claims: list[dict],
        duplicate_police_report_claims: list[dict],
    ) -> FraudAssessment:
        claim = ClaimData(**claim_data)
        policy = PolicyData(**policy_data)

        documents = [
            DocumentFacts(**document)
            for document in document_facts
        ]

        indicators = []

        single_result_checks = [
            flag_policy_inactive(claim, policy),
            flag_late_reporting(
                claim=claim,
                submitted_date=date.today(),
            ),
            flag_duplicate_claim(
                claim=claim,
                historical_claims=historical_claims,
            ),
            flag_repeated_claims(
                historical_claims=historical_claims,
            ),
            flag_duplicate_police_report(
                claim=claim,
                matching_claims=duplicate_police_report_claims,
            ),
        ]

        indicators.extend(
            indicator
            for indicator in single_result_checks
            if indicator is not None
        )

        indicators.extend(
            flag_date_conflicts(
                claim=claim,
                documents=documents,
            )
        )

        indicators.extend(
            flag_amount_conflicts(
                claim=claim,
                documents=documents,
            )
        )

        missing_documents = get_missing_documents(
            claim_type=claim.claim_type,
            documents=documents,
        )

        rule_score = calculate_rule_score(indicators)
        risk_level = get_risk_level(rule_score)

        recommended_action = get_recommended_action(
            risk_level=risk_level,
            missing_documents=missing_documents,
        )

        return FraudAssessment(
            risk_level=risk_level,
            risk_score=rule_score,
            rule_score=rule_score,
            ml_anomaly_score=None,
            risk_indicators=indicators,
            missing_documents=missing_documents,
            recommended_action=recommended_action,
            automated_decision=False,
            rules_version="1.0.0",
            model_version=None,
        )