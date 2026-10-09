"""Tests for GitHub enrichment, client isolation, single-flight caching, and scoring."""

import asyncio
from datetime import datetime, timezone, timedelta
import json
import httpx
import pytest
from screener.config import load_config
from screener.github.client import GitHubClient, GitHubProfileData
from screener.scoring.github_score import score_github_profile


@pytest.fixture
def github_cfg():
    cfg = load_config()
    return cfg.scoring.github


@pytest.mark.asyncio
async def test_github_active_profile_and_scoring(github_cfg):
    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev_dt = (now - timedelta(days=5)).isoformat()
    repo_dt = (now - timedelta(days=10)).isoformat()

    mock_events = [
        {"type": "PushEvent", "created_at": ev_dt},
        {"type": "PullRequestEvent", "created_at": ev_dt},
    ]
    mock_repos = [
        {"name": "repo1", "fork": False, "archived": False, "pushed_at": repo_dt, "language": "Python", "size": 100, "description": "AI agent repo"},
        {"name": "repo2", "fork": False, "archived": False, "pushed_at": repo_dt, "language": "Python", "size": 200, "description": "LangGraph demo"},
        {"name": "repo3", "fork": False, "archived": False, "pushed_at": repo_dt, "language": "TypeScript", "size": 50, "description": "Frontend"},
    ]

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        if "/events/public" in request.url.path:
            return httpx.Response(200, json=mock_events)
        elif "/repos" in request.url.path:
            return httpx.Response(200, json=mock_repos)
        return httpx.Response(404)

    client = GitHubClient(transport=httpx.MockTransport(mock_handler))
    profile = await client.fetch_profile("activeuser")
    assert profile.status == "ok"

    res = score_github_profile(profile, github_cfg, now=now)
    assert res.status == "ok"
    assert res.activity_points > 0
    assert res.repo_points > 0
    assert res.activity_points + res.repo_points <= 10
    assert "Last public activity" in res.summary


@pytest.mark.asyncio
async def test_github_404_not_found(github_cfg):
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = GitHubClient(transport=httpx.MockTransport(mock_handler))
    profile = await client.fetch_profile("nonexistentuser")
    assert profile.status == "not_found"

    res = score_github_profile(profile, github_cfg)
    assert res.status == "not_found"
    assert res.activity_points == 0
    assert res.repo_points == 0


@pytest.mark.asyncio
async def test_github_rate_limit_circuit_breaker(github_cfg):
    # First call returns 403 with x-ratelimit-remaining = 0
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0"})

    client = GitHubClient(transport=httpx.MockTransport(mock_handler))

    # User 1 hits rate limit
    p1 = await client.fetch_profile("user1")
    assert p1.status == "rate_limited"
    assert client.circuit_broken is True

    # User 2 is intercepted by the circuit breaker without hitting the network
    p2 = await client.fetch_profile("user2")
    assert p2.status == "rate_limited"
    assert call_count == 1  # Network was only hit once!


@pytest.mark.asyncio
async def test_github_single_flight_deduplication():
    network_hits = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal network_hits
        network_hits += 1
        await asyncio.sleep(0.05)  # Simulate network latency
        return httpx.Response(200, json=[])

    client = GitHubClient(transport=httpx.MockTransport(mock_handler))

    # Two concurrent requests for the same username
    p1, p2 = await asyncio.gather(
        client.fetch_profile("shareduser"),
        client.fetch_profile("shareduser"),
    )

    assert p1.status == "ok"
    assert p2.status == "ok"
    # Even though two requests were made concurrently, only 2 HTTP requests (events + repos) were made!
    assert network_hits == 2
