from time import time

from lethargy.collector.errors import RateLimitFloorHit


class RateLimitState:
    """In-process snapshot of GitHub's rate-limit headers.

    Updated on every GitHub response; consulted before every request by the
    collector so we never spend the last N points of budget. v0 uses a single
    global budget gauge — GitHub has separate REST and GraphQL pools, so this
    is a lossy blend that tracks whichever was touched last. Acceptable for
    single-user v0 traffic; split into two gauges when hardening.
    """

    def __init__(self, floor: int) -> None:
        self._floor = floor
        self._remaining: int | None = None
        self._reset: int | None = None  # unix seconds

    def update(self, *, remaining: int, reset: int) -> None:
        self._remaining = remaining
        self._reset = reset

    @property
    def remaining(self) -> int | None:
        return self._remaining

    @property
    def reset(self) -> int | None:
        return self._reset

    def seconds_until_reset(self) -> int | None:
        if self._reset is None:
            return None
        return max(0, int(self._reset - time()))

    def check_floor(self) -> None:
        if self._remaining is None or self._remaining >= self._floor:
            return
        raise RateLimitFloorHit(
            f"rate limit remaining={self._remaining} below floor={self._floor}",
            retry_after=self.seconds_until_reset() or 60,
        )
