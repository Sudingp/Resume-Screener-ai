"""Heuristic fallback extractor using regex lexicons and layout analysis.

Used when --no-llm is specified or if the LLM provider fails after retries.
"""

import re
from typing import Dict, List, Set, Tuple
from screener.config import LexiconsConfig
from screener.lexicon import CompiledLexicons
from screener.models import (
    ResumeExtraction,
    ProjectEvidence,
    Signal,
    CapabilityKey,
    SignalKey,
    Context,
    SCHEMA_VERSION,
)


SKILLS_HEADER_REGEX = re.compile(
    r"^\s*(skills|technical\s+skills|core\s+competencies|technologies|tools)\b",
    re.IGNORECASE,
)
EXPERIENCE_HEADER_REGEX = re.compile(
    r"^\s*(experience|work\s+experience|employment|projects|project\s+experience)\b",
    re.IGNORECASE,
)


def extract_heuristic(
    resume_text: str,
    compiled_lexicons: CompiledLexicons,
) -> ResumeExtraction:
    """
    Deterministically extract signals and capabilities using regex and section detection.
    """
    lines = resume_text.splitlines()

    # Detect sections
    in_skills_section = False
    in_projects_section = False
    skills_lines: List[str] = []
    project_lines: List[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if SKILLS_HEADER_REGEX.match(s):
            in_skills_section = True
            in_projects_section = False
            continue
        elif EXPERIENCE_HEADER_REGEX.match(s):
            in_projects_section = True
            in_skills_section = False
            continue

        if in_skills_section:
            skills_lines.append(s)
        else:
            project_lines.append(s)

    has_sections = bool(skills_lines and project_lines)
    full_skills_text = " ".join(skills_lines)
    full_project_text = " ".join(project_lines)

    # 1. Signals extraction
    signals: List[Signal] = []
    seen_signals: Set[str] = set()

    for sig_key, patterns in compiled_lexicons.signal_regexes.items():
        # Check in project lines first for applied context
        found_applied = False
        applied_quote = ""
        for line in project_lines:
            if any(pat.search(line) for pat in patterns):
                found_applied = True
                applied_quote = line[:200]
                break

        if found_applied:
            signals.append(
                Signal(
                    key=sig_key,  # type: ignore
                    context="applied",
                    quote=applied_quote,
                )
            )
            seen_signals.add(sig_key)
        else:
            # Check skills lines
            for line in skills_lines:
                if any(pat.search(line) for pat in patterns):
                    signals.append(
                        Signal(
                            key=sig_key,  # type: ignore
                            context="skills_only",
                            quote=line[:200],
                        )
                    )
                    seen_signals.add(sig_key)
                    break

        # Fallback if sections were not separated
        if not has_sections and sig_key not in seen_signals:
            for line in lines:
                if any(pat.search(line) for pat in patterns):
                    signals.append(
                        Signal(
                            key=sig_key,  # type: ignore
                            context="skills_only",  # Conservative credit when section unclear
                            quote=line[:200],
                        )
                    )
                    break

    # 2. Capabilities extraction for AI
    capabilities: List[CapabilityKey] = []
    quotes: List[str] = []

    # Map regex to capabilities
    cap_patterns: Dict[CapabilityKey, List[re.Pattern]] = {
        "retrieval_rag": [re.compile(r"\bRAG\b"), re.compile(r"retrieval[\s-]augmented", re.I), re.compile(r"vector\s+(?:search|database)", re.I)],
        "tool_calling": [re.compile(r"tool[\s-]calling", re.I), re.compile(r"function[\s-]calling", re.I)],
        "multi_agent": [re.compile(r"multi[\s-]agent", re.I), re.compile(r"langgraph", re.I), re.compile(r"crewai", re.I), re.compile(r"autogen", re.I)],
        "llm_call": [re.compile(r"openai", re.I), re.compile(r"gemini", re.I), re.compile(r"claude", re.I), re.compile(r"\bllms?\b", re.I)],
        "state_orchestration": [re.compile(r"stateful", re.I), re.compile(r"orchestrat", re.I)],
        "evaluation_guardrails": [re.compile(r"guardrail", re.I), re.compile(r"evaluation", re.I)],
        "business_logic_data": [re.compile(r"pipeline", re.I), re.compile(r"etl", re.I), re.compile(r"data processing", re.I)],
    }

    for cap, pats in cap_patterns.items():
        for line in project_lines or lines:
            if any(p.search(line) for p in pats):
                capabilities.append(cap)
                quotes.append(line[:200])
                break

    matched_skills = compiled_lexicons.match_matched_skills(resume_text)

    project = None
    if capabilities:
        project = ProjectEvidence(
            name="Heuristic Detected AI Project",
            summary="Extracted via deterministic heuristic text scanning",
            technologies=matched_skills[:5],
            is_ai_project=True,
            capabilities=capabilities,
            is_thin_wrapper=False,
            is_tutorial_style=False,
            ownership_evidence=True,
            quotes=quotes[:3],
        )

    return ResumeExtraction(
        schema_version=SCHEMA_VERSION,
        candidate_name=None,
        skills=matched_skills,
        projects=[project] if project else [],
        signals=signals,
        strengths=["Heuristic text extraction completed"],
        concerns=["Extracted via fallback heuristic, not LLM grounded"],
    )
