from datetime import date

from backend.app.fraud.anomaly_model import AnomalyModel
from backend.app.fraud.document_checks import (
    flag_amount_conflicts,
    flag_date_conflicts,
    get_missing_documents,
)
from backend.app.fraud.feature_engineering import build_feature_row
from backend.app.fraud.history_checks import (
    flag_duplicate_claim,
    flag_duplicate_police_report,
    flag_repeated_claims,
)
from backend.app.fraud.rules import (
    flag_late_reporting,
    flag_policy_inactive,
)
from backend.app.fraud.schemas import (
    ClaimData,
    DocumentFacts,
    FraudAssessment,
    PolicyData,
)
from backend.app.fraud.scoring import (
    apply_ml_override,
    calculate_rule_score,
    combine_hybrid_scores,
    get_recommended_action,
    get_risk_level,
)


class FraudDetectionEngine:
    def __init__(self) -> None:
        self.anomaly_model = AnomalyModel()

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
            flag_policy_inactive(
                claim=claim,
                policy=policy,
            ),
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

        ml_anomaly_score = None
        warnings: list[str] = []

        if claim.claimed_amount is None:
            warnings.append("ML anomaly scoring unavailable: claimed amount missing")
        elif self.anomaly_model.is_available():
            try:
                features = build_feature_row(
                    claim_data=claim_data,
                    policy_data=policy_data,
                    document_facts=document_facts,
                    historical_claims=historical_claims,
                    missing_documents=missing_documents,
                    risk_indicators=indicators,
                )
                ml_anomaly_score = self.anomaly_model.get_anomaly_score(
                    features=features,
                )
            except Exception:
                warnings.append("ML anomaly scoring unavailable")
        else:
            warnings.append("ML anomaly model unavailable")

        risk_score = combine_hybrid_scores(
            rule_score=rule_score,
            ml_anomaly_score=ml_anomaly_score,
        )

        risk_level = get_risk_level(risk_score)

        risk_level = apply_ml_override(
            risk_level=risk_level,
            ml_anomaly_score=ml_anomaly_score,
        )

        recommended_action = get_recommended_action(
            risk_level=risk_level,
            missing_documents=missing_documents,
        )

        return FraudAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            rule_score=rule_score,
            ml_anomaly_score=ml_anomaly_score,
            risk_indicators=indicators,
            missing_documents=missing_documents,
            recommended_action=recommended_action,
            automated_decision=False,
            rules_version="1.0.0",
            model_version=(
                "isolation_forest_v1"
                if ml_anomaly_score is not None
                else None
            ),
            warnings=warnings,
        )
