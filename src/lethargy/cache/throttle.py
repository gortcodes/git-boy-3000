from opentelemetry import trace

from lethargy.cache.redis import RedisClient
from lethargy.obs.names import SPAN_CACHE_THROTTLE_ARM, SPAN_CACHE_THROTTLE_CHECK

tracer = trace.get_tracer(__name__)


class Throttle:
    def __init__(self, redis: RedisClient, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def exists(self, username: str) -> bool:
        with tracer.start_as_current_span(SPAN_CACHE_THROTTLE_CHECK):
            return await self._redis.exists(_key(username))

    async def arm(self, username: str) -> None:
        with tracer.start_as_current_span(SPAN_CACHE_THROTTLE_ARM):
            await self._redis.set_bytes(_key(username), b"1", ex=self._ttl)


def _key(username: str) -> str:
    return f"lethargy:throttle:{username}"
