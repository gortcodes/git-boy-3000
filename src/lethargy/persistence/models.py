from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB

metadata = MetaData()

raw_snapshot = Table(
    "raw_snapshot",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("username", CITEXT, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("raw_schema_version", Integer, nullable=False),
    Column("profile", JSONB, nullable=False),
    Column("events", JSONB, nullable=False),
    Column("contributions", JSONB, nullable=False),
    Column("gists_meta", JSONB, nullable=False),
    UniqueConstraint("username", "fetched_at", name="uq_raw_snapshot_user_time"),
)

Index(
    "raw_snapshot_user_time",
    raw_snapshot.c.username,
    text("fetched_at DESC"),
)

computed_sheet = Table(
    "computed_sheet",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "raw_snapshot_id",
        BigInteger,
        ForeignKey("raw_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("username", CITEXT, nullable=False),
    Column("engine_version", Integer, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    Column("signals", JSONB, nullable=False),
    Column("stats", JSONB, nullable=False),
    Column("flavor", JSONB, nullable=False),
    UniqueConstraint(
        "raw_snapshot_id", "engine_version", name="uq_computed_sheet_raw_engine"
    ),
)

Index(
    "computed_sheet_user_time",
    computed_sheet.c.username,
    text("computed_at DESC"),
)
