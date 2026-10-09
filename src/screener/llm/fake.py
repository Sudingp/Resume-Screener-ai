"""Scriptable Fake LLM client for deterministic, offline testing."""

import asyncio
from typing import Dict, List, Optional
from screener.errors import LLMError
from screener.llm.base import LLMClient
from screener.models import ResumeExtraction, ProjectEvidence, Signal, SCHEMA_VERSION


class FakeLLM(LLMClient):
    """Fake LLM client supporting scripted responses, call tracking, and error injection."""

    def __init__(
        self,
        default_extraction: Optional[ResumeExtraction] = None,
        scripted_extractions: Optional[Dict[str, ResumeExtraction]] = None,
        should_fail: bool = False,
        fail_times: int = 0,
        delay_seconds: float = 0.0,
        invalid_json_first: bool = False,
    ):
        self.call_count = 0
        self.should_fail = should_fail
        self.fail_times = fail_times
        self.failed_so_far = 0
        self.delay_seconds = delay_seconds
        self.invalid_json_first = invalid_json_first
        self.scripted_extractions = scripted_extractions or {}

        if default_extraction is None:
            self.default_extraction = ResumeExtraction(
                schema_version=SCHEMA_VERSION,
                candidate_name="Test Candidate",
                email="test@example.com",
                skills=["Python", "FastAPI"],
                projects=[],
                signals=[],
                strengths=["Good general background"],
                concerns=[],
            )
        else:
            self.default_extraction = default_extraction

    async def extract(self, prompt: str) -> ResumeExtraction:
        self.call_count += 1

        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        if self.should_fail:
            raise LLMError("FakeLLM simulated provider failure")

        if self.failed_so_far < self.fail_times:
            self.failed_so_far += 1
            raise LLMError(f"FakeLLM transient failure ({self.failed_so_far}/{self.fail_times})")

        # Check scripted extractions by keywords in prompt
        for kw, ext in self.scripted_extractions.items():
            if kw in prompt:
                return ext

        return self.default_extraction
