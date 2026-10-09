"""Unit tests for LLM layer, structured extraction, grounding, and caching."""

import pytest
from pathlib import Path
from screener.llm.base import LLMClient
from screener.llm.fake import FakeLLM
from screener.llm.grounding import validate_grounding
from screener.llm.cache import LLMCache
from screener.llm.prompts import build_extraction_prompt
from screener.models import (
    ResumeExtraction,
    ProjectEvidence,
    Signal,
    SCHEMA_VERSION,
)
from screener.errors import LLMError


@pytest.mark.asyncio
async def test_fake_llm_extraction_and_call_count():
    fake = FakeLLM()
    res = await fake.extract("some prompt")
    assert res.candidate_name == "Test Candidate"
    assert fake.call_count == 1

    res2 = await fake.extract("another prompt")
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_fake_llm_error_handling():
    fake = FakeLLM(should_fail=True)
    with pytest.raises(LLMError, match="simulated provider failure"):
        await fake.extract("prompt")


def test_grounding_drops_ungrounded_quotes():
    resume_text = (
        "Sarah Connor\n"
        "Built high throughput REST APIs with FastAPI and optimized PostgreSQL queries."
    )

    # Extraction with 1 grounded signal and 1 fabricated / hallucinated signal
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Sarah Connor",
        skills=["FastAPI"],
        projects=[
            ProjectEvidence(
                name="API Service",
                summary="High throughput API",
                technologies=["FastAPI"],
                is_ai_project=True,
                capabilities=["retrieval_rag"],
                quotes=["Fabricated quote about multi-agent systems not in resume"],
            )
        ],
        signals=[
            Signal(
                key="fastapi",
                context="applied",
                quote="Built high throughput REST APIs with FastAPI",
            ),
            Signal(
                key="redis",
                context="applied",
                quote="Configured enterprise Redis cluster with sentinel failover",
            ),
        ],
    )

    validated, warnings = validate_grounding(extraction, resume_text)

    # The ungrounded redis signal must be dropped
    assert len(validated.signals) == 1
    assert validated.signals[0].key == "fastapi"

    # The project with only ungrounded quote must lose its capabilities and is_ai_project flag
    assert len(validated.projects) == 1
    assert validated.projects[0].capabilities == []
    assert not validated.projects[0].is_ai_project
    assert any("ungrounded_quotes" in w for w in warnings)


def test_disk_cache_hit_and_atomic_write(tmp_path):
    cache = LLMCache(cache_dir=tmp_path)
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Cached Candidate",
        skills=["Python"],
    )

    # Miss
    assert cache.get("model_a", "v1", "v1", "hash123") is None

    # Set
    cache.set("model_a", "v1", "v1", "hash123", extraction)

    # Hit
    cached = cache.get("model_a", "v1", "v1", "hash123")
    assert cached is not None
    assert cached.candidate_name == "Cached Candidate"


def test_disk_cache_corrupt_entry_ignored(tmp_path):
    cache = LLMCache(cache_dir=tmp_path)
    # Write garbage directly to key file
    key = cache._make_key("model_a", "v1", "v1", "corrupt_hash")
    corrupt_file = tmp_path / f"{key}.json"
    corrupt_file.write_text("{{corrupted json", encoding="utf-8")

    # Should ignore corrupt file and return None safely
    assert cache.get("model_a", "v1", "v1", "corrupt_hash") is None
