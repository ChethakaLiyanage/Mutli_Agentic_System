"""Privacy-context routing and minimum-necessary data classification."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


PrivacyRequestType = Literal[
    "sensitive_context_recall",
    "sensitive_data_disclosure",
]


_DISCLOSURE_ACTION = re.compile(
    r"\b(?:list|repeat|print|show|tell|give|provide|reveal|display|read|"
    r"recall|enumerate|return|output)\b",
    re.IGNORECASE,
)
_MEMORY_CONTEXT = re.compile(
    r"\b(?:remember|retained|stored|earlier|previously|before|prior|"
    r"conversation|chat|messages?|provided|gave|told|know\s+about\s+me)\b",
    re.IGNORECASE,
)
_SENSITIVE_SCOPE = re.compile(
    r"\b(?:personal|private|sensitive|identifying|identifiers?|identity|"
    r"contact|email|e-mail|phone|telephone|mobile|address|vehicle\s+"
    r"(?:registration|number)|registration\s+number|policy\s+(?:number|"
    r"information|details)|claim\s+(?:number|information|details)|"
    r"customer-specific)\b",
    re.IGNORECASE,
)
_BULK_SCOPE = re.compile(
    r"\b(?:all|every|everything|anything|full|complete|entire)\b",
    re.IGNORECASE,
)
_SELF_REFERENCE = re.compile(
    r"\b(?:my|me|about\s+me|this\s+(?:conversation|chat)|"
    r"i\s+(?:provided|gave|told|shared))\b",
    re.IGNORECASE,
)

_EMAIL_VALUE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_VALUE = re.compile(r"(?<!\d)(?:\+?94|0)?7\d{8}(?!\d)")
_LABELED_IDENTIFIER_VALUE = re.compile(
    r"\b(?:vehicle\s+(?:registration|number)|registration\s+number|"
    r"policy\s+number|claim\s+number)\s*(?:is|:|=)?\s*"
    r"[A-Z0-9][A-Z0-9 -]{2,20}\b",
    re.IGNORECASE,
)
_PERSONAL_DISCLOSURE = re.compile(
    r"\b(?:my|test)\s+(?:email|e-mail|phone|telephone|mobile|address|"
    r"vehicle\s+(?:registration|number)|registration\s+number|"
    r"policy\s+number|claim\s+number)\b",
    re.IGNORECASE,
)

_LEGITIMATE_TASK_LANGUAGE = re.compile(
    r"\b(?:use|apply|attach|link)\b.{0,50}\b(?:current|active|this|my)\s+claim\b"
    r"|\b(?:submit|file|lodge|make|open|report)\b.{0,25}\bclaim\b"
    r"|\b(?:crash(?:ed)?|collid(?:e|ed|ing)|accident|hit|damag(?:e|ed)|"
    r"shatter(?:ed)?|stolen|theft|break[ -]?in|flood(?:ed|ing)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PrivacyContextDecision:
    """A value-free routing decision suitable for Agent 4."""

    request_type: PrivacyRequestType
    disclosure: Literal["restricted", "minimized"]
    reason: Literal["minimum_necessary", "no_current_insurance_task"]
    safe_alternatives: tuple[str, ...]

    @property
    def guidance_task(self) -> Literal[
        "sensitive_context_recall",
        "sensitive_context_notice",
    ]:
        if self.request_type == "sensitive_context_recall":
            return "sensitive_context_recall"
        return "sensitive_context_notice"

    def to_safe_context(self) -> dict[str, object]:
        return {
            "privacy_result": "restricted",
            "request_type": self.request_type,
            "disclosure": self.disclosure,
            "reason": self.reason,
            "safe_alternatives": list(self.safe_alternatives),
            "authenticated_customer": True,
        }


def is_sensitive_context_recall(text: str) -> bool:
    """Return whether a message asks to reproduce retained personal context.

    Detection combines independent semantic features rather than matching any
    complete test phrase. Legitimate use verbs such as ``use`` or ``apply`` are
    deliberately not disclosure actions.
    """

    normalized = " ".join(text.split())
    has_action = bool(_DISCLOSURE_ACTION.search(normalized))
    has_memory = bool(_MEMORY_CONTEXT.search(normalized))
    has_sensitive_scope = bool(_SENSITIVE_SCOPE.search(normalized))
    has_bulk_scope = bool(_BULK_SCOPE.search(normalized))
    has_self_reference = bool(_SELF_REFERENCE.search(normalized))
    has_recall_question = bool(
        re.search(r"\b(?:what|which)\b", normalized, re.IGNORECASE)
        and has_memory
    )

    return (
        (has_action or has_recall_question)
        and has_self_reference
        and (
            (has_memory and (has_sensitive_scope or has_bulk_scope))
            or (
                has_sensitive_scope
                and bool(re.search(r"\b(?:repeat|recall|print)\b", normalized, re.IGNORECASE))
            )
        )
    )


def is_standalone_sensitive_disclosure(text: str) -> bool:
    """Detect supplied PII that is not tied to a legitimate insurance task."""

    if _LEGITIMATE_TASK_LANGUAGE.search(text):
        return False
    has_sensitive_value = bool(
        _EMAIL_VALUE.search(text)
        or _PHONE_VALUE.search(text)
        or _LABELED_IDENTIFIER_VALUE.search(text)
    )
    return has_sensitive_value and bool(_PERSONAL_DISCLOSURE.search(text))


def classify_privacy_context(text: str) -> PrivacyContextDecision | None:
    """Classify privacy-only turns before insurance intake or retrieval."""

    if is_sensitive_context_recall(text):
        return PrivacyContextDecision(
            request_type="sensitive_context_recall",
            disclosure="restricted",
            reason="minimum_necessary",
            safe_alternatives=(
                "continue_current_insurance_request",
                "provide_relevant_own_policy_information",
                "provide_relevant_own_claim_information",
            ),
        )
    if is_standalone_sensitive_disclosure(text):
        return PrivacyContextDecision(
            request_type="sensitive_data_disclosure",
            disclosure="minimized",
            reason="no_current_insurance_task",
            safe_alternatives=(
                "continue_current_insurance_request",
                "start_claim_with_relevant_details",
                "ask_policy_or_claim_question",
            ),
        )
    return None


def minimized_workflow_text(decision: PrivacyContextDecision) -> str:
    """Return a non-PII persistence marker for a privacy-only workflow."""

    return f"[privacy context minimized: {decision.request_type}]"
