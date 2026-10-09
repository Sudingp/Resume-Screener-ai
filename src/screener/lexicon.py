"""Precompiled lexicon matching engine for skills, signals, and eligibility tiers."""

import re
from typing import Dict, List, NamedTuple, Optional, Set
from screener.config import LexiconsConfig


class MatchResult(NamedTuple):
    term: str
    tier: str  # 'python' | 'strong' | 'medium' | 'weak' | 'skill' | 'verb' | 'signal'
    line_number: int
    line_text: str
    section_hint: Optional[str] = None


class CompiledLexicons:
    """Precompiles regex patterns for high-throughput single-pass or multi-pattern matching."""

    def __init__(self, config: LexiconsConfig):
        self.config = config

        # Python patterns (case-insensitive)
        self.python_regexes = [
            re.compile(pat, re.IGNORECASE) for pat in config.eligibility.python_patterns
        ]

        # Strong AI terms
        self.strong_ai_regexes = []
        for pat in config.eligibility.strong_ai_terms:
            if pat == r"\bRAG\b":
                # Case-sensitive for uppercase RAG to avoid matching "storage" or "fragment"
                self.strong_ai_regexes.append(re.compile(r"\bRAG\b"))
            else:
                self.strong_ai_regexes.append(re.compile(pat, re.IGNORECASE))

        # Medium AI terms (case-insensitive)
        self.medium_ai_regexes = [
            re.compile(pat, re.IGNORECASE) for pat in config.eligibility.medium_ai_terms
        ]

        # Weak AI terms (case-insensitive)
        self.weak_ai_regexes = [
            re.compile(pat, re.IGNORECASE) for pat in config.eligibility.weak_ai_terms
        ]

        # Implementation verbs (case-insensitive)
        self.verb_regexes = [
            re.compile(rf"\b{re.escape(verb)}\b", re.IGNORECASE)
            for verb in config.eligibility.implementation_verbs
        ]

        # Skills catalog: map canonical skill name -> compiled regex
        self.skills_map: Dict[str, re.Pattern] = {}
        for skill in config.skills_catalog:
            # Special case for case-sensitive terms like RAG, GCP, AWS, REST API
            if skill in {"RAG", "GCP", "AWS", "REST API", "CI/CD"}:
                self.skills_map[skill] = re.compile(rf"\b{re.escape(skill)}\b")
            else:
                self.skills_map[skill] = re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE)

        # Signal patterns
        self.signal_regexes: Dict[str, List[re.Pattern]] = {}
        for sig_key, patterns in config.signal_patterns.items():
            self.signal_regexes[sig_key] = [
                re.compile(pat, re.IGNORECASE) for pat in patterns
            ]

    def match_matched_skills(self, text: str) -> List[str]:
        """Extract all matched canonical skills present in the resume text."""
        matched: List[str] = []
        for skill_name, pattern in self.skills_map.items():
            if pattern.search(text):
                matched.append(skill_name)
        return sorted(matched)
