from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from backend.app.fraud.feature_engineering import FEATURE_COLUMNS


BASE_DIR = Path(__file__).resolve().parents[2]
TRAINING_DATA_PATH = (
    BASE_DIR / "data" / "synthetic_claim_features.csv"
)
MODEL_PATH = (
    BASE_DIR / "models" / "isolation_forest_v1.joblib"
)


def train_model() -> None:
    df = pd.read_csv(TRAINING_DATA_PATH)

    X = df[FEATURE_COLUMNS].fillna(0)

    model = Pipeline([
        ("scaler", StandardScaler()),
        (
            "isolation_forest",
            IsolationForest(
                n_estimators=200,
                contamination=0.05,
                random_state=42,
            ),
        ),
    ])

    model.fit(X)

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(model, MODEL_PATH)


if __name__ == "__main__":
    train_model()
    print(f"Saved model to: {MODEL_PATH}")
