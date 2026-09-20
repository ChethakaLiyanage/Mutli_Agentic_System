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
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.nlp.preprocessing import preprocess_text
from backend.app.nlp.lexical_normalization import (
    GREETING_PHRASES,
    INSURANCE_TERMS,
    ControlledTextNormalizer,
    damerau_levenshtein_distance,
)
from backend.app.schemas.intake import IntentResult


INTENT_LABELS = (
    "greeting",
    "thanks",
    "goodbye",
    "acknowledgement",
    "claim_submission",
    "policy_question",
    "coverage_question",
    "required_documents_question",
    "claim_status",
    "general_information",
)

# These are intentionally narrow whole-message patterns.  Social language is
# useful conversational context, but it must never take priority over a real
# insurance request such as "hi, I need to make a claim".
_PURE_SOCIAL_INTENTS = {
    "greeting": {
        "hi", "hello", "hey", "greetings", "hello there", "hi there",
        "good morning", "good afternoon", "good evening", "gud day",
    },
    "thanks": {
        "thanks", "thank you", "thank u", "thx", "cheers", "many thanks",
        "thanks a lot", "appreciate it", "appreciate your help",
    },
    "goodbye": {
        "bye", "goodbye", "good bye", "see you", "see ya", "take care",
        "talk later",
    },
    "acknowledgement": {
        "ok", "okay", "alright", "all right", "got it", "understood",
        "noted", "sure", "sounds good", "i understand",
    },
}

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = BACKEND_DIR / "data" / "intent_training.csv"
DEFAULT_CLEAN_EVALUATION_PATH = BACKEND_DIR / "data" / "intent_evaluation_clean.csv"
DEFAULT_NOISY_EVALUATION_PATH = BACKEND_DIR / "data" / "intent_evaluation_noisy.csv"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "intent_classifier.joblib"

_MODEL_CACHE: dict[Path, Pipeline] = {}

WORD_TFIDF_SETTINGS = {
    "ngram_range": (1, 2),
    "sublinear_tf": True,
}
CHAR_TFIDF_SETTINGS = {
    "analyzer": "char_wb",
    "ngram_range": (3, 5),
    "sublinear_tf": True,
}
LOGISTIC_REGRESSION_SETTINGS = {
    "C": 2.0,
    "max_iter": 1000,
}


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
    class_distribution: dict[str, int]
    cross_validation_accuracy: float
    cross_validation_f1: float


@dataclass(frozen=True)
class IntentEvaluationResult:
    """Metrics measured on one or more external, non-training datasets."""

    accuracy: float
    f1_score: float
    classification_report: str
    confusion_matrix: list[list[int]]
    sample_size: int


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


def _load_evaluation_dataset(
    dataset_path: str | Path,
) -> tuple[list[str], list[str]]:
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Intent evaluation dataset not found: {path}")

    with path.open(encoding="utf-8", newline="") as dataset_file:
        rows = list(csv.DictReader(dataset_file))
    if not rows or not {"text", "label"}.issubset(rows[0]):
        raise ValueError("Evaluation dataset must contain text and label columns")

    texts: list[str] = []
    labels: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        text = row.get("text", "")
        label = row.get("label", "")
        if not preprocess_text(text):
            raise ValueError(f"Evaluation row {row_number} has empty text")
        if label not in INTENT_LABELS:
            raise ValueError(
                f"Evaluation row {row_number} has unsupported label: {label}"
            )
        texts.append(text)
        labels.append(label)
    return texts, labels


def _build_pipeline(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("normalize", ControlledTextNormalizer()),
            (
                "features",
                FeatureUnion(
                    transformer_list=[
                        (
                            "word_tfidf",
                            TfidfVectorizer(
                                lowercase=False,
                                **WORD_TFIDF_SETTINGS,
                            ),
                        ),
                        (
                            "char_tfidf",
                            TfidfVectorizer(
                                lowercase=False,
                                **CHAR_TFIDF_SETTINGS,
                            ),
                        ),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    random_state=random_state,
                    **LOGISTIC_REGRESSION_SETTINGS,
                ),
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

    cross_validation = cross_validate(
        _build_pipeline(random_state),
        texts,
        labels,
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state),
        scoring=("accuracy", "f1_macro"),
        n_jobs=1,
    )

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
        class_distribution={label: labels.count(label) for label in INTENT_LABELS},
        cross_validation_accuracy=float(
            cross_validation["test_accuracy"].mean()
        ),
        cross_validation_f1=float(cross_validation["test_f1_macro"].mean()),
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


def evaluate_intent_classifier(
    dataset_paths: str | Path | tuple[str | Path, ...],
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> IntentEvaluationResult:
    """Evaluate the persisted production pipeline on external labeled data."""

    paths = dataset_paths if isinstance(dataset_paths, tuple) else (dataset_paths,)
    texts: list[str] = []
    labels: list[str] = []
    for path in paths:
        path_texts, path_labels = _load_evaluation_dataset(path)
        texts.extend(path_texts)
        labels.extend(path_labels)

    model = load_intent_classifier(model_path, force_reload=True)
    predictions = [_predict_with_model(text, model)[0] for text in texts]
    return IntentEvaluationResult(
        accuracy=float(accuracy_score(labels, predictions)),
        f1_score=float(
            f1_score(
                labels,
                predictions,
                labels=INTENT_LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        classification_report=classification_report(
            labels,
            predictions,
            labels=INTENT_LABELS,
            zero_division=0,
        ),
        confusion_matrix=confusion_matrix(
            labels,
            predictions,
            labels=INTENT_LABELS,
        ).tolist(),
        sample_size=len(texts),
    )


def predict_intent(
    text: str,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> tuple[str, float]:
    """Return the most likely supported intent and its class probability."""

    cleaned_text = preprocess_text(text)
    if not cleaned_text:
        raise ValueError("text must not be empty or whitespace only")

    model = load_intent_classifier(model_path)
    return _predict_with_model(text, model)


def _predict_with_model(text: str, model: Pipeline) -> tuple[str, float]:
    """Apply the persisted model and controlled short-text arbitration."""

    probabilities = model.predict_proba([text])[0]
    normalized_text = model.named_steps["normalize"].transform([text])[0]
    normalized_tokens = normalized_text.split()
    normalized_token_set = set(normalized_tokens)

    # A social turn is only recognised when the complete message is social.
    # This preserves normal insurance routing for mixed messages.
    for social_intent, phrases in _PURE_SOCIAL_INTENTS.items():
        if normalized_text in phrases:
            social_indexes = [
                index
                for index, model_label in enumerate(model.classes_)
                if model_label == social_intent
            ]
            if social_indexes:
                return social_intent, float(probabilities[social_indexes[0]])

    # A claim creation action must take precedence over greeting or status
    # language. This is vocabulary-level arbitration rather than sentence
    # matching, and still requires support from the supervised class score.
    submission_actions = {"file", "lodge", "make", "open", "report", "submit"}
    status_terms = {
        "decision",
        "pending",
        "progress",
        "reviewed",
        "stage",
        "status",
        "track",
        "update",
    }
    if (
        "claim" in normalized_token_set
        and normalized_token_set.intersection(submission_actions)
        and not normalized_token_set.intersection(status_terms)
    ):
        submission_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label == "claim_submission"
        ]
        if submission_indexes:
            submission_index = submission_indexes[0]
            submission_probability = float(probabilities[submission_index])
            if submission_probability >= 0.10:
                return "claim_submission", max(submission_probability, 0.75)

    policy_inquiry_terms = {"policy", "coverage", "cover"}

    # Active accident reporting (e.g. "im accidented just now what shoul i do?",
    # "someone hit my car just now", "i crashed my car what should i do") represents
    # a claim submission even if phrased as a question. In contrast, hypothetical
    # questions (e.g. "what should i do if i have an accident", "in case of an accident what to do")
    # are general information inquiries.
    active_incident_indicators = {
        "accident",
        "accidented",
        "crash",
        "crashed",
        "hit",
        "collided",
        "collision",
        "sideswiped",
        "vandalised",
    }
    active_temporal_or_subject = {
        "just",
        "now",
        "today",
        "yesterday",
        "ago",
        "happened",
        "occurred",
        "got",
        "had",
        "was",
        "were",
        "someone",
        "im",
        "my",
        "our",
        "mins",
        "minutes",
    }
    hypothetical_markers = {"if", "suppose", "whether", "generally", "normally", "usually"}
    is_hypothetical = (
        bool(normalized_token_set.intersection(hypothetical_markers))
        or ("case" in normalized_token_set and "in" in normalized_token_set)
    )

    if (
        normalized_token_set.intersection(active_incident_indicators)
        and not is_hypothetical
        and not normalized_token_set.intersection(status_terms)
        and not normalized_token_set.intersection(policy_inquiry_terms)
    ):
        has_active_marker = bool(normalized_token_set.intersection(active_temporal_or_subject))
        submission_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label == "claim_submission"
        ]
        if submission_indexes and has_active_marker:
            submission_index = submission_indexes[0]
            submission_probability = float(probabilities[submission_index])
            return "claim_submission", max(submission_probability, 0.85)

    if is_hypothetical and normalized_token_set.intersection(active_incident_indicators):
        gen_info_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label == "general_information"
        ]
        if gen_info_indexes:
            gen_idx = gen_info_indexes[0]
            gen_prob = float(probabilities[gen_idx])
            return "general_information", max(gen_prob, 0.75)

    if (
        len(normalized_tokens) <= 2
        and not normalized_token_set.intersection(INSURANCE_TERMS)
    ):
        greeting_similarity = max(
            1.0
            - damerau_levenshtein_distance(normalized_text, phrase)
            / max(len(normalized_text), len(phrase))
            for phrase in GREETING_PHRASES
        )
        greeting_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label == "greeting"
        ]
        if greeting_indexes:
            greeting_index = greeting_indexes[0]
            greeting_probability = float(probabilities[greeting_index])
            if greeting_similarity >= 0.75 and greeting_probability >= 0.20:
                return "greeting", greeting_probability

    # If the user is asking about policy or coverage and not explicitly
    # asking for status/tracking, policy_question / coverage_question must
    # take precedence over claim_status (e.g. "can i know about motor claim policy").
    policy_inquiry_terms = {"policy", "coverage", "cover"}
    if (
        normalized_token_set.intersection(policy_inquiry_terms)
        and not normalized_token_set.intersection(status_terms)
    ):
        info_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label in {
                "policy_question",
                "coverage_question",
                "required_documents_question",
                "general_information",
            }
        ]
        if info_indexes:
            best_info_idx = max(info_indexes, key=lambda idx: probabilities[idx])
            info_prob_sum = float(sum(probabilities[idx] for idx in info_indexes))
            best_info_label = str(model.classes_[best_info_idx])
            if probabilities[best_info_idx] >= 0.15 or info_prob_sum >= 0.25:
                effective_confidence = max(float(probabilities[best_info_idx]), info_prob_sum, 0.70)
                return best_info_label, effective_confidence

    has_insurance_topic = bool(
        normalized_token_set.intersection(INSURANCE_TERMS)
        or normalized_token_set.intersection(policy_inquiry_terms)
        or normalized_token_set.intersection(submission_actions)
    )

    is_pure_social = False
    for s_intent, s_phrases in _PURE_SOCIAL_INTENTS.items():
        if normalized_text in s_phrases:
            is_pure_social = True
            break

    # If the user message has no insurance terms and is not a recognized pure social
    # turn (e.g. out-of-domain words like "panda", "dog", "cat"), route it to general
    # information so it can proceed through retrieval and be naturally answered by the LLM.
    if not has_insurance_topic and not is_pure_social:
        return "general_information", 0.50

    best_index = int(probabilities.argmax())
    label = str(model.classes_[best_index])
    confidence = float(probabilities[best_index])

    social_classes = {"greeting", "thanks", "goodbye", "acknowledgement"}
    if label in social_classes and has_insurance_topic:
        # Social words must not hide the substantive insurance request.
        insurance_indices = [
            idx for idx, c in enumerate(model.classes_)
            if c not in social_classes
        ]
        if insurance_indices:
            best_insurance_idx = max(insurance_indices, key=lambda idx: probabilities[idx])
            label = str(model.classes_[best_insurance_idx])
            confidence = max(float(probabilities[best_insurance_idx]), 0.70)

    # If the predicted label is an information intent and multiple info categories
    # split probability mass (e.g., policy_question vs coverage_question), aggregate
    # the info mass so valid inquiries are not penalized by fine-grained class split.
    if label in {
        "policy_question",
        "coverage_question",
        "required_documents_question",
        "general_information",
    }:
        info_indexes = [
            index
            for index, model_label in enumerate(model.classes_)
            if model_label in {
                "policy_question",
                "coverage_question",
                "required_documents_question",
                "general_information",
            }
        ]
        info_prob_sum = float(sum(probabilities[idx] for idx in info_indexes))
        if info_prob_sum >= 0.25:
            confidence = max(confidence, info_prob_sum, 0.70)

    return label, confidence


class IntentClassifier:
    """Object-oriented adapter used by the Claim Intake Agent."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)

    def classify(self, text: str) -> IntentResult:
        """Return a schema-compatible intent result for the supplied text."""

        label, confidence = predict_intent(text, self.model_path)
        return IntentResult(label=label, confidence=confidence)
