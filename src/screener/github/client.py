"""Single choke-point async GitHub API client with rate-limiting circuit breaker and single-flight deduplication."""

import asyncio
from typing import Any, Dict, List, Optional
import httpx
from screener.errors import GitHubError
from screener.extract.contact import GITHUB_USERNAME_REGEX


class GitHubProfileData:
    """Raw parsed data from public GitHub API calls."""

    def __init__(
        self,
        status: str,
        username: str,
        events: Optional[List[Dict[str, Any]]] = None,
        repos: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
    ):
        self.status = status
        self.username = username
        self.events = events or []
        self.repos = repos or []
        self.error_message = error_message


class GitHubClient:
    """
    Dedicated client for api.github.com.
    Protects API quota with in-run cache, single-flight task locking, and circuit breaker.
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: Optional[str] = None,
        timeout_seconds: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.token = token
        self.timeout = timeout_seconds
        self.transport = transport
        self.circuit_broken = False
        self._cache: Dict[str, GitHubProfileData] = {}
        self._inflight: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ResumeScreener-Engine/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def fetch_profile(self, raw_username: str) -> GitHubProfileData:
        """Fetch public events and repos for a validated username."""
        username = raw_username.strip().lower()

        # Validate username with strict regex
        if not GITHUB_USERNAME_REGEX.match(username):
            return GitHubProfileData(status="error", username=username, error_message="Invalid username syntax")

        # 1. Check in-run cache
        if username in self._cache:
            return self._cache[username]

        # 2. Check single-flight in-progress task
        async with self._lock:
            if username in self._cache:
                return self._cache[username]
            if username in self._inflight:
                task = self._inflight[username]
            else:
                task = asyncio.create_task(self._do_fetch_profile(username))
                self._inflight[username] = task

        try:
            res = await task
            self._cache[username] = res
            return res
        finally:
            async with self._lock:
                self._inflight.pop(username, None)

    async def _do_fetch_profile(self, username: str) -> GitHubProfileData:
        if self.circuit_broken:
            return GitHubProfileData(
                status="rate_limited",
                username=username,
                error_message="Circuit breaker open due to prior rate limit",
            )

        headers = self._build_headers()

        async with httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            try:
                # 1. Fetch public events
                events_resp = await client.get(f"/users/{username}/events/public")
                self._check_rate_limit(events_resp)

                if events_resp.status_code == 404:
                    return GitHubProfileData(status="not_found", username=username)
                elif events_resp.status_code in (403, 429):
                    self.circuit_broken = True
                    return GitHubProfileData(status="rate_limited", username=username)
                elif events_resp.status_code != 200:
                    return GitHubProfileData(
                        status="error",
                        username=username,
                        error_message=f"Events returned HTTP {events_resp.status_code}",
                    )

                events = events_resp.json()

                # 2. Fetch repos (sorted by pushed, max 100)
                repos_resp = await client.get(
                    f"/users/{username}/repos",
                    params={"sort": "pushed", "per_page": "100"},
                )
                self._check_rate_limit(repos_resp)

                if repos_resp.status_code in (403, 429):
                    self.circuit_broken = True
                    return GitHubProfileData(status="rate_limited", username=username)
                elif repos_resp.status_code != 200:
                    return GitHubProfileData(
                        status="error",
                        username=username,
                        error_message=f"Repos returned HTTP {repos_resp.status_code}",
                    )

                repos = repos_resp.json()

                return GitHubProfileData(
                    status="ok",
                    username=username,
                    events=events if isinstance(events, list) else [],
                    repos=repos if isinstance(repos, list) else [],
                )

            except httpx.TimeoutException:
                return GitHubProfileData(status="error", username=username, error_message="GitHub request timed out")
            except Exception as e:
                return GitHubProfileData(status="error", username=username, error_message=str(e))

    def _check_rate_limit(self, resp: httpx.Response) -> None:
        rem = resp.headers.get("x-ratelimit-remaining")
        if rem == "0":
            self.circuit_broken = True
