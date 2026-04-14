import asyncio
from datetime import UTC, datetime

from opentelemetry import trace

from lethargy.collector.client import GitHubClient
from lethargy.engine.domain import RawSnapshot
from lethargy.obs.names import SPAN_COLLECTOR_SNAPSHOT_BUILD

RAW_SCHEMA_VERSION = 1

tracer = trace.get_tracer(__name__)


class SnapshotBuilder:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def build(self, username: str) -> RawSnapshot:
        with tracer.start_as_current_span(SPAN_COLLECTOR_SNAPSHOT_BUILD):
            profile, events, contributions = await asyncio.gather(
                self._client.get_profile(username),
                self._client.get_public_events(username),
                self._client.get_contributions(username),
            )

        gists_meta = {"count": profile.get("public_gists", 0)}
        return RawSnapshot(
            username=username,
            fetched_at=datetime.now(UTC),
            raw_schema_version=RAW_SCHEMA_VERSION,
            profile=profile,
            events=events,
            contributions=contributions,
            gists_meta=gists_meta,
        )
