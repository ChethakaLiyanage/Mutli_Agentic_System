"""Deterministic extraction of claimed amounts from customer messages."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_AMOUNT_PATTERN = (
    r"\d{1,3}(?:[, ]\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"
)
_PREFIX_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"(?ix)"
    r"(?<![\w.])"
    r"(?:lkr|rs\.?|inr|usd|\$|€|£)\s*"
    rf"(?P<amount>{_AMOUNT_PATTERN})"
    r"\s*"
    r"(?:dollars?|rupees?)?"
    r"(?![\w,])"
)
_SUFFIX_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"(?ix)"
    r"(?<![\w.])"
    rf"(?P<amount>{_AMOUNT_PATTERN})"
    r"\s*"
    r"(?:lkr|rs\.?|inr|usd|dollars?|rupees?|\$|€|£)"
    r"(?!\w)"
)
_LABELLED_AMOUNT_PATTERN = re.compile(
    r"(?ix)"
    r"\b(?:claim(?:ed)?|amount|value|valued|worth)\b"
    r"\s*(?:is|of|for|:)?\s*"
    rf"(?P<amount>{_AMOUNT_PATTERN})"
    r"(?![\w,])"
)


def extract_claimed_amount(text: str) -> Decimal | None:
    """Return the first currency-like amount explicitly stated in ``text``."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    matches = [
        *_PREFIX_CURRENCY_AMOUNT_PATTERN.finditer(text),
        *_SUFFIX_CURRENCY_AMOUNT_PATTERN.finditer(text),
        *_LABELLED_AMOUNT_PATTERN.finditer(text),
    ]
    for match in sorted(matches, key=lambda item: item.start()):
        raw_amount = match.group("amount").replace(",", "").replace(" ", "")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            continue
        if amount > 0:
            return amount
    return None
