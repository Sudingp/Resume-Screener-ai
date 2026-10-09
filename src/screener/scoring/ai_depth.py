"""AI Project Depth category scorer (40 points cap)."""

from typing import List, Set, Tuple
from screener.config import AIDepthConfig
from screener.models import ResumeExtraction, EvidenceItem


def score_ai_project_depth(
    extraction: ResumeExtraction,
    config: AIDepthConfig,
) -> Tuple[int, List[EvidenceItem], List[str]]:
    """
    Score AI project depth.
    Union of capabilities across projects flagged is_ai_project with grounded quotes.
    Returns (score, evidence_items, strengths_or_concerns).
    """
    evidence: List[EvidenceItem] = []
    applied_ai_projects = [
        p for p in extraction.projects if p.is_ai_project and p.quotes and p.capabilities
    ]

    if not applied_ai_projects:
        # Check if AI skills exist in skills list without applied project
        has_ai_skills = any(
            s.lower() in ("langchain", "llamaindex", "openai", "rag", "crewai", "autogen", "faiss")
            for s in extraction.skills
        )
        if has_ai_skills:
            score = min(config.skills_only_max, config.category_cap)
            return score, [], ["AI frameworks present in skills list but lacks applied project"]
        return 0, [], ["No applied AI project evidence found"]

    # Gather union of capabilities across all applied AI projects
    seen_capabilities: Set[str] = set()
    total_score = 0

    tool_or_multi_counted = False

    for proj in applied_ai_projects:
        quote = proj.quotes[0] if proj.quotes else proj.summary
        for cap in proj.capabilities:
            if cap in seen_capabilities:
                continue
            seen_capabilities.add(cap)

            if cap in ("tool_calling", "multi_agent"):
                if not tool_or_multi_counted:
                    pts = config.capabilities.get("tool_calling", 9)
                    total_score += pts
                    tool_or_multi_counted = True
                    evidence.append(
                        EvidenceItem(
                            category="ai_project_depth",
                            capability=cap,
                            quote=quote,
                        )
                    )
            else:
                pts = config.capabilities.get(cap, 0)
                if pts > 0:
                    total_score += pts
                    evidence.append(
                        EvidenceItem(
                            category="ai_project_depth",
                            capability=cap,
                            quote=quote,
                        )
                    )

    final_score = min(total_score, config.category_cap)
    notes = []
    if final_score >= 30:
        notes.append("Strong multi-faceted AI project implementation")
    elif final_score < 12:
        notes.append("Limited AI project depth")

    return final_score, evidence, notes
