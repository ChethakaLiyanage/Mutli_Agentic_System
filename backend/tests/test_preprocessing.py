"""Tests for deterministic claim-intake text preprocessing."""

import pytest

from backend.app.nlp.preprocessing import preprocess_text


def test_converts_text_to_lowercase() -> None:
    assert preprocess_text("A BUS Hit My Car") == "a bus hit my car"


def test_trims_and_normalizes_repeated_whitespace() -> None:
    assert preprocess_text("  My\tcar   was\nhit  ") == "my car was hit"


def test_removes_unnecessary_punctuation() -> None:
    assert (
        preprocess_text("A BUS hit my car yesterday near Kandy!!!")
        == "a bus hit my car yesterday near kandy"
    )


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_empty_or_whitespace_input_returns_empty_string(text: str) -> None:
    assert preprocess_text(text) == ""


def test_preserves_common_date_and_time_formats() -> None:
    assert (
        preprocess_text("Accident on 16/09/2026 at 10:30.")
        == "accident on 16/09/2026 at 10:30"
    )
    assert preprocess_text("Reported on 2026-09-16") == "reported on 2026-09-16"


def test_preserves_vehicle_and_policy_like_identifiers() -> None:
    assert (
        preprocess_text("Vehicle WP-CAD-1234, policy POL/2026-001_A.")
        == "vehicle wp-cad-1234 policy pol/2026-001_a"
    )


def test_preserves_original_input_string() -> None:
    original = "  Claim for WP-CAD-1234!!!  "

    preprocess_text(original)

    assert original == "  Claim for WP-CAD-1234!!!  "


def test_rejects_non_string_input() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        preprocess_text(None)  # type: ignore[arg-type]
