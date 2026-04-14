"""initial: raw_snapshot + computed_sheet

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-14

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT, JSONB

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "raw_snapshot",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", CITEXT, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_schema_version", sa.Integer, nullable=False),
        sa.Column("profile", JSONB, nullable=False),
        sa.Column("events", JSONB, nullable=False),
        sa.Column("contributions", JSONB, nullable=False),
        sa.Column("gists_meta", JSONB, nullable=False),
        sa.UniqueConstraint("username", "fetched_at", name="uq_raw_snapshot_user_time"),
    )
    op.create_index(
        "raw_snapshot_user_time",
        "raw_snapshot",
        ["username", sa.text("fetched_at DESC")],
    )

    op.create_table(
        "computed_sheet",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "raw_snapshot_id",
            sa.BigInteger,
            sa.ForeignKey("raw_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("username", CITEXT, nullable=False),
        sa.Column("engine_version", sa.Integer, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signals", JSONB, nullable=False),
        sa.Column("stats", JSONB, nullable=False),
        sa.Column("flavor", JSONB, nullable=False),
        sa.UniqueConstraint(
            "raw_snapshot_id", "engine_version", name="uq_computed_sheet_raw_engine"
        ),
    )
    op.create_index(
        "computed_sheet_user_time",
        "computed_sheet",
        ["username", sa.text("computed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("computed_sheet_user_time", table_name="computed_sheet")
    op.drop_table("computed_sheet")
    op.drop_index("raw_snapshot_user_time", table_name="raw_snapshot")
    op.drop_table("raw_snapshot")
