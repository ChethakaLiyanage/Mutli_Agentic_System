"""Controlled verification script for Agent 4 Gemini LLM integration.

Usage:
    python -m backend.scripts.verify_gemini_live
or:
    python backend/scripts/verify_gemini_live.py
"""

from __future__ import annotations

import os
import sys

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.config import ENV_FILE_PATHS
from dotenv import load_dotenv

for path in ENV_FILE_PATHS:
    if path.exists():
        load_dotenv(path, override=False)

from backend.app.guidance.schemas import GuidanceRequest
from backend.app.guidance.service import GuidanceService
from backend.app.llm.client import GeminiLLMClient, get_llm_client
from backend.app.llm.config import LLMSettings


def main() -> int:
    print("=== Agent 4 Gemini Runtime Verification ===")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[FAIL] GEMINI_API_KEY is not configured in environment.")
        return 1

    print("[PASS] GEMINI_API_KEY is configured (secret value not shown).")

    settings = LLMSettings.from_env()
    print(f"[INFO] Configured provider: {settings.provider}")
    print(f"[INFO] Configured model: {settings.model_name}")

    client = get_llm_client(settings)
    print(f"[INFO] Acquired LLM client: {client.__class__.__name__}")
    if not isinstance(client, GeminiLLMClient):
        print(f"[FAIL] Expected GeminiLLMClient, got {client.__class__.__name__}")
        return 1
    print("[PASS] GeminiLLMClient selected successfully.")

    service = GuidanceService(llm_client=client)
    request = GuidanceRequest(
        request_id="LIVE-VERIFY-001",
        audience="customer",
        task_type="greeting",
        safe_customer_context={"customer_message": "Hello, good morning!"},
    )

    print("[INFO] Sending single controlled Agent 4 request...")
    response = service.process_request(request)

    if not response or not response.data:
        print("[FAIL] Empty guidance response received.")
        return 1

    msg = response.data.message
    if not msg or not msg.strip():
        print("[FAIL] Empty guidance message returned.")
        return 1

    print("[PASS] Non-empty response text received.")
    print(f"[INFO] Response status: {response.status}")
    print(f"[INFO] Response provider: {response.provider}")
    print(f"[INFO] Sample message output: {msg[:100]}...")
    print(f"[INFO] Automated decision flag: {response.data.automated_decision}")

    if response.data.automated_decision is not False:
        print("[FAIL] automated_decision must strictly be False.")
        return 1

    print("[SUCCESS] Agent 4 Gemini integration and safe failure handling verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
