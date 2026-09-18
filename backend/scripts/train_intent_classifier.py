"""Train, evaluate, and persist the claim-intake intent classifier."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from backend.app.nlp.intent_classifier import (  # noqa: E402
    DEFAULT_CLEAN_EVALUATION_PATH,
    DEFAULT_NOISY_EVALUATION_PATH,
    INTENT_LABELS,
    evaluate_intent_classifier,
    train_intent_classifier,
)


def main() -> None:
    """Run an explicit training job and print measured evaluation results."""

    result = train_intent_classifier()

    print(f"Training samples: {result.train_size}")
    print(f"Test samples: {result.test_size}")
    print(f"Class distribution: {result.class_distribution}")
    print(f"Accuracy: {result.accuracy:.4f}")
    print(f"Macro precision: {result.precision:.4f}")
    print(f"Macro recall: {result.recall:.4f}")
    print(f"Macro F1-score: {result.f1_score:.4f}")
    print(
        "5-fold cross-validation accuracy: "
        f"{result.cross_validation_accuracy:.4f}"
    )
    print(
        "5-fold cross-validation macro F1-score: "
        f"{result.cross_validation_f1:.4f}"
    )
    print("\nClassification report:")
    print(result.classification_report)
    print("Confusion matrix label order:")
    print(list(INTENT_LABELS))
    print("Confusion matrix:")
    for row in result.confusion_matrix:
        print(row)
    print(f"\nSaved final model to: {result.model_path}")

    evaluations = {
        "Clean external": evaluate_intent_classifier(
            DEFAULT_CLEAN_EVALUATION_PATH
        ),
        "Noisy external": evaluate_intent_classifier(
            DEFAULT_NOISY_EVALUATION_PATH
        ),
        "Combined external": evaluate_intent_classifier(
            (
                DEFAULT_CLEAN_EVALUATION_PATH,
                DEFAULT_NOISY_EVALUATION_PATH,
            )
        ),
    }
    for name, evaluation in evaluations.items():
        print(f"\n{name} evaluation ({evaluation.sample_size} samples):")
        print(f"Accuracy: {evaluation.accuracy:.4f}")
        print(f"Macro F1-score: {evaluation.f1_score:.4f}")
        print(evaluation.classification_report)
        print("Confusion matrix:")
        for row in evaluation.confusion_matrix:
            print(row)


if __name__ == "__main__":
    main()
