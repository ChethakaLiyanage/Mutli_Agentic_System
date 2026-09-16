"""Interface for future vehicle-damage extraction."""

from backend.app.schemas.intake import DamageInformation


class DamageExtractor:
    """Extract stated vehicle damage without inferring unstated facts."""

    def extract(self, text: str) -> DamageInformation:
        """Return damage areas and the customer's description."""

        raise NotImplementedError("Damage extraction has not been implemented yet")
