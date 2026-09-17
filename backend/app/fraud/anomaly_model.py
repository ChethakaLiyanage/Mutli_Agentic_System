from pathlib import Path

import joblib
import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = (
    BACKEND_DIR
    / "models"
    / "isolation_forest_v1.joblib"
)


class AnomalyModel:
    def __init__(self):
        self.model = None

        print(f"Looking for model at: {MODEL_PATH}")

        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)

    def is_available(self) -> bool:
        return self.model is not None

    def get_anomaly_score(
        self,
        features: pd.DataFrame,
    ) -> float | None:
        if self.model is None:
            return None

        decision_score = float(
            self.model.decision_function(features)[0]
        )

        anomaly_score = 1 / (
            1 + pow(2.718281828, 5 * decision_score)
        )

        return round(
            max(0.0, min(1.0, anomaly_score)),
            2,
        )