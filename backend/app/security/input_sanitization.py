from __future__ import annotations
"""Centralized security input sanitization module for motor-insurance backend.

Applies security-focused sanitization to free-text inputs, document uploads,
and untrusted content passed to LLM components without destroying domain-specific
insurance data (such as policy numbers, registration numbers, dates, or amounts).
"""


import html
import re
import unicodedata

MAX_TEXT_LENGTH = 5000

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"system\s+prompt",
    r"developer\s+message",
]


class InputSanitizationError(ValueError):
    """Raised when user input violates input sanitization limits or format rules."""

    pass


def sanitize_user_text(value: str) -> str:
    """Sanitize customer-supplied free-text while preserving domain identifiers.

    - Validates that input is text.
    - Normalizes Unicode characters via NFKC.
    - Removes null bytes and unsafe ASCII control characters.
    - Enforces maximum character length limit (5000 chars).
    - Removes script tags and HTML markup.
    - Unescapes safe HTML entities.
    - Normalizes spacing and multiline breaks.
    - Preserves claim IDs (CLM-9283), registration plates (WP-CAB-1234),
      dates (18/09/2026), currency amounts (Rs. 150,000), and normal punctuation.
    """
    if not isinstance(value, str):
        raise InputSanitizationError("Input must be text.")

    # Unicode normalization
    value = unicodedata.normalize("NFKC", value)

    # Remove null bytes and unsafe control characters
    value = value.replace("\x00", "")
    value = "".join(
        ch for ch in value
        if ch in ("\n", "\t") or ord(ch) >= 32
    )

    # Length enforcement
    if len(value) > MAX_TEXT_LENGTH:
        raise InputSanitizationError(
            f"Input exceeds maximum allowed length of {MAX_TEXT_LENGTH} characters."
        )

    # Strip script blocks completely
    value = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip remaining HTML tags
    value = re.sub(r"<[^>]+>", " ", value)

    # Unescape harmless HTML entities
    value = html.unescape(value)

    # Normalize whitespace
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def sanitize_untrusted_llm_content(text: str) -> str:
    """Sanitize text bound for LLM consumption, neutralising prompt injection patterns.

    Applies standard security sanitization and filters out known prompt-injection
    phrases by replacing them with [UNTRUSTED_CONTENT_FILTERED].
    """
    cleaned = sanitize_user_text(text)

    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = re.sub(
            pattern,
            "[UNTRUSTED_CONTENT_FILTERED]",
            cleaned,
            flags=re.IGNORECASE,
        )

    return cleaned
