"""Base protocol and interfaces for LLM clients."""

from typing import Protocol, runtime_checkable
from screener.models import ResumeExtraction


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM extraction providers."""

    async def extract(self, prompt: str) -> ResumeExtraction:
        """
        Extract structured observations from resume prompt text.
        Never produces scores or decides eligibility.
        """
        ...
