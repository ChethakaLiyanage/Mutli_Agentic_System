"""Interface for future named-entity and vehicle-information extraction."""

from backend.app.schemas.intake import ExtractedEntity


class EntityExtractor:
    """Extract only entities supported by evidence in the input message."""

    def extract(self, text: str) -> list[ExtractedEntity]:
        """Return entities and their optional source offsets."""

        raise NotImplementedError("Entity extraction has not been implemented yet")
