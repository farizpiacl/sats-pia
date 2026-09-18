"""Add SARI activity type, Partially Closed QARI status, qari_closed_count

- Adds 'sari' to the activity_type enum (a QARI-style activity whose
  entries hide the QARI No. field and auto-record both SARI-closed and
  QARI-closed counts from a single "No. of QARI Closed" input).
- Adds 'partially_closed' to the qari_entry_status enum.
- Adds qari_entries.qari_closed_count (Integer, nullable) to store the
  auto-derived QARI-closed count for SARI activities.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'sari'")
        op.execute("ALTER TYPE qari_entry_status ADD VALUE IF NOT EXISTS 'partially_closed'")
        # Newly added enum values can't be used in the same transaction
        # they were added in on PostgreSQL.
        connection.execute(sa.text("COMMIT"))
        connection.execute(sa.text("BEGIN"))
    else:
        # SQLite: VARCHAR + CHECK constraint via batch mode.
        with op.batch_alter_table("activities") as batch_op:
            batch_op.alter_column(
                "activity_type",
                existing_type=sa.Enum(
                    "maintenance_check", "mic_scheduled_maintenance", "qari", "tsr",
                    "pirep_unscheduled_maintenance", "replacement", "cf_removal", "cf",
                    name="activity_type",
                ),
                type_=sa.Enum(
                    "maintenance_check", "mic_scheduled_maintenance", "qari", "sari", "tsr",
                    "pirep_unscheduled_maintenance", "replacement", "cf_removal", "cf",
                    name="activity_type",
                ),
                existing_nullable=False,
            )
        with op.batch_alter_table("qari_entries") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.Enum("open", "closed", name="qari_entry_status"),
                type_=sa.Enum("open", "partially_closed", "closed", name="qari_entry_status"),
                existing_nullable=True,
            )

    op.add_column("qari_entries", sa.Column("qari_closed_count", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("qari_entries", "qari_closed_count")
    # Enum values (Postgres) and the SQLite CHECK constraint are left as
    # the widened superset on downgrade - no data is stranded, consistent
    # with the approach used elsewhere in this migration history (see
    # f1a2b3c4d5e6's downgrade for the same rationale).
