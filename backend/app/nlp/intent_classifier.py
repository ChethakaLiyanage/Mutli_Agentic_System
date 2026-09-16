"""TF-IDF and Logistic Regression intent classification."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.nlp.preprocessing import preprocess_text
from backend.app.schemas.intake import IntentResult


INTENT_LABELS = (
    "claim_submission",
    "policy_question",
    "coverage_question",
    "required_documents_question",
    "claim_status",
    "general_information",
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = BACKEND_DIR / "data" / "intent_training.csv"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "intent_classifier.joblib"

_MODEL_CACHE: dict[Path, Pipeline] = {}


@dataclass(frozen=True)
class IntentTrainingResult:
    """Measured held-out evaluation results from an explicit training run."""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    classification_report: str
    confusion_matrix: list[list[int]]
    train_size: int
    test_size: int
    model_path: Path


def _load_dataset(dataset_path: str | Path) -> tuple[list[str], list[str]]:
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Intent dataset not found: {path}")

    with path.open(encoding="utf-8", newline="") as dataset_file:
        rows = list(csv.DictReader(dataset_file))

    if not rows or set(rows[0]) != {"text", "label"}:
        raise ValueError("Intent dataset must contain text and label columns")

    texts: list[str] = []
    labels: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        text = row.get("text", "")
        label = row.get("label", "")
        if not preprocess_text(text):
            raise ValueError(f"Dataset row {row_number} has empty text")
        if label not in INTENT_LABELS:
            raise ValueError(f"Dataset row {row_number} has unsupported label: {label}")
        texts.append(text)
        labels.append(label)

    if set(labels) != set(INTENT_LABELS):
        missing = sorted(set(INTENT_LABELS) - set(labels))
        raise ValueError(f"Intent dataset is missing labels: {missing}")

    return texts, labels


def _build_pipeline(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=preprocess_text,
                    lowercase=False,
                    ngram_range=(1, 2),
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=1000, random_state=random_state),
            ),
        ]
    )


def train_intent_classifier(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> IntentTrainingResult:
    """Train, evaluate, then persist a classifier fitted on all available data.

    Evaluation metrics come only from the stratified held-out test split. After
    evaluation, a fresh pipeline is fitted on the complete dataset and saved for
    runtime predictions. Calling this function explicitly overwrites the model.
    """

    texts, labels = _load_dataset(dataset_path)
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )

    evaluation_model = _build_pipeline(random_state)
    evaluation_model.fit(train_texts, train_labels)
    predictions = evaluation_model.predict(test_texts)

    accuracy = accuracy_score(test_labels, predictions)
    precision = precision_score(
        test_labels,
        predictions,
        labels=INTENT_LABELS,
        average="macro",
        zero_division=0,
    )
    recall = recall_score(
        test_labels,
        predictions,
        labels=INTENT_LABELS,
        average="macro",
        zero_division=0,
    )
    f1 = f1_score(
        test_labels,
        predictions,
        labels=INTENT_LABELS,
        average="macro",
        zero_division=0,
    )
    report = classification_report(
        test_labels,
        predictions,
        labels=INTENT_LABELS,
        zero_division=0,
    )
    matrix = confusion_matrix(
        test_labels,
        predictions,
        labels=INTENT_LABELS,
    ).tolist()

    final_model = _build_pipeline(random_state)
    final_model.fit(texts, labels)

    resolved_model_path = Path(model_path).resolve()
    resolved_model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, resolved_model_path)
    _MODEL_CACHE[resolved_model_path] = final_model

    return IntentTrainingResult(
        accuracy=float(accuracy),
        precision=float(precision),
        recall=float(recall),
        f1_score=float(f1),
        classification_report=report,
        confusion_matrix=matrix,
        train_size=len(train_texts),
        test_size=len(test_texts),
        model_path=resolved_model_path,
    )


def load_intent_classifier(
    model_path: str | Path = DEFAULT_MODEL_PATH,
    *,
    force_reload: bool = False,
) -> Pipeline:
    """Load a persisted pipeline once and reuse it for later predictions."""

    resolved_model_path = Path(model_path).resolve()
    if not force_reload and resolved_model_path in _MODEL_CACHE:
        return _MODEL_CACHE[resolved_model_path]
    if not resolved_model_path.is_file():
        raise FileNotFoundError(
            f"Intent model not found: {resolved_model_path}. "
            "Run backend/scripts/train_intent_classifier.py first."
        )

    model = joblib.load(resolved_model_path)
    if not isinstance(model, Pipeline) or not hasattr(model, "predict_proba"):
        raise TypeError("Persisted intent model is not a probability pipeline")

    _MODEL_CACHE[resolved_model_path] = model
    return model


def predict_intent(
    text: str,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> tuple[str, float]:
    """Return the most likely supported intent and its class probability."""

    cleaned_text = preprocess_text(text)
    if not cleaned_text:
        raise ValueError("text must not be empty or whitespace only")

    model = load_intent_classifier(model_path)
    probabilities = model.predict_proba([cleaned_text])[0]
    best_index = int(probabilities.argmax())
    label = str(model.classes_[best_index])
    return label, float(probabilities[best_index])


class IntentClassifier:
    """Object-oriented adapter used by the Claim Intake Agent."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)

    def classify(self, text: str) -> IntentResult:
        """Return a schema-compatible intent result for the supplied text."""

        label, confidence = predict_intent(text, self.model_path)
        return IntentResult(label=label, confidence=confidence)
