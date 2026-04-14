from dataclasses import dataclass
from datetime import UTC, datetime

from opentelemetry import trace

from lethargy.collector.fetch import SnapshotBuilder
from lethargy.engine.domain import CharacterSheet, RawSnapshot, Signals
from lethargy.engine.registry import ENGINES, LATEST
from lethargy.obs import metrics as obs_metrics
from lethargy.obs.names import SPAN_SERVICE_SHEET_GET_OR_REFRESH
from lethargy.persistence.db import Database
from lethargy.persistence.sheets import insert_sheet
from lethargy.persistence.snapshots import insert_snapshot

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class SheetBundle:
    sheet: CharacterSheet
    signals: Signals


class SheetService:
    def __init__(
        self,
        snapshot_builder: SnapshotBuilder,
        database: Database,
        owner_usernames: frozenset[str],
    ) -> None:
        self._snapshot_builder = snapshot_builder
        self._database = database
        self._owner_usernames = owner_usernames

    async def get_or_refresh(self, username: str) -> SheetBundle:
        with tracer.start_as_current_span(SPAN_SERVICE_SHEET_GET_OR_REFRESH):
            snapshot = await self._snapshot_builder.build(username)
            engine = ENGINES[LATEST]
            signals = engine.extract(snapshot)
            sheet = engine.score(
                signals,
                username=snapshot.username,
                fetched_at=snapshot.fetched_at,
                computed_at=datetime.now(UTC),
                raw_schema_version=snapshot.raw_schema_version,
            )

            if username.lower() in self._owner_usernames:
                await self._persist_owner(snapshot, sheet, signals)

            return SheetBundle(sheet=sheet, signals=signals)

    async def _persist_owner(
        self,
        snapshot: RawSnapshot,
        sheet: CharacterSheet,
        signals: Signals,
    ) -> None:
        async with self._database.session() as session, session.begin():
            raw_id = await insert_snapshot(session, snapshot)
            await insert_sheet(
                session,
                raw_snapshot_id=raw_id,
                sheet=sheet,
                signals=signals,
            )
        obs_metrics.owner_snapshots_total.labels(username=sheet.username).inc()
