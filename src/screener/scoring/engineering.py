"""Engineering Depth category scorer (5 points cap)."""

from typing import Dict, List, Tuple
from screener.config import EngineeringDepthConfig
from screener.models import ResumeExtraction, EvidenceItem, Signal


def score_engineering_depth(
    extraction: ResumeExtraction,
    config: EngineeringDepthConfig,
) -> Tuple[int, List[EvidenceItem], List[str]]:
    """
    Score engineering practices: testing, architecture, queues, observability, concurrency.
    1 point per applied signal, capped at 5.
    """
    evidence: List[EvidenceItem] = []
    # Collect signals where context == "applied"
    applied_signals: Dict[str, Signal] = {
        sig.key: sig for sig in extraction.signals if sig.context == "applied"
    }

    score = 0
    for req_sig in config.signals:
        sig = applied_signals.get(req_sig)
        if sig:
            score += config.points_per_applied_signal
            evidence.append(
                EvidenceItem(
                    category="engineering_depth",
                    signal=req_sig,
                    quote=sig.quote,
                )
            )

    final_score = min(score, config.category_cap)
    notes = []
    if final_score >= 3:
        notes.append("Demonstrated engineering rigor (testing/observability/architecture)")

    return final_score, evidence, notes
