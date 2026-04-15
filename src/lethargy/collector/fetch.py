import asyncio
import logging
from datetime import UTC, datetime

from opentelemetry import trace

from lethargy.collector.client import GitHubClient
from lethargy.collector.errors import GitHubError
from lethargy.engine.domain import RawSnapshot
from lethargy.obs.names import SPAN_COLLECTOR_SNAPSHOT_BUILD

RAW_SCHEMA_VERSION_V1 = 1
RAW_SCHEMA_VERSION_V2 = 2

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class SnapshotBuilder:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def build(
        self, username: str, *, include_repo_content: bool = False
    ) -> RawSnapshot:
        with tracer.start_as_current_span(SPAN_COLLECTOR_SNAPSHOT_BUILD):
            if include_repo_content:
                (
                    profile,
                    events,
                    contributions,
                    repos,
                ) = await asyncio.gather(
                    self._client.get_profile(username),
                    self._client.get_public_events(username),
                    self._client.get_contributions(username),
                    self._client.list_user_repos(username),
                )
                repo_trees, repo_languages = await self._fetch_repo_content(repos)
                raw_schema_version = RAW_SCHEMA_VERSION_V2
            else:
                profile, events, contributions = await asyncio.gather(
                    self._client.get_profile(username),
                    self._client.get_public_events(username),
                    self._client.get_contributions(username),
                )
                repos = []
                repo_trees = {}
                repo_languages = {}
                raw_schema_version = RAW_SCHEMA_VERSION_V1

            gists_meta = {"count": profile.get("public_gists", 0)}
            return RawSnapshot(
                username=username,
                fetched_at=datetime.now(UTC),
                raw_schema_version=raw_schema_version,
                profile=profile,
                events=events,
                contributions=contributions,
                gists_meta=gists_meta,
                repos=repos,
                repo_trees=repo_trees,
                repo_languages=repo_languages,
            )

    async def _fetch_repo_content(
        self, repos: list[dict]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, int]]]:
        repo_trees: dict[str, list[str]] = {}
        repo_languages: dict[str, dict[str, int]] = {}

        async def fetch_one(repo: dict) -> None:
            full_name = repo.get("full_name", "")
            if not isinstance(full_name, str) or "/" not in full_name:
                return
            owner, name = full_name.split("/", 1)
            branch = repo.get("default_branch") or "main"

            try:
                tree = await self._client.get_repo_tree(owner, name, branch)
            except GitHubError as exc:
                log.warning("repo tree fetch failed for %s: %s", full_name, exc)
                tree = []
            repo_trees[full_name] = tree

            try:
                langs = await self._client.get_repo_languages(owner, name)
            except GitHubError as exc:
                log.warning("repo languages fetch failed for %s: %s", full_name, exc)
                langs = {}
            repo_languages[full_name] = langs

        await asyncio.gather(
            *(fetch_one(repo) for repo in repos), return_exceptions=True
        )
        return repo_trees, repo_languages
