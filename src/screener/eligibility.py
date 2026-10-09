"""Pure deterministic eligibility evaluation.

LLM as witness, code as judge.
Never decides eligibility with an LLM.
"""

from typing import List, Tuple
from screener.config import AppConfig
from screener.lexicon import CompiledLexicons
from screener.models import EligibilityResult


STANDARD_NO_PYTHON = "No evidence of Python stack"
STANDARD_NO_AI = "No AI/agentic project evidence"
STANDARD_NEEDS_REVIEW = "AI-related terms found but no implementation evidence (needs review)"


def check_eligibility(
    text: str,
    compiled_lexicons: CompiledLexicons,
    config: AppConfig,
) -> EligibilityResult:
    """
    Pure function: text -> EligibilityResult.
    Deterministic, zero network calls, zero LLM calls.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Python check
    python_ok = False
    for pat in compiled_lexicons.python_regexes:
        if pat.search(text):
            python_ok = True
            break

    # 2. AI check
    has_strong_ai = False
    has_medium_ai = False
    has_medium_ai_with_verb = False
    has_weak_ai = False
    matched_strong_terms: List[str] = []

    # Check strong AI across full text
    for pat in compiled_lexicons.strong_ai_regexes:
        m = pat.search(text)
        if m:
            has_strong_ai = True
            matched_strong_terms.append(m.group(0))

    # Check lines for medium AI and verbs
    for line in lines:
        line_has_medium = any(pat.search(line) for pat in compiled_lexicons.medium_ai_regexes)
        if line_has_medium:
            has_medium_ai = True
            line_has_verb = any(vpat.search(line) for vpat in compiled_lexicons.verb_regexes)
            if line_has_verb:
                has_medium_ai_with_verb = True

    # Check weak AI across full text
    for pat in compiled_lexicons.weak_ai_regexes:
        if pat.search(text):
            has_weak_ai = True
            break

    # Evaluate AI status
    ai_ok = False
    needs_review = False
    rejection_reasons: List[str] = []
    warnings: List[str] = []

    if has_strong_ai:
        ai_ok = True
    elif has_medium_ai and (not config.lexicons.eligibility.medium_requires_verb or has_medium_ai_with_verb):
        ai_ok = True
    elif has_medium_ai and not has_medium_ai_with_verb:
        # Medium terms found, but lacking implementation verbs
        needs_review = True
    elif has_weak_ai:
        warnings.append("Weak AI or classical ML terms found without modern agentic/LLM project evidence")

    # Determine eligibility and rejection reasons
    if not python_ok:
        rejection_reasons.append(STANDARD_NO_PYTHON)

    if not ai_ok:
        if needs_review:
            rejection_reasons.append(STANDARD_NEEDS_REVIEW)
        else:
            rejection_reasons.append(STANDARD_NO_AI)

    is_eligible = python_ok and ai_ok

    # Produce matched skills catalog for every candidate
    matched_skills = compiled_lexicons.match_matched_skills(text)

    return EligibilityResult(
        eligible=is_eligible,
        rejection_reasons=rejection_reasons,
        matched_skills=matched_skills,
        needs_review=needs_review,
        python_ok=python_ok,
        ai_ok=ai_ok,
        warnings=warnings,
    )
