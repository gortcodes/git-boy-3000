from datetime import UTC, datetime

from opentelemetry import trace

from lethargy.engine.domain import CharacterSheet
from lethargy.engine.registry import ENGINES
from lethargy.persistence.db import Database
from lethargy.persistence.snapshots import get_latest_snapshot_for_user
from lethargy.services.errors import NoHistoryAvailable, UnknownEngineVersion

tracer = trace.get_tracer(__name__)


class ReplayService:
    def __init__(
        self,
        database: Database,
        owner_usernames: frozenset[str],
    ) -> None:
        self._database = database
        self._owner_usernames = owner_usernames

    async def recompute(self, username: str, engine_version: int) -> CharacterSheet:
        if engine_version not in ENGINES:
            raise UnknownEngineVersion(engine_version)

        if username.lower() not in self._owner_usernames:
            raise NoHistoryAvailable(username)

        async with self._database.session() as session:
            snapshot = await get_latest_snapshot_for_user(session, username)

        if snapshot is None:
            raise NoHistoryAvailable(username)

        engine = ENGINES[engine_version]
        signals = engine.extract(snapshot)
        return engine.score(
            signals,
            username=snapshot.username,
            fetched_at=snapshot.fetched_at,
            computed_at=datetime.now(UTC),
            raw_schema_version=snapshot.raw_schema_version,
        )
