import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from opentelemetry import trace

from lethargy.cache.lock import Lock, LockContended
from lethargy.cache.sheet import SheetCache
from lethargy.cache.throttle import Throttle
from lethargy.collector.errors import GitHubUnavailable
from lethargy.collector.fetch import SnapshotBuilder
from lethargy.engine.domain import SheetBundle, SheetBundleV2
from lethargy.engine.registry import ENGINES
from lethargy.obs import metrics as obs_metrics
from lethargy.obs.names import SPAN_SERVICE_SHEET_GET_OR_REFRESH

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

AnyBundle = SheetBundle | SheetBundleV2


@dataclass(frozen=True)
class SheetEnvelope:
    bundle: AnyBundle
    cache_status: str  # hit | stale | miss | throttled | forced


class SheetService:
    def __init__(
        self,
        snapshot_builder: SnapshotBuilder,
        sheet_cache: SheetCache,
        lock: Lock,
        throttle: Throttle,
        owner_usernames: frozenset[str],
        fresh_ttl_seconds: int,
        stale_ttl_seconds: int,
        owner_class: str,
    ) -> None:
        self._snapshot_builder = snapshot_builder
        self._sheet_cache = sheet_cache
        self._lock = lock
        self._throttle = throttle
        self._owner_usernames = owner_usernames
        self._fresh_ttl = fresh_ttl_seconds
        self._stale_ttl = stale_ttl_seconds
        self._owner_class = owner_class
        self._background_tasks: set[asyncio.Task] = set()

    def _engine_version_for(self, key: str) -> int:
        return 2 if key in self._owner_usernames else 1

    async def get_or_refresh(
        self, username: str, *, force: bool = False
    ) -> SheetEnvelope:
        key = username.lower()
        is_owner = key in self._owner_usernames
        engine_version = self._engine_version_for(key)

        # v0 force gate: only owners may bypass the cache. See memory
        # "multi-user future" for the long-term replacement.
        if force and not is_owner:
            force = False

        with tracer.start_as_current_span(SPAN_SERVICE_SHEET_GET_OR_REFRESH) as span:
            span.set_attribute("force", force)
            span.set_attribute("engine.version", engine_version)

            cached = await self._sheet_cache.get(key, engine_version)

            if cached is not None and not force:
                if cached.age_seconds < self._fresh_ttl:
                    _record_cache("hit")
                    return SheetEnvelope(bundle=cached.bundle, cache_status="hit")
                if cached.age_seconds < self._fresh_ttl + self._stale_ttl:
                    _record_cache("stale")
                    task = asyncio.create_task(
                        self._refresh_background(username, engine_version=engine_version)
                    )
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                    return SheetEnvelope(bundle=cached.bundle, cache_status="stale")
                # cache too old — fall through to a synchronous refresh

            if not force and cached is not None and await self._throttle.exists(key):
                _record_cache("throttled")
                return SheetEnvelope(bundle=cached.bundle, cache_status="throttled")

            outcome = await self._lock.acquire(key)
            if isinstance(outcome, LockContended):
                if cached is not None:
                    _record_cache("stale")
                    return SheetEnvelope(bundle=cached.bundle, cache_status="stale")
                raise GitHubUnavailable("refresh in progress; try again")

            try:
                bundle = await self._compute(username, engine_version=engine_version)
                await self._sheet_cache.put(
                    key, bundle, ttl=self._fresh_ttl + self._stale_ttl
                )
                await self._throttle.arm(key)
                status = "forced" if force else "miss"
                _record_cache(status)
                return SheetEnvelope(bundle=bundle, cache_status=status)
            finally:
                await self._lock.release(key, outcome.token)

    async def _refresh_background(
        self, username: str, *, engine_version: int
    ) -> None:
        key = username.lower()
        try:
            outcome = await self._lock.acquire(key)
            if isinstance(outcome, LockContended):
                return
            try:
                bundle = await self._compute(username, engine_version=engine_version)
                await self._sheet_cache.put(
                    key, bundle, ttl=self._fresh_ttl + self._stale_ttl
                )
                await self._throttle.arm(key)
            finally:
                await self._lock.release(key, outcome.token)
        except Exception:
            log.exception("background refresh failed for %s", username)

    async def _compute(
        self, username: str, *, engine_version: int
    ) -> AnyBundle:
        is_owner = username.lower() in self._owner_usernames
        snapshot = await self._snapshot_builder.build(
            username, include_repo_content=is_owner
        )
        engine = ENGINES[engine_version]
        signals = engine.extract(snapshot)
        now = datetime.now(UTC)

        if engine_version == 2:
            sheet = engine.score(
                signals,
                username=snapshot.username,
                class_name=self._owner_class,
                fetched_at=snapshot.fetched_at,
                computed_at=now,
                raw_schema_version=snapshot.raw_schema_version,
            )
            return SheetBundleV2(sheet=sheet, signals=signals)

        sheet = engine.score(
            signals,
            username=snapshot.username,
            fetched_at=snapshot.fetched_at,
            computed_at=now,
            raw_schema_version=snapshot.raw_schema_version,
        )
        return SheetBundle(sheet=sheet, signals=signals)


def _record_cache(result: str) -> None:
    obs_metrics.sheet_cache_result_total.labels(result=result).inc()
