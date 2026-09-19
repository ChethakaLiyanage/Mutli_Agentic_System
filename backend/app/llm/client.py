"""LLM client abstraction and implementations for Agent 4.

Provides BaseLLMClient interface, MockLLMClient (for offline deterministic execution & testing),
and live API clients using HTTP transport.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any
import httpx
from backend.app.llm.config import LLMSettings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Raised when LLM invocation or JSON parsing fails."""
    pass


class BaseLLMClient(ABC):
    """Abstract interface for LLM client integration."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    @abstractmethod
    def generate_json(self, system_instruction: str, user_prompt: str) -> dict[str, Any]:
        """Generate structured JSON response conforming to system instructions."""
        pass


class MockLLMClient(BaseLLMClient):
    """Deterministic, rule-grounded mock client for offline tests and evaluation.

    Extracts facts directly from prompt context to produce 100% grounded responses
    without making external API requests.
    """

    def generate_json(self, system_instruction: str, user_prompt: str) -> dict[str, Any]:
        is_customer = "AUDIENCE: CUSTOMER" in system_instruction
        is_reviewer = "AUDIENCE: CLAIMS OFFICER" in system_instruction

        # Extract evidence citations if present
        evidence_matches = re.findall(
            r'<document id="([^"]+)" name="([^"]+)" section="([^"]+)">',
            user_prompt,
        )
        evidence_used = [
            f"{doc_name}#{section}" for _, doc_name, section in evidence_matches
        ]
        evidence_contents = re.findall(
            r'<document[^>]*>\s*(.*?)\s*</document>', user_prompt, re.DOTALL
        )

        if "TASK: Give a brief, friendly greeting" in user_prompt:
            return {
                "message": (
                    "Hi! I can help with claims, policy questions, coverage, "
                    "required documents, or claim status. What can I help you with?"
                ),
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        if "TASK: Confirm that the customer can begin a motor claim" in user_prompt:
            return {
                "message": (
                    "Yes, you can report a motor claim here. Tell me what happened "
                    "to your vehicle, when it happened, and where it happened."
                ),
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        if "TASK: Tell the customer that the claim is waiting" in user_prompt:
            return {
                "message": "Your claim is now waiting for review by a claims officer.",
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": True,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        if "TASK: Explain that a claims officer must help" in user_prompt:
            return {
                "message": "A claims officer needs to help with the next step of your claim.",
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        if "TASK: Give a short, customer-safe technical failure" in user_prompt:
            return {
                "message": "I'm sorry, I couldn't continue this request safely. Please try again.",
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        if "TASK: Explain briefly that the available controlled documents do not contain enough information" in user_prompt:
            return {
                "message": (
                    "I couldn't find enough information in the available policy documents "
                    "to confirm the answer reliably."
                ),
                "next_steps": [
                    "Try asking another motor insurance question",
                    "Check your policy documents for more details",
                ],
                "evidence_used": [],
                "requires_human_review": is_reviewer,
                "insufficient_evidence": True,
                "automated_decision": False,
            }

        if "TASK: Briefly explain the customer-safe workflow progress" in user_prompt:
            status_match = re.search(
                r"Authoritative Workflow Status:\s*([^\n]+)", user_prompt
            )
            status = status_match.group(1).strip() if status_match else ""
            if status == "awaiting_human_review":
                message = "Your claim is now waiting for review by a claims officer."
            elif status == "manual_assistance_required":
                message = (
                    "Your claim details were saved, but a claims officer needs "
                    "to help with the next step."
                )
            else:
                message = (
                    "Thanks, I have the main incident details and your claim can "
                    "now continue for review."
                )
            return {
                "message": message,
                "next_steps": [],
                "evidence_used": [],
                "requires_human_review": status == "awaiting_human_review",
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        # Scenario: final_decision_explanation
        if (
            "TASK: Explain the final decision" in user_prompt
            or "TASK: Explain exactly the verified human decision" in user_prompt
        ):
            if "APPROVED" in user_prompt:
                return {
                    "message": (
                        "A claims officer reviewed your claim and recorded an approved decision."
                    ),
                    "next_steps": [
                        "Keep your claim reference available for future correspondence",
                    ],
                    "evidence_used": evidence_used,
                    "requires_human_review": False,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }
            elif "REJECTED" in user_prompt:
                reason_match = re.search(
                    r"Customer-safe decision reason:\s*([^\n]+)", user_prompt
                )
                reason = reason_match.group(1).strip() if reason_match else None
                return {
                    "message": (
                        "A claims officer reviewed the claim and recorded a rejected decision."
                        + (f" The recorded reason is: {reason}" if reason else "")
                    ),
                    "next_steps": [
                        "Contact claims support if you need clarification about the recorded decision",
                    ],
                    "evidence_used": evidence_used,
                    "requires_human_review": False,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }
            elif "INFO_REQUESTED" in user_prompt:
                reason_match = re.search(
                    r"Customer-safe decision reason:\s*([^\n]+)", user_prompt
                )
                reason = reason_match.group(1).strip() if reason_match else "Additional information is required."
                return {
                    "message": f"A claims officer requested additional information: {reason}",
                    "next_steps": ["Provide the requested information through the claims support channel"],
                    "evidence_used": evidence_used,
                    "requires_human_review": False,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }
            elif "ESCALATED" in user_prompt:
                return {
                    "message": "A claims officer escalated your claim for additional specialist review. No final approval or rejection has been recorded.",
                    "next_steps": ["Wait for the specialist review team to contact you"],
                    "evidence_used": evidence_used,
                    "requires_human_review": True,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }

        # Scenario: required_documents
        if "TASK: List the required documents" in user_prompt:
            missing_docs = []
            missing_match = re.search(r"Missing Documents:\s*([^\n]+)", user_prompt)
            if missing_match:
                missing_docs = [d.strip() for d in missing_match.group(1).split(",") if d.strip()]

            evidence_text = " ".join(evidence_contents).strip()
            grounded_documents = [
                label for label in (
                    "Police report", "Repair estimate", "Driving license copy",
                    "Vehicle registration", "Claim form", "Damage photos",
                )
                if label.lower() in evidence_text.lower()
            ]
            doc_text = ", ".join(missing_docs or grounded_documents)
            return {
                "message": (
                    f"The retrieved claims guidance identifies these documents: {doc_text}."
                ),
                "next_steps": [
                    f"Provide requested document: {doc}" for doc in (missing_docs or grounded_documents)
                ],
                "evidence_used": evidence_used,
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        # Scenario: claim_status
        if "TASK: Formulate a neutral and informative claim status message" in user_prompt:
            status_match = re.search(r"Verified Claim Status:\s*([^\n]+)", user_prompt)
            status = status_match.group(1).strip() if status_match else "under_review"
            return {
                "message": (
                    f"Your motor insurance claim is currently recorded as '{status}'. "
                    "Our claims assessment team is actively reviewing your submitted details and supporting evidence."
                ),
                "next_steps": [
                    "Check your email and customer portal periodically for status updates",
                    "A claims officer will contact you if additional details are required",
                ],
                "evidence_used": evidence_used,
                "requires_human_review": True,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        # Scenario: clarification_question
        if "TASK: Formulate polite, targeted clarification questions" in user_prompt:
            missing_info_match = re.search(r"Missing Claim Information:\s*([^\n]+)", user_prompt)
            missing_info = missing_info_match.group(1).strip() if missing_info_match else "incident location"
            missing_fields = [
                field.strip() for field in missing_info.split(",") if field.strip()
            ]
            date_match = re.search(
                r'"date_text":\s*"([^"]+)"', user_prompt
            )
            if missing_fields == ["location"]:
                prefix = (
                    f"I've got that the accident happened {date_match.group(1)}. "
                    if date_match
                    else "I've got the incident details. "
                )
                message = prefix + "Where did it happen?"
            else:
                labels = {
                    "incident_type": "what happened to your vehicle",
                    "incident_date": "when it happened",
                    "location": "where it happened",
                }
                requested = [labels[item] for item in missing_fields if item in labels]
                message = (
                    "Could you tell me " + ", and ".join(requested) + "?"
                    if requested
                    else "Could you clarify what you need help with?"
                )
            return {
                "message": message,
                "next_steps": [],
                "evidence_used": evidence_used,
                "requires_human_review": False,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        # Scenario: reviewer_summary or reviewer audience
        if "TASK: Generate a concise decision-support executive summary" in user_prompt or is_reviewer:
            risk_match = re.search(r"Risk Level:\s*([^\n]+)", user_prompt)
            risk_level = risk_match.group(1).strip() if risk_match else "LOW"
            return {
                "message": (
                    "Executive claim dossier generated for claims officer review. "
                    "All extracted facts, relevant policy clauses, and risk triage indicators are organized below."
                ),
                "next_steps": [
                    "Verify vehicle registration and incident date against supporting documents",
                    "Conduct manual coverage confirmation prior to final settlement decision",
                ],
                "evidence_used": evidence_used,
                "requires_human_review": True,
                "insufficient_evidence": False,
                "automated_decision": False,
                "reviewer_summary": {
                    "claim_overview": "Motor accident claim submitted for evaluation.",
                    "policy_findings": [f"Applicable section: {src}" for src in evidence_used] or ["Standard motor policy terms apply."],
                    "risk_observations": [f"Risk level evaluated as {risk_level} by triage engine."],
                    "missing_items": ["Verify outstanding estimate receipts if applicable."],
                    "reviewer_action_points": ["Conduct manual policy coverage check", "Inspect document dates"],
                },
            }

        # Scenario: fraud_indicator_explanation
        if "TASK: Translate the technical risk indicators" in user_prompt:
            return {
                "message": (
                    "The fraud-triage component identified specific risk indicators requiring human inspection. "
                    "The incident dates and repair costs should be verified against external official documents."
                ),
                "next_steps": [
                    "Cross-reference accident date with police report timestamp",
                    "Verify repair estimate against standard garage labor rates",
                ],
                "evidence_used": evidence_used,
                "requires_human_review": True,
                "insufficient_evidence": False,
                "automated_decision": False,
            }

        generic_scope = "specific_policy_not_available" in user_prompt
        evidence_summary = " ".join(evidence_contents).strip()
        return {
            "message": (
                ("The available material provides general policy information and does not confirm coverage under your specific policy. " if generic_scope else "")
                + "Based on the retrieved policy evidence: "
                + evidence_summary
            ),
            "next_steps": [
                "Review the cited policy material and contact claims support if clarification is needed",
            ],
            "evidence_used": evidence_used,
            "requires_human_review": False,
            "insufficient_evidence": False,
            "automated_decision": False,
        }


class GeminiLLMClient(BaseLLMClient):
    """Direct HTTP client for Google Gemini API."""

    _FALLBACK_STATUS_CODES = frozenset({429, 503})

    def __init__(
        self,
        settings: LLMSettings,
        *,
        grounded_fallback: BaseLLMClient | None = None,
    ) -> None:
        super().__init__(settings)
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.grounded_fallback = grounded_fallback or MockLLMClient(
            settings.model_copy(update={"provider": "mock"})
        )

    def generate_json(self, system_instruction: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMClientError("GEMINI_API_KEY environment variable is not configured.")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.model_name}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": self.settings.temperature,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
        except httpx.HTTPStatusError as err:
            status_code = err.response.status_code
            if status_code in self._FALLBACK_STATUS_CODES:
                logger.warning(
                    "Gemini temporarily unavailable (HTTP %s); using grounded fallback",
                    status_code,
                )
                return self.grounded_fallback.generate_json(
                    system_instruction, user_prompt
                )
            logger.error("Gemini API returned HTTP %s", status_code)
            raise LLMClientError(
                f"Gemini API generation failed with HTTP {status_code}"
            ) from err
        except Exception as err:
            logger.error("Gemini API generation failed: %s", type(err).__name__)
            raise LLMClientError("Gemini API generation failed") from err


class OpenAILLMClient(BaseLLMClient):
    """Direct HTTP client for OpenAI-compatible Chat Completions API."""

    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def generate_json(self, system_instruction: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMClientError("OPENAI_API_KEY environment variable is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"]
                return json.loads(raw_text)
        except Exception as err:
            logger.error("OpenAI API call failed: %s", err)
            raise LLMClientError(f"OpenAI API generation error: {err}") from err


def get_llm_client(settings: LLMSettings | None = None) -> BaseLLMClient:
    """Factory function to acquire configured LLM client."""
    if settings is None:
        settings = LLMSettings.from_env()

    if settings.provider == "gemini":
        return GeminiLLMClient(settings)
    elif settings.provider == "openai":
        return OpenAILLMClient(settings)
    else:
        return MockLLMClient(settings)
