import time
from typing import Any

import httpx
from opentelemetry import trace

from lethargy.cache.github_etag import GitHubEtagCache
from lethargy.collector.errors import (
    GitHubUnavailable,
    RateLimited,
    UserNotFound,
)
from lethargy.config import Settings
from lethargy.obs import metrics as obs_metrics
from lethargy.obs.names import SPAN_COLLECTOR_GITHUB_PROFILE

GITHUB_API = "https://api.github.com"
USER_AGENT = "lethargy.io/0.1 (+https://lethargy.io)"

tracer = trace.get_tracer(__name__)


class GitHubClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient,
        etag_cache: GitHubEtagCache,
    ) -> None:
        self._settings = settings
        self._http = http
        self._etag_cache = etag_cache

    async def get_profile(self, username: str) -> dict[str, Any]:
        with tracer.start_as_current_span(SPAN_COLLECTOR_GITHUB_PROFILE):
            return await self._conditional_get(
                url=f"{GITHUB_API}/users/{username}",
                endpoint_label="users.get",
                not_found_exc=UserNotFound,
            )

    async def _conditional_get(
        self,
        *,
        url: str,
        endpoint_label: str,
        not_found_exc: type[Exception] = GitHubUnavailable,
    ) -> dict[str, Any]:
        headers = self._auth_headers()
        cached = await self._etag_cache.get(url)
        if cached is not None:
            headers["If-None-Match"] = cached.etag

        try:
            response = await self._http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            _inc_requests(endpoint_label, "error", "miss")
            raise GitHubUnavailable(str(exc)) from exc

        _update_rate_limit(response)

        status = response.status_code

        if status == 304 and cached is not None:
            _inc_requests(endpoint_label, "304", "etag")
            return cached.body

        if status == 200:
            body = response.json()
            etag = response.headers.get("ETag")
            if etag:
                await self._etag_cache.put(url, etag=etag, body=body)
            _inc_requests(endpoint_label, "200", "miss")
            return body

        if status == 404:
            _inc_requests(endpoint_label, "404", "miss")
            raise not_found_exc(url)

        if status == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            _inc_requests(endpoint_label, "403", "miss")
            raise RateLimited("GitHub rate limit exhausted")

        _inc_requests(endpoint_label, str(status), "miss")
        raise GitHubUnavailable(f"unexpected status {status} from {url}")

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._settings.github_token:
            headers["Authorization"] = f"Bearer {self._settings.github_token}"
        return headers


def _inc_requests(endpoint: str, status: str, cache: str) -> None:
    obs_metrics.collector_github_requests_total.labels(
        endpoint=endpoint, status=status, cache=cache
    ).inc()


def _update_rate_limit(response: httpx.Response) -> None:
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if remaining is not None and remaining.isdigit():
        obs_metrics.github_rate_limit_remaining.set(int(remaining))
    if reset is not None and reset.isdigit():
        delta = max(0.0, int(reset) - time.time())
        obs_metrics.github_rate_limit_reset_seconds.set(delta)
