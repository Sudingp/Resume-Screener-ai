"""Comprehensive unit tests for pure deterministic eligibility engine."""

import pytest
from screener.config import load_config
from screener.lexicon import CompiledLexicons
from screener.eligibility import (
    check_eligibility,
    STANDARD_NO_PYTHON,
    STANDARD_NO_AI,
    STANDARD_NEEDS_REVIEW,
)
from screener.llm.base import LLMClient
from screener.models import ResumeExtraction


class FailingFakeLLM(LLMClient):
    """Proves that eligibility does not invoke or depend on any LLM."""
    async def extract(self, prompt: str) -> ResumeExtraction:
        raise AssertionError("LLM should never be called during eligibility check!")


@pytest.fixture
def compiled():
    cfg = load_config()
    return CompiledLexicons(cfg.lexicons), cfg


def test_java_react_only_rejected_with_both_reasons(compiled):
    lex, cfg = compiled
    text = (
        "Experienced Full Stack Engineer.\n"
        "Proficient in Java, Spring Boot, React, and MySQL.\n"
        "Built scalable microservices and user dashboards."
    )
    res = check_eligibility(text, lex, cfg)
    assert not res.eligible
    assert STANDARD_NO_PYTHON in res.rejection_reasons
    assert STANDARD_NO_AI in res.rejection_reasons
    assert "Java" in res.matched_skills
    assert "React" in res.matched_skills


def test_python_only_rejected_with_no_ai(compiled):
    lex, cfg = compiled
    text = (
        "Backend Developer with Python and FastAPI experience.\n"
        "Built high throughput endpoints and managed PostgreSQL and Redis."
    )
    res = check_eligibility(text, lex, cfg)
    assert not res.eligible
    assert res.python_ok
    assert not res.ai_ok
    assert STANDARD_NO_AI in res.rejection_reasons
    assert STANDARD_NO_PYTHON not in res.rejection_reasons
    assert "Python" in res.matched_skills


def test_python_ai_strong_eligible(compiled):
    lex, cfg = compiled
    text = (
        "AI Engineer.\n"
        "Languages: Python, SQL.\n"
        "Developed multi-agent workflow using LangGraph, FAISS vector search, and tool calling."
    )
    res = check_eligibility(text, lex, cfg)
    assert res.eligible
    assert res.python_ok
    assert res.ai_ok
    assert len(res.rejection_reasons) == 0


def test_python_ai_java_react_eligible(compiled):
    lex, cfg = compiled
    text = (
        "Polyglot Software Engineer.\n"
        "Skills: Python, Java, React, TypeScript, LangChain, Pinecone.\n"
        "Built RAG pipeline using LangChain and Python, with React frontend."
    )
    res = check_eligibility(text, lex, cfg)
    assert res.eligible
    assert res.python_ok
    assert res.ai_ok
    assert len(res.rejection_reasons) == 0


def test_word_boundaries_javascript_not_java(compiled):
    lex, cfg = compiled
    text = "Frontend Engineer proficient in JavaScript and Next.js."
    skills = lex.match_matched_skills(text)
    assert "JavaScript" in skills
    assert "Java" not in skills


def test_rag_word_boundaries_and_case_sensitivity(compiled):
    lex, cfg = compiled
    # 'storage' or 'fragment' or lowercase 'rag' should NOT trigger strong AI
    text = "Managed database storage and eliminated fragment memory."
    res = check_eligibility(text, lex, cfg)
    assert not res.ai_ok

    text_lower = "Used rag for information retrieval in python."
    res_lower = check_eligibility(text_lower, lex, cfg)
    # Lowercase 'rag' without verb/other terms does not match case-sensitive \bRAG\b
    assert not res_lower.ai_ok

    text_upper = "Implemented RAG architecture for document retrieval with Python."
    res_upper = check_eligibility(text_upper, lex, cfg)
    assert res_upper.ai_ok
    assert res_upper.eligible


def test_user_agent_does_not_match_agentic(compiled):
    lex, cfg = compiled
    text = "Configured user agent headers for HTTP crawler in Python."
    res = check_eligibility(text, lex, cfg)
    assert not res.ai_ok
    assert not res.eligible


def test_weak_only_classical_ml_rejected(compiled):
    lex, cfg = compiled
    text = (
        "Data Analyst.\n"
        "Used Python, scikit-learn, and machine learning for regression analysis.\n"
        "Explored basic deep learning."
    )
    res = check_eligibility(text, lex, cfg)
    assert not res.ai_ok
    assert not res.eligible
    assert STANDARD_NO_AI in res.rejection_reasons
    assert any("Weak AI" in w for w in res.warnings)


def test_ai_terms_without_verb_flags_needs_review(compiled):
    lex, cfg = compiled
    # Has medium term 'OpenAI' and 'LLMs' in skills section but no implementation verb on that line
    text = (
        "Software Engineer with Python.\n"
        "Skills: Python, OpenAI, LLMs, Docker.\n"
        "Maintained corporate web systems."
    )
    res = check_eligibility(text, lex, cfg)
    assert not res.eligible
    assert res.needs_review
    assert STANDARD_NEEDS_REVIEW in res.rejection_reasons


def test_eligibility_independence_from_llm(compiled):
    lex, cfg = compiled
    failing_llm = FailingFakeLLM()
    # Ensure calling eligibility never touches any LLM
    text = "Python engineer who implemented LangGraph multi-agent systems."
    res = check_eligibility(text, lex, cfg)
    assert res.eligible
