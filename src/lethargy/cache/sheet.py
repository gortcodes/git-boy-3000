from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import msgpack

from lethargy.cache.redis import RedisClient
from lethargy.engine.domain import (
    CharacterSheet,
    CharacterSheetV2,
    SheetBundle,
    SheetBundleV2,
    Signals,
    SignalsV2,
    Stat,
    StatV2,
    SubStatV2,
)

AnyBundle = SheetBundle | SheetBundleV2


@dataclass(frozen=True)
class CachedBundle:
    bundle: AnyBundle
    age_seconds: float


class SheetCache:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def get(self, username: str, engine_version: int) -> CachedBundle | None:
        raw = await self._redis.get_bytes(_key(username, engine_version))
        if raw is None:
            return None
        payload = msgpack.unpackb(raw, raw=False)
        bundle: AnyBundle
        if engine_version == 2:
            bundle = _bundle_from_dict_v2(payload["bundle"])
        else:
            bundle = _bundle_from_dict_v1(payload["bundle"])
        computed_at = datetime.fromisoformat(payload["computed_at"])
        age = (datetime.now(UTC) - computed_at).total_seconds()
        return CachedBundle(bundle=bundle, age_seconds=max(age, 0.0))

    async def put(self, username: str, bundle: AnyBundle, *, ttl: int) -> None:
        key = _key(username, bundle.sheet.engine_version)
        if isinstance(bundle, SheetBundleV2):
            payload_bundle = _bundle_to_dict_v2(bundle)
        else:
            payload_bundle = _bundle_to_dict_v1(bundle)
        payload = {
            "bundle": payload_bundle,
            "computed_at": bundle.sheet.computed_at.isoformat(),
        }
        await self._redis.set_bytes(
            key, msgpack.packb(payload, use_bin_type=True), ex=ttl
        )

    async def delete(self, username: str, engine_version: int) -> None:
        await self._redis.delete(_key(username, engine_version))


def _key(username: str, engine_version: int) -> str:
    return f"lethargy:sheet:{username}:{engine_version}"


def _bundle_to_dict_v1(bundle: SheetBundle) -> dict:
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


def _bundle_from_dict_v1(data: dict) -> SheetBundle:
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


def _bundle_to_dict_v2(bundle: SheetBundleV2) -> dict:
    sheet = bundle.sheet
    return {
        "sheet": {
            "username": sheet.username,
            "engine_version": sheet.engine_version,
            "raw_schema_version": sheet.raw_schema_version,
            "fetched_at": sheet.fetched_at.isoformat(),
            "computed_at": sheet.computed_at.isoformat(),
            "class_name": sheet.class_name,
            "character_level": sheet.character_level,
            "stats": {
                name: {
                    "name": stat.name,
                    "display": stat.display,
                    "level": stat.level,
                    "sub_stats": [
                        {"name": s.name, "level": s.level} for s in stat.sub_stats
                    ],
                }
                for name, stat in sheet.stats.items()
            },
            "flavor": sheet.flavor,
        },
        "signals": asdict(bundle.signals),
    }


def _bundle_from_dict_v2(data: dict) -> SheetBundleV2:
    sheet_data = data["sheet"]
    stats: dict[str, StatV2] = {}
    for name, stat_data in sheet_data["stats"].items():
        sub_stats = [
            SubStatV2(name=s["name"], level=s["level"])
            for s in stat_data["sub_stats"]
        ]
        stats[name] = StatV2(
            name=stat_data["name"],
            display=stat_data["display"],
            level=stat_data["level"],
            sub_stats=sub_stats,
        )
    sheet = CharacterSheetV2(
        username=sheet_data["username"],
        engine_version=sheet_data["engine_version"],
        raw_schema_version=sheet_data["raw_schema_version"],
        fetched_at=datetime.fromisoformat(sheet_data["fetched_at"]),
        computed_at=datetime.fromisoformat(sheet_data["computed_at"]),
        class_name=sheet_data["class_name"],
        character_level=sheet_data["character_level"],
        stats=stats,
        flavor=sheet_data["flavor"],
    )
    signals = SignalsV2(**data["signals"])
    return SheetBundleV2(sheet=sheet, signals=signals)
