"""Train, evaluate, and persist the claim-intake intent classifier."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from backend.app.nlp.intent_classifier import (  # noqa: E402
    INTENT_LABELS,
    train_intent_classifier,
)


def main() -> None:
    """Run an explicit training job and print measured evaluation results."""

    result = train_intent_classifier()

    print(f"Training samples: {result.train_size}")
    print(f"Test samples: {result.test_size}")
    print(f"Accuracy: {result.accuracy:.4f}")
    print(f"Macro precision: {result.precision:.4f}")
    print(f"Macro recall: {result.recall:.4f}")
    print(f"Macro F1-score: {result.f1_score:.4f}")
    print("\nClassification report:")
    print(result.classification_report)
    print("Confusion matrix label order:")
    print(list(INTENT_LABELS))
    print("Confusion matrix:")
    for row in result.confusion_matrix:
        print(row)
    print(f"\nSaved final model to: {result.model_path}")


if __name__ == "__main__":
    main()
