import uuid
from dataclasses import dataclass

from opentelemetry import trace

from lethargy.cache.redis import RedisClient
from lethargy.obs.names import SPAN_CACHE_LOCK_ACQUIRE, SPAN_CACHE_LOCK_RELEASE

LOCK_TTL_SECONDS = 30

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class LockAcquired:
    token: str


@dataclass(frozen=True)
class LockContended:
    pass


LockOutcome = LockAcquired | LockContended


class Lock:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def acquire(self, username: str) -> LockOutcome:
        with tracer.start_as_current_span(SPAN_CACHE_LOCK_ACQUIRE):
            token = uuid.uuid4().hex
            ok = await self._redis.set_nx_bytes(
                _key(username), token.encode(), ex=LOCK_TTL_SECONDS
            )
            return LockAcquired(token=token) if ok else LockContended()

    async def release(self, username: str, token: str) -> None:
        with tracer.start_as_current_span(SPAN_CACHE_LOCK_RELEASE):
            await self._redis.delete(_key(username))


def _key(username: str) -> str:
    return f"lethargy:lock:{username}"
