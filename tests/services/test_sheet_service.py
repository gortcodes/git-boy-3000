from datetime import UTC, datetime

from lethargy.cache.lock import LockAcquired, LockContended
from lethargy.cache.sheet import CachedBundle
from lethargy.engine.domain import (
    CharacterSheet,
    RawSnapshot,
    SheetBundle,
    SheetBundleV2,
    Signals,
    Stat,
)
from lethargy.services.sheet_service import SheetService


def _sheet() -> CharacterSheet:
    return CharacterSheet(
        username="test",
        engine_version=1,
        raw_schema_version=1,
        fetched_at=datetime(2026, 4, 14, tzinfo=UTC),
        computed_at=datetime(2026, 4, 14, tzinfo=UTC),
        stats={
            n: Stat(n, 10, 10.0, {})
            for n in ("STR", "DEX", "CON", "INT", "WIS", "CHA")
        },
        flavor={},
    )


def _signals() -> Signals:
    return Signals(
        engine_version=1,
        account_age_days=0,
        activity_span_days=0,
        total_commit_contributions=0,
        total_pr_contributions=0,
        total_pr_review_contributions=0,
        total_issue_contributions=0,
        restricted_contribution_count=0,
        push_event_count=0,
        pr_event_count=0,
        pr_review_event_count=0,
        issue_event_count=0,
        issue_comment_event_count=0,
        distinct_repos_touched=0,
        distinct_external_repos_touched=0,
        gists=0,
        current_streak_days=0,
        longest_streak_days=0,
        weekly_commits=[0] * 52,
        hour_histogram=[0] * 24,
    )


def _bundle() -> SheetBundle:
    return SheetBundle(sheet=_sheet(), signals=_signals())


class _Cache:
    def __init__(self, entry: CachedBundle | None = None):
        self.entry = entry
        self.put_calls = 0

    async def get(self, username, engine_version):
        return self.entry

    async def put(self, username, bundle, *, ttl):
        self.put_calls += 1
        self.entry = CachedBundle(bundle=bundle, age_seconds=0.0)

    async def delete(self, username, engine_version):
        self.entry = None


class _Lock:
    def __init__(self, contended: bool = False):
        self.contended = contended
        self.acquires = 0

    async def acquire(self, username):
        self.acquires += 1
        return LockContended() if self.contended else LockAcquired(token="t")

    async def release(self, username, token):
        pass


class _Throttle:
    def __init__(self, armed: bool = False):
        self.armed = armed

    async def exists(self, username):
        return self.armed

    async def arm(self, username):
        self.armed = True


class _Builder:
    def __init__(self):
        self.calls = 0
        self.last_include_repo_content = False

    async def build(self, username, *, include_repo_content: bool = False):
        self.calls += 1
        self.last_include_repo_content = include_repo_content
        return RawSnapshot(
            username=username,
            fetched_at=datetime(2026, 4, 15, tzinfo=UTC),
            raw_schema_version=2 if include_repo_content else 1,
            profile={"login": username, "created_at": "2020-01-01T00:00:00Z"},
            events=[],
            contributions={},
            gists_meta={"count": 0},
        )


def _service(
    *,
    cache=None,
    lock=None,
    throttle=None,
    builder=None,
    owners=frozenset(),
    fresh=600,
    stale=3000,
    owner_class="TestClass",
) -> SheetService:
    return SheetService(
        snapshot_builder=builder or _Builder(),
        sheet_cache=cache or _Cache(),
        lock=lock or _Lock(),
        throttle=throttle or _Throttle(),
        owner_usernames=owners,
        fresh_ttl_seconds=fresh,
        stale_ttl_seconds=stale,
        owner_class=owner_class,
    )


async def test_fresh_cache_hit_does_not_call_builder():
    cache = _Cache(entry=CachedBundle(bundle=_bundle(), age_seconds=60))
    builder = _Builder()
    service = _service(cache=cache, builder=builder)

    envelope = await service.get_or_refresh("test")

    assert envelope.cache_status == "hit"
    assert builder.calls == 0


async def test_miss_triggers_fetch_and_populates_cache():
    cache = _Cache()
    builder = _Builder()
    service = _service(cache=cache, builder=builder)

    envelope = await service.get_or_refresh("test")

    assert envelope.cache_status == "miss"
    assert builder.calls == 1
    assert cache.put_calls == 1


async def test_throttled_serves_old_cache_without_fetching():
    cache = _Cache(entry=CachedBundle(bundle=_bundle(), age_seconds=4000))
    builder = _Builder()
    throttle = _Throttle(armed=True)
    service = _service(
        cache=cache, builder=builder, throttle=throttle, fresh=600, stale=3000
    )

    envelope = await service.get_or_refresh("test")

    assert envelope.cache_status == "throttled"
    assert builder.calls == 0


async def test_force_is_silently_ignored_for_non_owner():
    cache = _Cache(entry=CachedBundle(bundle=_bundle(), age_seconds=60))
    builder = _Builder()
    service = _service(cache=cache, builder=builder, owners=frozenset())

    envelope = await service.get_or_refresh("stranger", force=True)

    assert envelope.cache_status == "hit"
    assert builder.calls == 0


async def test_owner_routes_to_engine_v2_and_force_bypasses_cache():
    cache = _Cache(entry=CachedBundle(bundle=_bundle(), age_seconds=60))
    builder = _Builder()
    service = _service(
        cache=cache, builder=builder, owners=frozenset({"owneruser"})
    )

    envelope = await service.get_or_refresh("owneruser", force=True)

    assert envelope.cache_status == "forced"
    assert builder.calls == 1
    assert builder.last_include_repo_content is True
    assert isinstance(envelope.bundle, SheetBundleV2)
    assert envelope.bundle.sheet.engine_version == 2
    assert envelope.bundle.sheet.class_name == "TestClass"


async def test_owner_miss_without_force_also_routes_to_v2():
    cache = _Cache()  # no cache entry
    builder = _Builder()
    service = _service(
        cache=cache, builder=builder, owners=frozenset({"owneruser"})
    )

    envelope = await service.get_or_refresh("owneruser")

    assert envelope.cache_status == "miss"
    assert isinstance(envelope.bundle, SheetBundleV2)
    assert builder.last_include_repo_content is True


async def test_non_owner_miss_routes_to_v1():
    cache = _Cache()
    builder = _Builder()
    service = _service(
        cache=cache, builder=builder, owners=frozenset({"owneruser"})
    )

    envelope = await service.get_or_refresh("stranger")

    assert envelope.cache_status == "miss"
    assert isinstance(envelope.bundle, SheetBundle)
    assert envelope.bundle.sheet.engine_version == 1
    assert builder.last_include_repo_content is False
