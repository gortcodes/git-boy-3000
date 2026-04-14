from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lethargy.engine.domain import CharacterSheet, RawSnapshot, Signals
from lethargy.engine.v1 import extract as _v1_extract
from lethargy.engine.v1 import score as _v1_score


@dataclass(frozen=True)
class Engine:
    version: int
    extract: Callable[[RawSnapshot], Signals]
    score: Callable[..., CharacterSheet]


ENGINES: dict[int, Engine] = {
    1: Engine(version=1, extract=_v1_extract.extract, score=_v1_score.score),
}

LATEST = max(ENGINES)
