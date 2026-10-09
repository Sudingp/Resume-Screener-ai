"""Concrete LLM client for Google Gemini REST API using httpx."""

import asyncio
import json
import secrets
from typing import Any, Dict, Optional
import httpx
from screener.errors import LLMError
from screener.llm.base import LLMClient
from screener.llm.prompts import SYSTEM_PROMPT
from screener.models import ResumeExtraction


class GeminiClient(LLMClient):
    """Client for Google Gemini API with native structured JSON output and retry logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        timeout_seconds: float = 60.0,
    ):
        if not api_key:
            raise LLMError("Gemini API key is required when using Gemini provider")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout_seconds

    async def extract(self, prompt: str) -> ResumeExtraction:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )

        headers = {
            "Content-Type": "application/json",
        }

        # Build request with structured JSON configuration
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}],
            },
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code != 200:
                    error_detail = resp.text[:200]
                    raise LLMError(
                        f"Gemini API returned status {resp.status_code}: {error_detail}",
                        provider="gemini",
                    )

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMError("Gemini returned empty candidates", provider="gemini")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMError("Gemini candidate has no parts", provider="gemini")

                raw_json_str = parts[0].get("text", "")
                parsed = json.loads(raw_json_str)
                return ResumeExtraction.model_validate(parsed)

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = LLMError(f"Network error communicating with Gemini: {e}", provider="gemini")
            except (json.JSONDecodeError, ValueError) as e:
                last_error = LLMError(f"Gemini output failed schema validation: {e}", provider="gemini")
            except LLMError as e:
                last_error = e

            if attempt < max_attempts:
                # Exponential backoff with cryptographically safe jitter
                jitter = secrets.SystemRandom().uniform(0.1, 0.3)
                sleep_time = (0.5 * (2 ** attempt)) + jitter
                await asyncio.sleep(sleep_time)

        raise last_error or LLMError("LLM extraction failed after retries", provider="gemini")
