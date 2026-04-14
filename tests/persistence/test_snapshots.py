import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_URL = os.environ.get("LETHARGY_TEST_DB_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="LETHARGY_TEST_DB_URL not set; persistence tests require a real postgres",
)


@pytest.fixture
async def database():
    from lethargy.persistence.db import Database
    from lethargy.persistence.models import metadata

    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(metadata.create_all)

    yield Database(engine)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


async def test_round_trip_raw_snapshot(database):
    from lethargy.engine.domain import RawSnapshot
    from lethargy.persistence.snapshots import get_snapshot, insert_snapshot

    snap = RawSnapshot(
        username="test-user",
        fetched_at=datetime(2026, 4, 14, 12, tzinfo=UTC),
        raw_schema_version=1,
        profile={"login": "test-user", "id": 42},
        events=[{"type": "PushEvent"}],
        contributions={"totalCommitContributions": 10},
        gists_meta={"count": 2},
    )

    async with database.session() as session:
        async with session.begin():
            snapshot_id = await insert_snapshot(session, snap)
        fetched = await get_snapshot(session, snapshot_id)

    assert fetched is not None
    assert fetched.username == "test-user"
    assert fetched.profile == {"login": "test-user", "id": 42}
    assert fetched.contributions["totalCommitContributions"] == 10
    assert fetched.raw_schema_version == 1


async def test_citext_username_case_insensitive(database):
    from lethargy.engine.domain import RawSnapshot
    from lethargy.persistence.snapshots import insert_snapshot, list_snapshots_for_user

    snap = RawSnapshot(
        username="MixedCase",
        fetched_at=datetime(2026, 4, 14, 12, tzinfo=UTC),
        raw_schema_version=1,
        profile={}, events=[], contributions={}, gists_meta={"count": 0},
    )
    async with database.session() as session:
        async with session.begin():
            await insert_snapshot(session, snap)
        rows = await list_snapshots_for_user(session, "mixedcase")

    assert len(rows) == 1
    assert rows[0]["username"].lower() == "mixedcase"
