"""Deterministic GitHub scoring and summary generation per rubric."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from screener.config import GitHubScoringConfig
from screener.github.client import GitHubProfileData
from screener.models import GitHubResult


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    """Parse ISO datetime string to timezone-aware UTC datetime."""
    if not dt_str:
        return None
    try:
        # Handles 2026-10-01T12:00:00Z or +00:00
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def score_github_profile(
    profile_data: Optional[GitHubProfileData],
    config: GitHubScoringConfig,
    now: Optional[datetime] = None,
) -> GitHubResult:
    """
    Score GitHub activity and repos deterministically.
    Total score capped at config.category_cap (10 points).
    """
    if profile_data is None:
        return GitHubResult(status="no_profile", activity_points=0, repo_points=0)

    status = profile_data.status
    username = profile_data.username

    if status != "ok":
        # Missing profile, not_found, rate_limited, error all yield 0 and are recorded
        status_map = {
            "no_profile": "no_profile",
            "not_found": "not_found",
            "rate_limited": "rate_limited",
            "error": "error",
            "disabled": "disabled",
            "skipped_rejected": "skipped_rejected",
        }
        res_status = status_map.get(status, "error")
        return GitHubResult(
            status=res_status,
            username=username,
            activity_points=0,
            repo_points=0,
            summary=f"GitHub profile {res_status.replace('_', ' ')}",
        )

    current_time = now or datetime.now(timezone.utc)
    events = profile_data.events
    repos = profile_data.repos

    # 1. Activity Scoring (0 - 5)
    # Find latest push/PR event or repo push
    latest_dt: Optional[datetime] = None
    push_pr_count = 0
    iso_weeks_90d: Set[Tuple[int, int]] = set()  # (year, week)

    cutoff_90d = current_time - timedelta(days=90)

    for ev in events:
        ev_type = ev.get("type")
        ev_created = parse_iso_datetime(ev.get("created_at"))
        if not ev_created:
            continue

        if ev_type in ("PushEvent", "PullRequestEvent"):
            push_pr_count += 1
            if latest_dt is None or ev_created > latest_dt:
                latest_dt = ev_created

            if ev_created >= cutoff_90d:
                iso_year, iso_week, _ = ev_created.isocalendar()
                iso_weeks_90d.add((iso_year, iso_week))

    # Also check repo pushed_at for recency
    for repo in repos:
        pushed_at = parse_iso_datetime(repo.get("pushed_at"))
        if pushed_at and (latest_dt is None or pushed_at > latest_dt):
            latest_dt = pushed_at

    activity_points = 0
    days_ago = None
    if latest_dt:
        days_ago = max(0, (current_time - latest_dt).days)
        if days_ago <= config.recency_days["tier1"][0]:
            activity_points += config.recency_days["tier1"][1]
        elif days_ago <= config.recency_days["tier2"][0]:
            activity_points += config.recency_days["tier2"][1]
        elif days_ago <= config.recency_days["tier3"][0]:
            activity_points += config.recency_days["tier3"][1]

    # Consistency
    active_weeks_count = len(iso_weeks_90d)
    if active_weeks_count >= config.active_weeks_90d["tier1"][0]:
        activity_points += config.active_weeks_90d["tier1"][1]
    elif active_weeks_count >= config.active_weeks_90d["tier2"][0]:
        activity_points += config.active_weeks_90d["tier2"][1]

    activity_points = min(activity_points, config.activity_max)

    # 2. Repos Scoring (0 - 5)
    cutoff_365d = current_time - timedelta(days=365)
    maintained_repos: List[Dict[str, Any]] = []
    relevant_repos: List[Dict[str, Any]] = []
    has_substance = False

    ai_keywords = {"ai", "rag", "agent", "llm", "langchain", "llamaindex", "gemini", "gpt", "fastapi"}

    for r in repos:
        is_fork = r.get("fork", False)
        is_archived = r.get("archived", False)
        pushed_at = parse_iso_datetime(r.get("pushed_at"))

        if not is_fork and not is_archived and pushed_at and pushed_at >= cutoff_365d:
            maintained_repos.append(r)

            # Check relevance: language is Python, or topics/description match AI terms
            lang = (r.get("language") or "").lower()
            desc = (r.get("description") or "").lower()
            topics = [t.lower() for t in r.get("topics", [])]

            is_relevant = (lang == "python") or any(
                kw in desc or kw in topics for kw in ai_keywords
            )
            if is_relevant:
                relevant_repos.append(r)

            size_kb = r.get("size", 0)
            if desc and size_kb >= config.min_repo_size_kb:
                has_substance = True

    repo_points = 0
    # Maintained repo count points
    m_count = len(maintained_repos)
    if m_count >= config.maintained_repos_365d["tier1"][0]:
        repo_points += config.maintained_repos_365d["tier1"][1]
    elif m_count >= config.maintained_repos_365d["tier2"][0]:
        repo_points += config.maintained_repos_365d["tier2"][1]

    # Relevant repo count points
    rel_count = len(relevant_repos)
    if rel_count >= config.relevant_repos["tier1"][0]:
        repo_points += config.relevant_repos["tier1"][1]
    elif rel_count >= config.relevant_repos["tier2"][0]:
        repo_points += config.relevant_repos["tier2"][1]

    # Substance point
    if has_substance:
        repo_points += 1

    repo_points = min(repo_points, config.repos_max)

    # Deterministic summary template
    recency_str = f"{days_ago} days ago" if days_ago is not None else "no recent activity"
    summary = (
        f"Last public activity {recency_str}; {push_pr_count} push/PR events over "
        f"{active_weeks_count} active weeks; {m_count} maintained repos, {rel_count} Python/AI-relevant."
    )

    return GitHubResult(
        status="ok",
        username=username,
        activity_points=activity_points,
        repo_points=repo_points,
        summary=summary,
        details={
            "maintained_repos_count": m_count,
            "relevant_repos_count": rel_count,
            "active_weeks_90d": active_weeks_count,
            "days_since_last_activity": days_ago,
        },
    )
