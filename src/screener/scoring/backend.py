"""Python and Backend category scorer (30 points cap)."""

from typing import Dict, List, Tuple
from screener.config import PythonBackendConfig
from screener.models import ResumeExtraction, EvidenceItem, Signal


def score_python_backend(
    extraction: ResumeExtraction,
    config: PythonBackendConfig,
) -> Tuple[int, List[EvidenceItem], List[str]]:
    """
    Score Python and backend technologies.
    Returns (score, evidence_items, notes).
    """
    evidence: List[EvidenceItem] = []
    # Map key -> best Signal (prefer applied over skills_only)
    best_signals: Dict[str, Signal] = {}
    for sig in extraction.signals:
        curr = best_signals.get(sig.key)
        if curr is None:
            best_signals[sig.key] = sig
        elif sig.context == "applied" and curr.context != "applied":
            best_signals[sig.key] = sig

    def get_points(key: str) -> Tuple[int, Optional[Signal]]:
        sig = best_signals.get(key)
        credits = config.credits.get(key, [0, 0])
        if sig is None:
            return 0, None
        pts = credits[0] if sig.context == "applied" else credits[1]
        return pts, sig

    total_score = 0

    # 1. Python
    py_pts, py_sig = get_points("python")
    total_score += py_pts
    if py_sig:
        evidence.append(EvidenceItem(category="python_backend", signal="python", quote=py_sig.quote))

    # 2. Web framework: max of fastapi vs flask_django
    fastapi_pts, fastapi_sig = get_points("fastapi")
    flask_django_pts, flask_django_sig = get_points("flask_django")
    if fastapi_pts >= flask_django_pts and fastapi_sig:
        total_score += fastapi_pts
        evidence.append(EvidenceItem(category="python_backend", signal="fastapi", quote=fastapi_sig.quote))
    elif flask_django_sig:
        total_score += flask_django_pts
        evidence.append(EvidenceItem(category="python_backend", signal="flask_django", quote=flask_django_sig.quote))

    # 3. Async programming
    async_pts, async_sig = get_points("async_programming")
    total_score += async_pts
    if async_sig:
        evidence.append(EvidenceItem(category="python_backend", signal="async_programming", quote=async_sig.quote))

    # 4. Database: max of postgresql vs other_sql
    pg_pts, pg_sig = get_points("postgresql")
    other_sql_pts, other_sql_sig = get_points("other_sql")
    if pg_pts >= other_sql_pts and pg_sig:
        total_score += pg_pts
        evidence.append(EvidenceItem(category="python_backend", signal="postgresql", quote=pg_sig.quote))
    elif other_sql_sig:
        total_score += other_sql_pts
        evidence.append(EvidenceItem(category="python_backend", signal="other_sql", quote=other_sql_sig.quote))

    # 5. Redis
    redis_pts, redis_sig = get_points("redis")
    total_score += redis_pts
    if redis_sig:
        evidence.append(EvidenceItem(category="python_backend", signal="redis", quote=redis_sig.quote))

    final_score = min(total_score, config.category_cap)
    notes = []
    if final_score >= 20:
        notes.append("Solid Python backend experience")
    if redis_pts == 0:
        notes.append("Limited Redis or distributed caching evidence")

    return final_score, evidence, notes
