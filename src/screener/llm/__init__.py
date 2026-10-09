"""LLM extraction, schemas, grounding, and provider implementations."""

from screener.llm.base import LLMClient
from screener.llm.schemas import ResumeExtraction, SCHEMA_VERSION
from screener.llm.prompts import PROMPT_VERSION, build_extraction_prompt
from screener.llm.grounding import validate_grounding
from screener.llm.cache import LLMCache
from screener.llm.fake import FakeLLM
from screener.llm.gemini import GeminiClient
from screener.config import AppConfig
from screener.errors import LLMError


def create_llm_client(config: AppConfig) -> LLMClient:
    """Create an LLM client instance based on configuration."""
    if not config.runtime.llm_enabled:
        return FakeLLM()

    provider = config.runtime.llm_provider.lower()
    api_key = config.runtime.llm_api_key

    if not api_key:
        raise LLMError(f"Missing API key for LLM provider: {provider}")

    if provider == "gemini":
        return GeminiClient(
            api_key=api_key,
            model=config.runtime.llm_model,
            timeout_seconds=config.runtime.llm_timeout_seconds,
        )
    else:
        # Default or fallback
        return GeminiClient(
            api_key=api_key,
            model=config.runtime.llm_model,
            timeout_seconds=config.runtime.llm_timeout_seconds,
        )


__all__ = [
    "LLMClient",
    "ResumeExtraction",
    "SCHEMA_VERSION",
    "PROMPT_VERSION",
    "build_extraction_prompt",
    "validate_grounding",
    "LLMCache",
    "FakeLLM",
    "GeminiClient",
    "create_llm_client",
]
