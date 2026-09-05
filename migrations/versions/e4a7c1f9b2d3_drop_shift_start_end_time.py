"""Drop shifts.start_time and shifts.end_time

Timings are no longer captured when creating/editing a Shift (Admin >
Shifts). The Shift Incharge / station / active-flag fields remain
unchanged. Downgrade re-adds the columns as nullable (original data is
not recoverable), so any environment relying on that data should back
it up before upgrading.

Revision ID: e4a7c1f9b2d3
Revises: d3f4a5b6c7e8
Create Date: 2026-08-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e4a7c1f9b2d3"
down_revision = "d3f4a5b6c7e8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("shifts", schema=None) as batch_op:
        batch_op.drop_column("start_time")
        batch_op.drop_column("end_time")


def downgrade():
    with op.batch_alter_table("shifts", schema=None) as batch_op:
        # Nullable on the way back down - historical values are gone,
        # so we can't reconstruct the original NOT NULL constraint.
        batch_op.add_column(sa.Column("start_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("end_time", sa.Time(), nullable=True))
