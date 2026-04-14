import time

import pytest

from lethargy.collector.errors import RateLimitFloorHit
from lethargy.collector.rate_limit import RateLimitState


def test_check_floor_does_nothing_before_first_update():
    state = RateLimitState(floor=100)
    state.check_floor()  # no exception; no observations yet


def test_check_floor_passes_when_remaining_above_floor():
    state = RateLimitState(floor=100)
    state.update(remaining=500, reset=int(time.time()) + 60)
    state.check_floor()


def test_check_floor_raises_when_remaining_below_floor():
    state = RateLimitState(floor=100)
    state.update(remaining=50, reset=int(time.time()) + 120)
    with pytest.raises(RateLimitFloorHit) as excinfo:
        state.check_floor()
    assert excinfo.value.retry_after is not None
    assert 0 <= excinfo.value.retry_after <= 120


def test_seconds_until_reset_clamps_to_zero_after_reset():
    state = RateLimitState(floor=100)
    state.update(remaining=50, reset=int(time.time()) - 10)
    assert state.seconds_until_reset() == 0
