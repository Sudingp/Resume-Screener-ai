"""Orchestrator that executes deterministic scoring across all categories, penalties, and caps."""

from typing import List, Optional, Tuple
from screener.config import ScoringConfig
from screener.models import (
    ResumeExtraction,
    ScoreBreakdown,
    Adjustment,
    EvidenceItem,
    GitHubResult,
)
from screener.scoring.ai_depth import score_ai_project_depth
from screener.scoring.backend import score_python_backend
from screener.scoring.cloud import score_cloud_fullstack
from screener.scoring.engineering import score_engineering_depth
from screener.scoring.penalties import evaluate_penalties, apply_no_meaningful_ai_cap


def compute_scores(
    extraction: ResumeExtraction,
    github_result: Optional[GitHubResult],
    scoring_config: ScoringConfig,
    is_heuristic: bool = False,
) -> Tuple[int, ScoreBreakdown, List[Adjustment], List[EvidenceItem], List[str], List[str]]:
    """
    Compute candidate score across all rubric categories, adjustments, and caps.
    Returns:
        (total_score, breakdown, adjustments, evidence, strengths, concerns)
    """
    all_evidence: List[EvidenceItem] = []
    all_strengths: List[str] = list(extraction.strengths)
    all_concerns: List[str] = list(extraction.concerns)
    all_adjustments: List[Adjustment] = []

    # 1. AI project depth
    ai_score, ai_evidence, ai_notes = score_ai_project_depth(
        extraction, scoring_config.ai_project_depth
    )
    if is_heuristic:
        ai_score = min(ai_score, scoring_config.thresholds.heuristic_ai_depth_cap)
    all_evidence.extend(ai_evidence)
    all_strengths.extend([n for n in ai_notes if "Strong" in n])
    all_concerns.extend([n for n in ai_notes if "Limited" in n or "frameworks" in n])

    # 2. Python & backend
    backend_score, backend_evidence, backend_notes = score_python_backend(
        extraction, scoring_config.python_backend
    )
    all_evidence.extend(backend_evidence)
    all_strengths.extend([n for n in backend_notes if "Solid" in n])
    all_concerns.extend([n for n in backend_notes if "Limited" in n])

    # 3. Cloud & fullstack
    cloud_score, cloud_evidence, cloud_notes = score_cloud_fullstack(
        extraction, scoring_config.cloud_fullstack
    )
    all_evidence.extend(cloud_evidence)
    all_strengths.extend(cloud_notes)

    # 4. GitHub
    github_score = 0
    if github_result and github_result.status == "ok":
        github_score = min(
            github_result.activity_points + github_result.repo_points,
            scoring_config.github.category_cap,
        )

    # 5. Engineering depth
    eng_score, eng_evidence, eng_notes = score_engineering_depth(
        extraction, scoring_config.engineering_depth
    )
    all_evidence.extend(eng_evidence)
    all_strengths.extend(eng_notes)

    # Breakdown before adjustments
    breakdown = ScoreBreakdown(
        ai_project_depth=ai_score,
        python_backend=backend_score,
        cloud_fullstack=cloud_score,
        github=github_score,
        engineering_depth=eng_score,
    )

    raw_sum = (
        ai_score
        + backend_score
        + cloud_score
        + github_score
        + eng_score
    )

    # 6. Penalties (thin wrapper, tutorial style)
    penalties, penalty_sum, penalty_concerns = evaluate_penalties(
        extraction, scoring_config.penalties
    )
    all_adjustments.extend(penalties)
    all_concerns.extend(penalty_concerns)

    score_after_penalties = raw_sum + penalty_sum

    # 7. No meaningful AI cap
    capped_score, cap_adjustments, cap_concerns = apply_no_meaningful_ai_cap(
        score_after_penalties, ai_score, scoring_config.thresholds
    )
    all_adjustments.extend(cap_adjustments)
    all_concerns.extend(cap_concerns)

    # 8. Clamp total to 0 - 100
    final_total = max(0, min(100, capped_score))

    # Keep unique strengths/concerns (up to 3 concise each per schema)
    clean_strengths = list(dict.fromkeys(s.strip() for s in all_strengths if s.strip()))[:3]
    clean_concerns = list(dict.fromkeys(c.strip() for c in all_concerns if c.strip()))[:3]

    return final_total, breakdown, all_adjustments, all_evidence, clean_strengths, clean_concerns
