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

        # Scenario: final_decision_explanation
        if "TASK: Explain the final decision" in user_prompt:
            if "APPROVED" in user_prompt:
                return {
                    "message": (
                        "We are pleased to inform you that your claim has been approved by the claims officer. "
                        "The payment processing has been initiated in accordance with the verified settlement amount."
                    ),
                    "next_steps": [
                        "Verify your bank details in the customer portal",
                        "Allow 2-3 business days for fund disbursement",
                    ],
                    "evidence_used": evidence_used,
                    "requires_human_review": False,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }
            elif "REJECTED" in user_prompt:
                return {
                    "message": (
                        "The claims officer has completed the review of your claim and determined that it cannot be approved. "
                        "This decision is based on the specific terms and exclusions outlined in your policy schedule."
                    ),
                    "next_steps": [
                        "Review the officer's written explanation in your claim file",
                        "Contact claims customer support if you wish to file a formal appeal",
                    ],
                    "evidence_used": evidence_used,
                    "requires_human_review": False,
                    "insufficient_evidence": False,
                    "automated_decision": False,
                }

        # Scenario: required_documents
        if "TASK: List the required documents" in user_prompt:
            missing_docs = []
            missing_match = re.search(r"Missing Documents:\s*([^\n]+)", user_prompt)
            if missing_match:
                missing_docs = [d.strip() for d in missing_match.group(1).split(",") if d.strip()]

            doc_text = "police report and repair estimate" if not missing_docs else ", ".join(missing_docs)
            return {
                "message": (
                    f"To process your motor insurance claim, the required documentation includes {doc_text}. "
                    "Please upload any outstanding documents to proceed."
                ),
                "next_steps": [
                    f"Upload missing document: {doc}" for doc in (missing_docs or ["Repair estimate", "Police report"])
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
            return {
                "message": (
                    f"Thank you for submitting your claim details. To assist us in reviewing your request, "
                    f"could you please clarify the following missing details: {missing_info}?"
                ),
                "next_steps": [
                    f"Provide clarification on: {missing_info}",
                    "Submit response through the claims portal",
                ],
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

        # Default / Coverage explanation
        return {
            "message": (
                "Based on the retrieved policy evidence, accidental damage may be eligible for coverage, "
                "subject to the policy terms, applicable deductibles, and final verification by a claims officer."
            ),
            "next_steps": [
                "Submit official repair estimate from an authorized garage",
                "Ensure police report is provided if applicable",
            ],
            "evidence_used": evidence_used,
            "requires_human_review": False,
            "insufficient_evidence": False,
            "automated_decision": False,
        }


class GeminiLLMClient(BaseLLMClient):
    """Direct HTTP client for Google Gemini API."""

    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def generate_json(self, system_instruction: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMClientError("GEMINI_API_KEY environment variable is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.model_name}:generateContent?key={self.api_key}"
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
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
        except Exception as err:
            logger.error("Gemini API call failed: %s", err)
            raise LLMClientError(f"Gemini API generation error: {err}") from err


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
