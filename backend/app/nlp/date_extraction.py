"""Interface for future date and time expression normalization."""


class DateExtractor:
    """Locate date/time text and normalize it when sufficient context exists."""

    def extract(self, text: str) -> tuple[str | None, str | None]:
        """Return the source date expression and an optional ISO date string."""

        raise NotImplementedError("Date extraction has not been implemented yet")
