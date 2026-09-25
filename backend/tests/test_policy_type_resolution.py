"""Canonical policy category and explicit-query resolution tests."""

import pytest

from backend.app.policy_types import (
    extract_requested_policy_type,
    normalize_policy_type,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Full Comprehensive", "full_comprehensive"),
        ("FULL_COMPREHENSIVE", "full_comprehensive"),
        ("full", "full_comprehensive"),
        ("comprehensive", "full_comprehensive"),
        ("Partial Comprehensive", "partial_comprehensive"),
        ("partial", "partial_comprehensive"),
        ("Third Party", "third_party"),
        ("third-party", "third_party"),
    ],
)
def test_policy_type_boundary_normalization(value: str, expected: str) -> None:
    assert normalize_policy_type(value) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Tell me about full comprehensive policy", "full_comprehensive"),
        ("Tell me about partial policy", "partial_comprehensive"),
        ("Tell me about third party policy", "third_party"),
        (
            "Does third party insurance cover own vehicle damage?",
            "third_party",
        ),
        ("What is my coverage?", None),
        ("What does my policy cover?", None),
        ("What is comprehensive insurance?", None),
    ],
)
def test_explicit_policy_type_extraction_is_not_ownership_resolution(
    query: str,
    expected: str | None,
) -> None:
    assert extract_requested_policy_type(query) == expected
