"""Tests for TF-IDF and Logistic Regression intent classification."""

import pytest

from backend.app.nlp.intent_classifier import (
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
