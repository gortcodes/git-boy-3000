from sqlalchemy import desc, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from lethargy.engine.domain import RawSnapshot
from lethargy.persistence.models import raw_snapshot


async def insert_snapshot(session: AsyncSession, snapshot: RawSnapshot) -> int:
    stmt = (
        insert(raw_snapshot)
        .values(
            username=snapshot.username,
            fetched_at=snapshot.fetched_at,
            raw_schema_version=snapshot.raw_schema_version,
            profile=snapshot.profile,
            events=snapshot.events,
            contributions=snapshot.contributions,
            gists_meta=snapshot.gists_meta,
        )
        .returning(raw_snapshot.c.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


def _row_to_snapshot(row) -> RawSnapshot:
    return RawSnapshot(
        username=row["username"],
        fetched_at=row["fetched_at"],
        raw_schema_version=row["raw_schema_version"],
        profile=row["profile"],
        events=row["events"],
        contributions=row["contributions"],
        gists_meta=row["gists_meta"],
    )


async def get_snapshot(session: AsyncSession, snapshot_id: int) -> RawSnapshot | None:
    stmt = select(raw_snapshot).where(raw_snapshot.c.id == snapshot_id)
    row = (await session.execute(stmt)).mappings().first()
    return _row_to_snapshot(row) if row is not None else None


async def get_latest_snapshot_for_user(
    session: AsyncSession, username: str
) -> RawSnapshot | None:
    stmt = (
        select(raw_snapshot)
        .where(raw_snapshot.c.username == username)
        .order_by(desc(raw_snapshot.c.fetched_at))
        .limit(1)
    )
    row = (await session.execute(stmt)).mappings().first()
    return _row_to_snapshot(row) if row is not None else None


async def list_snapshots_for_user(
    session: AsyncSession, username: str, limit: int = 20
) -> list[dict]:
    stmt = (
        select(
            raw_snapshot.c.id,
            raw_snapshot.c.username,
            raw_snapshot.c.fetched_at,
            raw_snapshot.c.raw_schema_version,
        )
        .where(raw_snapshot.c.username == username)
        .order_by(desc(raw_snapshot.c.fetched_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [dict(row) for row in rows]
