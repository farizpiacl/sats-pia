"""Flight Coverage destination station + QARI No. of Attempted

Engineer Activity Form changes:

* Adds `activities.destination_station` (String, nullable) - a free-text
  destination the engineer types in when Coverage Type = Flight. No FK,
  no fixed/hardcoded list - purely manual entry, mirroring the existing
  aircraft_registration_manual / aircraft_model_manual pattern.
* Adds `qari_entries.qari_attempted_count` (Integer, nullable) - the new
  "No. of QARI Attempted" numeric field.
* Drops `qari_entries.qari_number` (String) - fully replaced by
  qari_attempted_count; no other code path or report reads this column.

Purely additive/removal of an unused column - no enum values are
touched, so this is safe on both PostgreSQL and SQLite without any
enum-transaction handling.

Revision ID: f4b1a2c3d5e6
Revises: e7a1c2d3f4b5
Create Date: 2026-08-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f4b1a2c3d5e6"
down_revision = "e7a1c2d3f4b5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("activities") as batch_op:
        batch_op.add_column(sa.Column("destination_station", sa.String(length=150), nullable=True))

    with op.batch_alter_table("qari_entries") as batch_op:
        batch_op.add_column(sa.Column("qari_attempted_count", sa.Integer(), nullable=True))
        batch_op.drop_column("qari_number")


def downgrade():
    with op.batch_alter_table("qari_entries") as batch_op:
        batch_op.add_column(sa.Column("qari_number", sa.String(length=50), nullable=True))
        batch_op.drop_column("qari_attempted_count")

    with op.batch_alter_table("activities") as batch_op:
        batch_op.drop_column("destination_station")
