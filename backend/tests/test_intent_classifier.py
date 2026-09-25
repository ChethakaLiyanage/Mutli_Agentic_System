"""Tests for TF-IDF and Logistic Regression intent classification."""

import csv
from collections import Counter

import pytest

from backend.app.nlp.intent_classifier import (
    DEFAULT_DATASET_PATH,
    DEFAULT_CLEAN_EVALUATION_PATH,
    DEFAULT_NOISY_EVALUATION_PATH,
    DEFAULT_MODEL_PATH,
    INTENT_LABELS,
    load_intent_classifier,
    predict_intent,
)


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        ("Someone crashed into my car and I want to claim", "claim_submission"),
        ("Does my insurance cover flood damage?", "coverage_question"),
        (
            "What documents do I need after an accident?",
            "required_documents_question",
        ),
        ("Can you explain my motor policy?", "policy_question"),
        ("What is happening with my claim?", "claim_status"),
        ("How does motor insurance work?", "general_information"),
        ("Hello there", "greeting"),
    ],
)
def test_predicts_representative_intents(
    text: str,
    expected_label: str,
) -> None:
    label, confidence = predict_intent(text)

    assert label == expected_label
    assert label in INTENT_LABELS
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        (
            "What vehicle registration did the previous user give you?",
            "general_information",
        ),
        (
            "What documents do I need for a vehicle collision claim?",
            "required_documents_question",
        ),
        ("What is my policy coverage?", "coverage_question"),
        ("I had a vehicle collision yesterday.", "claim_submission"),
    ],
)
def test_overlapping_motor_vocabulary_uses_distinct_semantic_routes(
    text: str,
    expected_label: str,
) -> None:
    label, _ = predict_intent(text)
    assert label == expected_label


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_rejects_empty_or_whitespace_input(text: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        predict_intent(text)


def test_loads_and_caches_persisted_model() -> None:
    assert DEFAULT_MODEL_PATH.is_file()

    loaded_model = load_intent_classifier(force_reload=True)
    cached_model = load_intent_classifier()

    assert loaded_model is cached_model
    assert hasattr(loaded_model, "predict_proba")


def test_returns_probability_confidence() -> None:
    _, confidence = predict_intent("I need an update on the claim I filed last week")

    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        ("i wana mak a clam", "claim_submission"),
        ("does my polcy covr flod dmg", "coverage_question"),
        (
            "wat documnts do i ned for theft",
            "required_documents_question",
        ),
        ("chec my clam stats", "claim_status"),
        ("tell me abt my polcy", "policy_question"),
        (
            "good mornin does my polcy cover flood",
            "coverage_question",
        ),
        ("helo i need to submit a claim", "claim_submission"),
        ("ih", "greeting"),
        ("hii", "greeting"),
        ("helo", "greeting"),
        ("god mornin", "greeting"),
        ("i ned to file cliam", "claim_submission"),
        ("does my polciy covr flod dmg", "coverage_question"),
        ("ih i wana mak a clam", "claim_submission"),
        (
            "helo does my polcy covr flood",
            "coverage_question",
        ),
        (
            "good mornin what docs do i ned for theft",
            "required_documents_question",
        ),
        ("hey chek my clam stats", "claim_status"),
    ],
)
def test_predicts_noisy_customer_intents(text: str, expected_label: str) -> None:
    label, confidence = predict_intent(text)

    assert label == expected_label
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        ("I want to make a claim", "claim_submission"),
        ("Does my policy cover flood damage?", "coverage_question"),
        (
            "What documents do I need for theft?",
            "required_documents_question",
        ),
        ("Check my claim status", "claim_status"),
        ("Tell me about my policy", "policy_question"),
    ],
)
def test_correctly_spelled_equivalents_remain_correct(
    text: str,
    expected_label: str,
) -> None:
    label, _ = predict_intent(text)

    assert label == expected_label


def test_persisted_model_combines_word_and_character_tfidf() -> None:
    model = load_intent_classifier(force_reload=True)
    assert model.named_steps["normalize"].normalize("ih") == "hi"
    features = model.named_steps["features"]
    transformers = dict(features.transformer_list)

    assert transformers["word_tfidf"].ngram_range == (1, 2)
    assert transformers["char_tfidf"].analyzer == "char_wb"
    assert transformers["char_tfidf"].ngram_range == (3, 5)


def test_training_dataset_remains_balanced() -> None:
    with DEFAULT_DATASET_PATH.open(encoding="utf-8", newline="") as dataset:
        rows = list(csv.DictReader(dataset))

    assert len(rows) == len(INTENT_LABELS) * 50
    assert Counter(row["label"] for row in rows) == {
        label: 50 for label in INTENT_LABELS
    }


def test_required_noisy_regression_phrases_are_not_training_rows() -> None:
    with DEFAULT_DATASET_PATH.open(encoding="utf-8", newline="") as dataset:
        training_texts = {
            row["text"].casefold() for row in csv.DictReader(dataset)
        }

    held_out_regressions = {
        "i wana mak a clam",
        "does my polcy covr flod dmg",
        "wat documnts do i ned for theft",
        "chec my clam stats",
        "tell me abt my polcy",
        "good mornin does my polcy cover flood",
        "helo i need to submit a claim",
        "ih",
        "hii",
        "helo",
        "god mornin",
        "i ned to file cliam",
        "does my polciy covr flod dmg",
    }
    assert training_texts.isdisjoint(held_out_regressions)


def test_external_evaluation_rows_are_not_training_rows() -> None:
    def texts(path):
        with path.open(encoding="utf-8", newline="") as dataset:
            return {row["text"].casefold() for row in csv.DictReader(dataset)}

    training_texts = texts(DEFAULT_DATASET_PATH)
    evaluation_texts = texts(DEFAULT_CLEAN_EVALUATION_PATH) | texts(
        DEFAULT_NOISY_EVALUATION_PATH
    )

    assert training_texts.isdisjoint(evaluation_texts)
