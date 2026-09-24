"""Deterministic authorization screening for protected customer resources."""

from __future__ import annotations

from dataclasses import dataclass
import re


_OTHER_CUSTOMER_REFERENCE = re.compile(
    r"\b(?:another|other|different)\s+customers?(?:\s*['\N{RIGHT SINGLE QUOTATION MARK}]s?)?\b"
    r"|\bsomeone\s+else(?:\s*['\N{RIGHT SINGLE QUOTATION MARK}]s)?\b",
    re.IGNORECASE,
)
_EXPLICIT_CUSTOMER_ID = re.compile(
    # Require an identifier-shaped token (a digit, dash, or underscore) so
    # ordinary phrases such as "customer policy" are not mistaken for an ID.
    r"\b(?:customer|user)\s+(?:id\s+)?"
    r"(?P<identifier>(?=[a-z0-9_-]*(?:\d|[-_]))[a-z0-9][a-z0-9_-]{2,})\b",
    re.IGNORECASE,
)

_RESOURCE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "claim_documents",
        (
            "claim document",
            "claim documents",
            "uploaded document",
            "uploaded documents",
            "uploaded file",
            "uploaded files",
            "damage photo",
            "damage photos",
        ),
    ),
    ("claim", ("claim", "claim status", "claim details", "claim information")),
    (
        "policy",
        (
            "policy",
            "coverage",
            "cover",
            "expiry date",
            "expiration date",
            "insurance details",
        ),
    ),
    (
        "personal_information",
        (
            "personal information",
            "account information",
            "account details",
            "address",
            "email",
            "phone number",
            "registration number",
        ),
    ),
)

_ALLOWED_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "policy": ("own_policy_information", "own_policy_coverage"),
    "claim": ("own_claim_information", "own_claim_status"),
    "claim_documents": ("own_claim_information", "own_claim_documents"),
    "personal_information": ("own_account_information",),
}


@dataclass(frozen=True)
class AuthorizationDenial:
    """Customer-safe authorization outcome; contains no protected record data."""

    requested_resource_type: str
    allowed_alternatives: tuple[str, ...]
    reason: str = "ownership_required"
    ownership: str = "other_customer"

    def to_safe_context(self) -> dict[str, object]:
        return {
            "authorization_result": "denied",
            "requested_resource_type": self.requested_resource_type,
            "reason": self.reason,
            "ownership": self.ownership,
            "allowed_alternatives": list(self.allowed_alternatives),
            "authenticated_customer": True,
        }


def deny_cross_customer_resource_request(
    text: str,
    *,
    authenticated_user_id: str,
) -> AuthorizationDenial | None:
    """Deny requests that explicitly target another customer's protected data.

    This check runs before retrieval. It only classifies the requested resource
    and ownership relationship; it never looks up or returns the target record.
    """

    normalized = " ".join(text.casefold().split())
    targets_other_customer = bool(_OTHER_CUSTOMER_REFERENCE.search(normalized))

    explicit_id = _EXPLICIT_CUSTOMER_ID.search(normalized)
    if explicit_id is not None:
        requested_id = explicit_id.group("identifier").casefold()
        targets_other_customer = requested_id != authenticated_user_id.casefold()

    if not targets_other_customer:
        return None

    resource_type = next(
        (
            name
            for name, terms in _RESOURCE_TERMS
            if any(
                re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized)
                for term in terms
            )
        ),
        None,
    )
    if resource_type is None:
        return None

    return AuthorizationDenial(
        requested_resource_type=resource_type,
        allowed_alternatives=_ALLOWED_ALTERNATIVES[resource_type],
    )
