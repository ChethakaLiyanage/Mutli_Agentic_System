"""Tests for conservative Agent 1 lexical normalization."""

from backend.app.nlp.lexical_normalization import (
    ControlledTextNormalizer,
    damerau_levenshtein_distance,
)


def fitted_normalizer() -> ControlledTextNormalizer:
    return ControlledTextNormalizer().fit(
        [
            "hello and good morning",
            "make a claim for vehicle damage",
            "does my policy cover flood damage",
            "documents needed for claim status",
        ]
    )


def test_damerau_levenshtein_handles_each_supported_edit_operation() -> None:
    assert damerau_levenshtein_distance("helo", "hello") == 1
    assert damerau_levenshtein_distance("hii", "hi") == 1
    assert damerau_levenshtein_distance("polisy", "policy") == 1
    assert damerau_levenshtein_distance("ih", "hi") == 1


def test_normalizes_common_noise_without_exact_phrase_rules() -> None:
    normalizer = fitted_normalizer()

    assert normalizer.normalize("ih") == "hi"
    assert normalizer.normalize("cliam polciy documnts covrage") == (
        "claim policy documents coverage"
    )
    assert normalizer.normalize("HELLLO!!!") == "hello"


def test_preserves_structured_identifiers_dates_amounts_email_and_url() -> None:
    normalizer = fitted_normalizer()
    text = (
        "MTR-100/26 CLM-9283 WP-CAB-1234 18/09/2026 LKR 150000 "
        "me@example.com https://example.com/claim/9283"
    )

    normalized = normalizer.normalize(text)

    for protected_value in text.split():
        assert protected_value in normalized


def test_preserves_unknown_token_when_no_close_candidate_exists() -> None:
    assert fitted_normalizer().normalize("qzvortex") == "qzvortex"
