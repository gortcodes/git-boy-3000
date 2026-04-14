from dataclasses import asdict

from sqlalchemy import desc, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from lethargy.engine.domain import CharacterSheet, Signals
from lethargy.persistence.models import computed_sheet


async def insert_sheet(
    session: AsyncSession,
    *,
    raw_snapshot_id: int,
    sheet: CharacterSheet,
    signals: Signals,
) -> int:
    stats_json = {name: asdict(stat) for name, stat in sheet.stats.items()}
    stmt = (
        insert(computed_sheet)
        .values(
            raw_snapshot_id=raw_snapshot_id,
            username=sheet.username,
            engine_version=sheet.engine_version,
            computed_at=sheet.computed_at,
            signals=asdict(signals),
            stats=stats_json,
            flavor=sheet.flavor,
        )
        .returning(computed_sheet.c.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def list_sheets_for_user(
    session: AsyncSession, username: str, limit: int = 20
) -> list[dict]:
    stmt = (
        select(
            computed_sheet.c.id,
            computed_sheet.c.username,
            computed_sheet.c.engine_version,
            computed_sheet.c.computed_at,
            computed_sheet.c.stats,
            computed_sheet.c.flavor,
        )
        .where(computed_sheet.c.username == username)
        .order_by(desc(computed_sheet.c.computed_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [dict(row) for row in rows]
