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

# LATEST is the newest registered engine. The service layer picks v1 or v2
# explicitly per request based on whether the username is in the owner set,
# so LATEST is only reported via /v1/engine/versions and not used as a
# runtime dispatch key.
LATEST = max(ENGINES)
