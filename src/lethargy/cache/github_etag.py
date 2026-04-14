import gzip
import hashlib
from dataclasses import dataclass
from typing import Any

import msgpack

from lethargy.cache.redis import RedisClient

ETAG_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class CachedResponse:
    etag: str
    body: Any


class GitHubEtagCache:
    def __init__(self, redis: RedisClient):
        self._redis = redis

    async def get(self, url: str) -> CachedResponse | None:
        raw = await self._redis.get_bytes(_key(url))
        if raw is None:
            return None
        blob = msgpack.unpackb(raw, raw=False)
        body = msgpack.unpackb(gzip.decompress(blob["body"]), raw=False)
        return CachedResponse(etag=blob["etag"], body=body)

    async def put(self, url: str, *, etag: str, body: Any) -> None:
        payload = {
            "etag": etag,
            "body": gzip.compress(msgpack.packb(body, use_bin_type=True)),
        }
        await self._redis.set_bytes(
            _key(url),
            msgpack.packb(payload, use_bin_type=True),
            ex=ETAG_TTL_SECONDS,
        )


def _key(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()
    return f"lethargy:gh:etag:{digest}"
