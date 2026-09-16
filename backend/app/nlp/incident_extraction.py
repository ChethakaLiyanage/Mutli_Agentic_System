"""Interface for future motor-incident information extraction."""

from backend.app.schemas.intake import IncidentInformation


class IncidentExtractor:
    """Extract incident type, date expression, and location from input text."""

    def extract(self, text: str) -> IncidentInformation:
        """Return incident information grounded in the input message."""

        raise NotImplementedError("Incident extraction has not been implemented yet")
