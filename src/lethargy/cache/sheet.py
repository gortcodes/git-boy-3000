from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import msgpack

from lethargy.cache.redis import RedisClient
from lethargy.engine.domain import CharacterSheet, SheetBundle, Signals, Stat


@dataclass(frozen=True)
class CachedBundle:
    bundle: SheetBundle
    age_seconds: float


class SheetCache:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def get(self, username: str, engine_version: int) -> CachedBundle | None:
        raw = await self._redis.get_bytes(_key(username, engine_version))
        if raw is None:
            return None
        payload = msgpack.unpackb(raw, raw=False)
        bundle = _bundle_from_dict(payload["bundle"])
        computed_at = datetime.fromisoformat(payload["computed_at"])
        age = (datetime.now(UTC) - computed_at).total_seconds()
        return CachedBundle(bundle=bundle, age_seconds=max(age, 0.0))

    async def put(self, username: str, bundle: SheetBundle, *, ttl: int) -> None:
        key = _key(username, bundle.sheet.engine_version)
        payload = {
            "bundle": _bundle_to_dict(bundle),
            "computed_at": bundle.sheet.computed_at.isoformat(),
        }
        await self._redis.set_bytes(
            key, msgpack.packb(payload, use_bin_type=True), ex=ttl
        )

    async def delete(self, username: str, engine_version: int) -> None:
        await self._redis.delete(_key(username, engine_version))


def _key(username: str, engine_version: int) -> str:
    return f"lethargy:sheet:{username}:{engine_version}"


def _bundle_to_dict(bundle: SheetBundle) -> dict:
    sheet = bundle.sheet
    return {
        "sheet": {
            "username": sheet.username,
            "engine_version": sheet.engine_version,
            "raw_schema_version": sheet.raw_schema_version,
            "fetched_at": sheet.fetched_at.isoformat(),
            "computed_at": sheet.computed_at.isoformat(),
            "stats": {name: asdict(stat) for name, stat in sheet.stats.items()},
            "flavor": sheet.flavor,
        },
        "signals": asdict(bundle.signals),
    }


def _bundle_from_dict(data: dict) -> SheetBundle:
    sheet_data = data["sheet"]
    stats = {
        name: Stat(**stat_data) for name, stat_data in sheet_data["stats"].items()
    }
    sheet = CharacterSheet(
        username=sheet_data["username"],
        engine_version=sheet_data["engine_version"],
        raw_schema_version=sheet_data["raw_schema_version"],
        fetched_at=datetime.fromisoformat(sheet_data["fetched_at"]),
        computed_at=datetime.fromisoformat(sheet_data["computed_at"]),
        stats=stats,
        flavor=sheet_data["flavor"],
    )
    signals = Signals(**data["signals"])
    return SheetBundle(sheet=sheet, signals=signals)
