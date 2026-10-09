"""Cloud, Deployment, and Fullstack category scorer (15 points cap)."""

from typing import Dict, List, Optional, Tuple
from screener.config import CloudFullstackConfig
from screener.models import ResumeExtraction, EvidenceItem, Signal


def score_cloud_fullstack(
    extraction: ResumeExtraction,
    config: CloudFullstackConfig,
) -> Tuple[int, List[EvidenceItem], List[str]]:
    """
    Score cloud platforms, containers, CI/CD deployment, and fullstack frontend.
    Returns (score, evidence_items, notes).
    """
    evidence: List[EvidenceItem] = []
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

    # 1. Cloud: max of gcp vs other_cloud
    gcp_pts, gcp_sig = get_points("gcp")
    other_cloud_pts, other_cloud_sig = get_points("other_cloud")
    if gcp_pts >= other_cloud_pts and gcp_sig:
        total_score += gcp_pts
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="gcp", quote=gcp_sig.quote))
    elif other_cloud_sig:
        total_score += other_cloud_pts
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="other_cloud", quote=other_cloud_sig.quote))

    # 2. Docker
    docker_pts, docker_sig = get_points("docker")
    total_score += docker_pts
    if docker_sig:
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="docker", quote=docker_sig.quote))

    # 3. Deployment or CI/CD (applied 3)
    dep_pts, dep_sig = get_points("deployment")
    cicd_pts, cicd_sig = get_points("ci_cd")
    if dep_pts >= cicd_pts and dep_sig:
        total_score += dep_pts
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="deployment", quote=dep_sig.quote))
    elif cicd_sig:
        total_score += cicd_pts
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="ci_cd", quote=cicd_sig.quote))

    # 4. React / Next.js
    react_pts, react_sig = get_points("react_nextjs")
    total_score += react_pts
    if react_sig:
        evidence.append(EvidenceItem(category="cloud_fullstack", signal="react_nextjs", quote=react_sig.quote))

    final_score = min(total_score, config.category_cap)
    notes = []
    if final_score >= 10:
        notes.append("Good cloud deployment and containerization exposure")

    return final_score, evidence, notes
