"""Deterministic penalty evaluation and score caps."""

from typing import List, Tuple
from screener.config import PenaltiesConfig, ThresholdsConfig
from screener.models import ResumeExtraction, Adjustment


def evaluate_penalties(
    extraction: ResumeExtraction,
    config: PenaltiesConfig,
) -> Tuple[List[Adjustment], int, List[str]]:
    """
    Evaluate penalties:
    - thin_wrapper_penalty (-10)
    - tutorial_style_penalty (-5)
    Total negative adjustment clamped to -max_total_penalty (-15).
    """
    adjustments: List[Adjustment] = []
    concerns: List[str] = []

    ai_projects = [p for p in extraction.projects if p.is_ai_project]

    if ai_projects:
        # Check thin wrapper
        all_thin = all(p.is_thin_wrapper for p in ai_projects)
        only_llm_call = all(
            p.capabilities == ["llm_call"] or len(p.capabilities) == 0 for p in ai_projects
        )
        if all_thin and only_llm_call:
            adjustments.append(
                Adjustment(
                    reason="thin_wrapper_penalty",
                    points=config.thin_wrapper_penalty,
                )
            )
            concerns.append("AI projects consist solely of thin LLM wrapper API calls")

        # Check tutorial style or lack of ownership
        has_tutorial = any(p.is_tutorial_style or not p.ownership_evidence for p in ai_projects)
        if has_tutorial:
            adjustments.append(
                Adjustment(
                    reason="tutorial_style_penalty",
                    points=config.tutorial_style_penalty,
                )
            )
            concerns.append("Projects exhibit tutorial-style implementations or lack ownership evidence")

    raw_penalty_sum = sum(adj.points for adj in adjustments)
    # Clamp to max negative penalty (e.g. -15)
    clamped_penalty = max(raw_penalty_sum, -config.max_total_penalty)

    return adjustments, clamped_penalty, concerns


def apply_no_meaningful_ai_cap(
    raw_total: int,
    ai_depth_score: int,
    config: ThresholdsConfig,
) -> Tuple[int, List[Adjustment], List[str]]:
    """
    If ai_project_depth < no_meaningful_ai_threshold (12),
    cap total at no_meaningful_ai_cap (55).
    """
    adjustments: List[Adjustment] = []
    concerns: List[str] = []

    if ai_depth_score < config.no_meaningful_ai_threshold and raw_total > config.no_meaningful_ai_cap:
        diff = config.no_meaningful_ai_cap - raw_total
        adjustments.append(
            Adjustment(
                reason="no_meaningful_ai_cap",
                points=diff,
            )
        )
        concerns.append(
            f"Total capped at {config.no_meaningful_ai_cap} due to low AI project depth ({ai_depth_score} < {config.no_meaningful_ai_threshold})"
        )
        return config.no_meaningful_ai_cap, adjustments, concerns

    return raw_total, adjustments, concerns
