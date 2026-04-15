from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lethargy.engine.v1 import extract as _v1_extract
from lethargy.engine.v1 import score as _v1_score
from lethargy.engine.v2 import extract as _v2_extract
from lethargy.engine.v2 import score as _v2_score


@dataclass(frozen=True)
class Engine:
    version: int
    extract: Callable
    score: Callable


ENGINES: dict[int, Engine] = {
    1: Engine(version=1, extract=_v1_extract.extract, score=_v1_score.score),
    2: Engine(version=2, extract=_v2_extract.extract, score=_v2_score.score),
}

# v2 is registered but not wired into the service layer yet. The service
# hard-codes ENGINES[LATEST] and v2.score requires additional kwargs
# (class_name) that only the owner path will provide. Until burst 3
# implements the owner-vs-guest routing, LATEST stays at 1 so guests
# continue getting the v1 pipeline unchanged.
LATEST = 1
