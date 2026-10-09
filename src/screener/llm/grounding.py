"""Grounding validator: verifies LLM quotes exist verbatim in the resume text.

LLM as witness, code as judge.
Any signal or capability without a grounded quote is dropped.
"""

import re
from typing import List, Tuple
from screener.models import ResumeExtraction, ProjectEvidence, Signal


def normalize_for_grounding(text: str) -> str:
    """
    Normalize text for robust substring matching:
    - lowercase
    - replace hyphens at line-breaks
    - remove punctuation and normalize all whitespace
    """
    # Remove hyphenated line-breaks (e.g. "multi-\nagent" -> "multiagent")
    s = re.sub(r"-\s+", "", text)
    # Lowercase and strip all whitespace and punctuation
    s = re.sub(r"[^\w\s]", "", s.lower())
    return "".join(s.split())


def is_grounded(quote: str, normalized_resume: str) -> bool:
    """Check if quote exists in the normalized resume text."""
    if not quote or not quote.strip():
        return False
    norm_quote = normalize_for_grounding(quote)
    if not norm_quote:
        return False
    return norm_quote in normalized_resume


def validate_grounding(
    extraction: ResumeExtraction,
    resume_text: str,
) -> Tuple[ResumeExtraction, List[str]]:
    """
    Validate all quotes in extraction against resume_text.
    Drops ungrounded signals and ungrounded project capabilities.
    Returns (cleaned_extraction, warnings).
    """
    normalized_resume = normalize_for_grounding(resume_text)
    ungrounded_count = 0
    warnings: List[str] = []

    # 1. Validate signals
    grounded_signals: List[Signal] = []
    for sig in extraction.signals:
        if is_grounded(sig.quote, normalized_resume):
            grounded_signals.append(sig)
        else:
            ungrounded_count += 1

    # 2. Validate projects
    grounded_projects: List[ProjectEvidence] = []
    for proj in extraction.projects:
        valid_quotes = [q for q in proj.quotes if is_grounded(q, normalized_resume)]
        invalid_quotes_count = len(proj.quotes) - len(valid_quotes)
        ungrounded_count += invalid_quotes_count

        if not valid_quotes and proj.capabilities:
            # A project with no grounded quote loses its capabilities
            proj_copy = proj.model_copy(
                update={"capabilities": [], "quotes": [], "is_ai_project": False}
            )
            grounded_projects.append(proj_copy)
        else:
            proj_copy = proj.model_copy(update={"quotes": valid_quotes})
            grounded_projects.append(proj_copy)

    if ungrounded_count > 0:
        warnings.append(f"ungrounded_quotes: {ungrounded_count}")

    validated_extraction = extraction.model_copy(
        update={
            "signals": grounded_signals,
            "projects": grounded_projects,
        }
    )

    return validated_extraction, warnings
