import pandas as pd

from app.fraud.anomaly_model import AnomalyModel
from app.fraud.feature_engineering import FEATURE_COLUMNS


model = AnomalyModel()

print("Model available:", model.is_available())

normal_claim = pd.DataFrame(
    [[
        200000,
        365,
        3,
        0,
        2,
        0,
        0,
        0,
        1.05,
    ]],
    columns=FEATURE_COLUMNS,
)

suspicious_claim = pd.DataFrame(
    [[
        1500000,
        3,
        90,
        7,
        1,
        3,
        2,
        1,
        4.00,
    ]],
    columns=FEATURE_COLUMNS,
)

normal_score = model.get_anomaly_score(normal_claim)
suspicious_score = model.get_anomaly_score(suspicious_claim)

print("Normal claim anomaly score:", normal_score)
print("Suspicious claim anomaly score:", suspicious_score)