"""Interface for the future intent-classification component."""

from backend.app.schemas.intake import IntentResult


class IntentClassifier:
    """Classify a preprocessed customer message into a supported intent."""

    def classify(self, text: str) -> IntentResult:
        """Return an intent label and calibrated confidence score."""

        raise NotImplementedError("Intent classification has not been implemented yet")
