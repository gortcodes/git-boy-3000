from redis.asyncio import Redis

from lethargy.config import Settings


class RedisClient:
    def __init__(self, redis: Redis):
        self._redis = redis

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisClient":
        return cls(Redis.from_url(settings.redis_url))

    async def get_bytes(self, key: str) -> bytes | None:
        return await self._redis.get(key)

    async def set_bytes(self, key: str, value: bytes, *, ex: int | None = None) -> None:
        await self._redis.set(key, value, ex=ex)

    async def set_nx_bytes(self, key: str, value: bytes, *, ex: int) -> bool:
        result = await self._redis.set(key, value, nx=True, ex=ex)
        return result is True

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        count = await self._redis.exists(key)
        return count > 0

    async def close(self) -> None:
        await self._redis.aclose()
