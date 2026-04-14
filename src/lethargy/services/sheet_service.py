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
from lethargy.engine.domain import CharacterSheet, RawSnapshot, SheetBundle, Signals
from lethargy.engine.registry import ENGINES, LATEST
from lethargy.obs import metrics as obs_metrics
from lethargy.obs.names import SPAN_SERVICE_SHEET_GET_OR_REFRESH
from lethargy.persistence.db import Database
from lethargy.persistence.sheets import insert_sheet
from lethargy.persistence.snapshots import insert_snapshot

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class SheetEnvelope:
    bundle: SheetBundle
    cache_status: str  # hit | stale | miss | throttled | forced


class SheetService:
    def __init__(
        self,
        snapshot_builder: SnapshotBuilder,
        database: Database | None,
        sheet_cache: SheetCache,
        lock: Lock,
        throttle: Throttle,
        owner_usernames: frozenset[str],
        fresh_ttl_seconds: int,
        stale_ttl_seconds: int,
    ) -> None:
        self._snapshot_builder = snapshot_builder
        self._database = database
        self._sheet_cache = sheet_cache
        self._lock = lock
        self._throttle = throttle
        self._owner_usernames = owner_usernames
        self._fresh_ttl = fresh_ttl_seconds
        self._stale_ttl = stale_ttl_seconds
        self._background_tasks: set[asyncio.Task] = set()

    async def get_or_refresh(
        self, username: str, *, force: bool = False
    ) -> SheetEnvelope:
        key = username.lower()

        # v0 force gate: only owners may bypass the cache. See memory
        # "multi-user future" for the long-term replacement.
        if force and key not in self._owner_usernames:
            force = False

        with tracer.start_as_current_span(SPAN_SERVICE_SHEET_GET_OR_REFRESH) as span:
            span.set_attribute("force", force)

            cached = await self._sheet_cache.get(key, LATEST)

            if cached is not None and not force:
                if cached.age_seconds < self._fresh_ttl:
                    _record_cache("hit")
                    return SheetEnvelope(bundle=cached.bundle, cache_status="hit")
                if cached.age_seconds < self._fresh_ttl + self._stale_ttl:
                    _record_cache("stale")
                    task = asyncio.create_task(self._refresh_background(username))
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
                bundle = await self._compute_and_persist(username)
                await self._sheet_cache.put(
                    key, bundle, ttl=self._fresh_ttl + self._stale_ttl
                )
                await self._throttle.arm(key)
                status = "forced" if force else "miss"
                _record_cache(status)
                return SheetEnvelope(bundle=bundle, cache_status=status)
            finally:
                await self._lock.release(key, outcome.token)

    async def _refresh_background(self, username: str) -> None:
        key = username.lower()
        try:
            outcome = await self._lock.acquire(key)
            if isinstance(outcome, LockContended):
                return
            try:
                bundle = await self._compute_and_persist(username)
                await self._sheet_cache.put(
                    key, bundle, ttl=self._fresh_ttl + self._stale_ttl
                )
                await self._throttle.arm(key)
            finally:
                await self._lock.release(key, outcome.token)
        except Exception:
            log.exception("background refresh failed for %s", username)

    async def _compute_and_persist(self, username: str) -> SheetBundle:
        snapshot = await self._snapshot_builder.build(username)
        engine = ENGINES[LATEST]
        signals = engine.extract(snapshot)
        sheet = engine.score(
            signals,
            username=snapshot.username,
            fetched_at=snapshot.fetched_at,
            computed_at=datetime.now(UTC),
            raw_schema_version=snapshot.raw_schema_version,
        )
        if username.lower() in self._owner_usernames:
            await self._persist_owner(snapshot, sheet, signals)
        return SheetBundle(sheet=sheet, signals=signals)

    async def _persist_owner(
        self,
        snapshot: RawSnapshot,
        sheet: CharacterSheet,
        signals: Signals,
    ) -> None:
        if self._database is None:
            return
        async with self._database.session() as session, session.begin():
            raw_id = await insert_snapshot(session, snapshot)
            await insert_sheet(
                session,
                raw_snapshot_id=raw_id,
                sheet=sheet,
                signals=signals,
            )
        obs_metrics.owner_snapshots_total.labels(username=sheet.username).inc()


def _record_cache(result: str) -> None:
    obs_metrics.sheet_cache_result_total.labels(result=result).inc()
