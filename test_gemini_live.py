import os
import httpx
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("LLM_MODEL_NAME", "gemini-3.6-flash")

print("=" * 60)
print("TESTING LIVE GEMINI API (NO MOCK)")
print("=" * 60)

if not api_key:
    print("[ERROR] GEMINI_API_KEY is not set in .env!")
    exit(1)

print(f"[1] Key in .env detected (length: {len(api_key)})")
print(f"[2] Testing model endpoint: {model_name} ...")

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": api_key,
}
payload = {
    "contents": [{"parts": [{"text": "Hello Gemini! Confirm in 1 sentence that you are live and operational."}]}]
}

try:
    resp = httpx.post(url, headers=headers, json=payload, timeout=20.0)
    print(f"    HTTP Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"    >>> SUCCESS! Live Gemini response: {text.strip()}")
    else:
        try:
            err_msg = resp.json().get("error", {}).get("message", "")
        except Exception:
            err_msg = resp.text
        print(f"    >>> Failed with status {resp.status_code}: {err_msg}")
except Exception as e:
    print(f"    >>> Network error: {e}")

print("=" * 60)
