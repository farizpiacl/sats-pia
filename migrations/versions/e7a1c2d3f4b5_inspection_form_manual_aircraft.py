"""Inspection Form - PIA dropdown vs manual aircraft registration

Mirrors the Engineer Activity Form's existing PIA/non-PIA aircraft
behaviour on the Engineer Inspection Form:

* `inspection_forms.aircraft_id` is relaxed from NOT NULL to nullable,
  since it is now only populated when the selected airline is PIA.
* Two new nullable columns are added - `aircraft_registration_manual`
  and `aircraft_model_manual` - populated instead of `aircraft_id` when
  the selected airline is anything other than PIA.

Purely additive/relaxing - no existing data is touched, no enum values
are added or changed, and no rows are deleted.

Revision ID: e7a1c2d3f4b5
Revises: d4e5f6a7b8c9
Create Date: 2026-08-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e7a1c2d3f4b5"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inspection_forms") as batch_op:
        batch_op.add_column(sa.Column("aircraft_registration_manual", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("aircraft_model_manual", sa.String(length=100), nullable=True))
        batch_op.alter_column(
            "aircraft_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade():
    # Any inspection rows saved with a manual (non-PIA) registration have
    # no aircraft_id to fall back to, so re-tightening the NOT NULL
    # constraint would fail on real data. Downgrading only removes the
    # manual columns and leaves aircraft_id nullable, which keeps the
    # schema usable; recreating the original hard NOT NULL constraint is
    # intentionally not attempted here.
    with op.batch_alter_table("inspection_forms") as batch_op:
        batch_op.drop_column("aircraft_model_manual")
        batch_op.drop_column("aircraft_registration_manual")
