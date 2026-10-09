"""Deterministic ranking engine per Blueprint Section E."""

from typing import List
from screener.models import CandidateResult


def rank_candidates(candidates: List[CandidateResult]) -> List[CandidateResult]:
    """
    Deterministically rank eligible candidates.
    Sort key:
      - total_score (descending)
      - ai_project_depth (descending)
      - python_backend (descending)
      - github (descending)
      - candidate_name.lower() (ascending)
      - source_file (ascending)

    Order in final array:
      1. Eligible candidates (ranks 1..N)
      2. Rejected candidates (rank is None)
      3. Failed candidates (rank is None)
    """
    eligible: List[CandidateResult] = []
    rejected: List[CandidateResult] = []
    failed: List[CandidateResult] = []

    for c in candidates:
        if c.status == "eligible":
            eligible.append(c)
        elif c.status == "rejected":
            rejected.append(c)
        else:
            failed.append(c)

    def sort_key(c: CandidateResult):
        total = c.total_score if c.total_score is not None else -1
        ai = c.score_breakdown.ai_project_depth if c.score_breakdown else -1
        py = c.score_breakdown.python_backend if c.score_breakdown else -1
        gh = c.score_breakdown.github if c.score_breakdown else -1
        name = (c.candidate_name or "").lower()
        src = c.source_file
        return (-total, -ai, -py, -gh, name, src)

    eligible.sort(key=sort_key)

    ranked_eligible: List[CandidateResult] = []
    for rank_idx, c in enumerate(eligible, start=1):
        ranked_c = c.model_copy(update={"rank": rank_idx})
        ranked_eligible.append(ranked_c)

    # Sort rejected deterministically by name / filename
    rejected.sort(key=lambda c: ((c.candidate_name or "").lower(), c.source_file))
    failed.sort(key=lambda c: c.source_file)

    return ranked_eligible + rejected + failed
