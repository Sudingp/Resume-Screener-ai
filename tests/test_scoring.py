"""Unit tests for deterministic scoring rubric, penalties, caps, and arithmetic."""

import pytest
from screener.config import load_config
from screener.models import (
    ResumeExtraction,
    ProjectEvidence,
    Signal,
    GitHubResult,
    SCHEMA_VERSION,
)
from screener.scoring.scorer import compute_scores


@pytest.fixture
def scoring_cfg():
    cfg = load_config()
    return cfg.scoring


def test_illustrative_arithmetic_79(scoring_cfg):
    """
    Blueprint Section E illustrative arithmetic test:
    - AI project depth: llm_call (6) + retrieval_rag (9) + tool_calling (9) + state_orchestration (7) + business_logic_data (4) = 35
    - Python & backend: python applied (8) + fastapi applied (7) + async_programming applied (5) + postgresql applied (5) = 25
    - Cloud: docker applied (4) + gcp skills_only (2) + deployment applied (3) = 9
    - GitHub: 8 points
    - Engineering depth: testing applied (1) + concurrency_failure_handling applied (1) = 2
    Total = 79.
    """
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Asha Rao",
        skills=["Python", "FastAPI", "GCP"],
        projects=[
            ProjectEvidence(
                name="AI Assistant",
                summary="Agentic system",
                technologies=["Python", "FastAPI"],
                is_ai_project=True,
                capabilities=[
                    "llm_call",
                    "retrieval_rag",
                    "tool_calling",
                    "state_orchestration",
                    "business_logic_data",
                ],
                quotes=["verbatim quote 1"],
            )
        ],
        signals=[
            Signal(key="python", context="applied", quote="Python quote"),
            Signal(key="fastapi", context="applied", quote="FastAPI quote"),
            Signal(key="async_programming", context="applied", quote="async quote"),
            Signal(key="postgresql", context="applied", quote="PostgreSQL quote"),
            Signal(key="docker", context="applied", quote="Docker quote"),
            Signal(key="gcp", context="skills_only", quote="GCP in skills"),
            Signal(key="deployment", context="applied", quote="Deployment quote"),
            Signal(key="testing", context="applied", quote="Testing quote"),
            Signal(key="concurrency_failure_handling", context="applied", quote="Failure handling quote"),
        ],
    )

    github_res = GitHubResult(
        status="ok",
        username="asharao",
        activity_points=4,
        repo_points=4,
    )

    total, breakdown, adjustments, evidence, strengths, concerns = compute_scores(
        extraction, github_res, scoring_cfg
    )

    assert breakdown.ai_project_depth == 35
    assert breakdown.python_backend == 25
    assert breakdown.cloud_fullstack == 9
    assert breakdown.github == 8
    assert breakdown.engineering_depth == 2
    assert total == 79
    assert len(adjustments) == 0


def test_category_caps(scoring_cfg):
    """Ensure that even if capabilities or signals exceed limits, category caps hold."""
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Max Candidate",
        skills=["All"],
        projects=[
            ProjectEvidence(
                name="Mega AI Project",
                summary="Everything",
                technologies=["All"],
                is_ai_project=True,
                capabilities=[
                    "llm_call",
                    "retrieval_rag",
                    "tool_calling",
                    "multi_agent",
                    "state_orchestration",
                    "evaluation_guardrails",
                    "business_logic_data",
                ],
                quotes=["quote"],
            )
        ],
        signals=[
            Signal(key="python", context="applied", quote="py"),
            Signal(key="fastapi", context="applied", quote="fa"),
            Signal(key="flask_django", context="applied", quote="dj"),
            Signal(key="async_programming", context="applied", quote="as"),
            Signal(key="postgresql", context="applied", quote="pg"),
            Signal(key="other_sql", context="applied", quote="sq"),
            Signal(key="redis", context="applied", quote="rd"),
            Signal(key="gcp", context="applied", quote="gcp"),
            Signal(key="other_cloud", context="applied", quote="aws"),
            Signal(key="docker", context="applied", quote="dk"),
            Signal(key="deployment", context="applied", quote="dp"),
            Signal(key="ci_cd", context="applied", quote="ci"),
            Signal(key="react_nextjs", context="applied", quote="rc"),
            Signal(key="testing", context="applied", quote="t"),
            Signal(key="architecture_design", context="applied", quote="a"),
            Signal(key="caching_queues", context="applied", quote="c"),
            Signal(key="observability", context="applied", quote="o"),
            Signal(key="concurrency_failure_handling", context="applied", quote="f"),
        ],
    )

    github_res = GitHubResult(status="ok", activity_points=5, repo_points=5)

    total, breakdown, adjustments, evidence, strengths, concerns = compute_scores(
        extraction, github_res, scoring_cfg
    )

    assert breakdown.ai_project_depth <= 40
    assert breakdown.python_backend <= 30
    assert breakdown.cloud_fullstack <= 15
    assert breakdown.github <= 10
    assert breakdown.engineering_depth <= 5
    assert total <= 100


def test_thin_wrapper_and_tutorial_penalties(scoring_cfg):
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Wrapper Dev",
        skills=["Python"],
        projects=[
            ProjectEvidence(
                name="Chatbot",
                summary="Simple OpenAI wrapper",
                technologies=["OpenAI"],
                is_ai_project=True,
                capabilities=["llm_call"],
                is_thin_wrapper=True,
                is_tutorial_style=True,
                ownership_evidence=False,
                quotes=["quote"],
            )
        ],
        signals=[
            Signal(key="python", context="applied", quote="py"),
        ],
    )

    total, breakdown, adjustments, evidence, strengths, concerns = compute_scores(
        extraction, None, scoring_cfg
    )

    penalty_reasons = [adj.reason for adj in adjustments]
    assert "thin_wrapper_penalty" in penalty_reasons
    assert "tutorial_style_penalty" in penalty_reasons
    total_penalty = sum(adj.points for adj in adjustments if "penalty" in adj.reason)
    assert total_penalty == -15  # -10 + -5


def test_no_meaningful_ai_cap_applied(scoring_cfg):
    """Candidate with strong backend/cloud/github but low AI depth (< 12) is capped at 55."""
    extraction = ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name="Strong Backend Low AI",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectEvidence(
                name="AI Experiment",
                summary="Basic call",
                technologies=["OpenAI"],
                is_ai_project=True,
                capabilities=["llm_call"],  # Only 6 points for AI depth (< 12)
                quotes=["quote"],
            )
        ],
        signals=[
            Signal(key="python", context="applied", quote="py"),  # 8
            Signal(key="fastapi", context="applied", quote="fa"),  # 7
            Signal(key="async_programming", context="applied", quote="as"),  # 5
            Signal(key="postgresql", context="applied", quote="pg"),  # 5
            Signal(key="redis", context="applied", quote="rd"),  # 5 -> backend = 30
            Signal(key="gcp", context="applied", quote="gcp"),  # 5
            Signal(key="docker", context="applied", quote="dk"),  # 4
            Signal(key="deployment", context="applied", quote="dp"),  # 3
            Signal(key="react_nextjs", context="applied", quote="rc"),  # 3 -> cloud = 15
        ],
    )
    github_res = GitHubResult(status="ok", activity_points=5, repo_points=5)  # 10

    total, breakdown, adjustments, evidence, strengths, concerns = compute_scores(
        extraction, github_res, scoring_cfg
    )

    # Raw score would be 6 + 30 + 15 + 10 = 61.
    # Because ai_depth == 6 < 12, total must be capped at 55.
    assert breakdown.ai_project_depth == 6
    assert total == 55
    assert any(adj.reason == "no_meaningful_ai_cap" for adj in adjustments)
    assert any("Total capped at 55" in c for c in concerns)
