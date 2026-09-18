"""Remove the Approval/Rejection workflow

Engineer-created tasks are now immediately active and visible to IS, DCE,
and Super Admin - there is no submit-for-approval / approve / reject step
anywhere in the system any more. This migration drops the now-unused
approval-related columns, their indexes, and the associated enum types
from both `activities` and `inspection_forms`.

Dropped from `activities`:
    approval_status, approval_remarks, approved_by_id, approved_at
    (plus indexes ix_activities_station_status, ix_activities_type_status,
    ix_activities_engineer_status, replaced with plain non-status indexes)

Dropped from `inspection_forms`:
    approval_status, approval_remarks, approved_by_id, approved_at
    (plus indexes ix_inspection_forms_station_status,
    ix_inspection_forms_engineer_status, replaced with plain indexes)

Enum types `approval_status` and `inspection_approval_status` are dropped
entirely (Postgres only - no-op on SQLite).

Revision ID: a9c4e1f7b3d2
Revises: b1c2d3e4f5a6
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9c4e1f7b3d2"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


APPROVAL_STATUS_VALUES = ("pending_approval", "approved", "rejected")


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # -------------------- activities --------------------
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_index("ix_activities_station_status")
        batch_op.drop_index("ix_activities_type_status")
        batch_op.drop_index("ix_activities_engineer_status")
        batch_op.drop_index("ix_activities_approval_status")
        batch_op.drop_index("ix_activities_approved_by_id")

        batch_op.drop_column("approval_status")
        batch_op.drop_column("approval_remarks")
        batch_op.drop_column("approved_by_id")
        batch_op.drop_column("approved_at")

        batch_op.create_index("ix_activities_station", ["station_id"])
        batch_op.create_index("ix_activities_type", ["activity_type"])
        batch_op.create_index("ix_activities_engineer", ["logged_by_id"])

    # -------------------- inspection_forms --------------------
    with op.batch_alter_table("inspection_forms", schema=None) as batch_op:
        batch_op.drop_index("ix_inspection_forms_station_status")
        batch_op.drop_index("ix_inspection_forms_engineer_status")
        batch_op.drop_index("ix_inspection_forms_approval_status")
        batch_op.drop_index("ix_inspection_forms_approved_by_id")

        batch_op.drop_column("approval_status")
        batch_op.drop_column("approval_remarks")
        batch_op.drop_column("approved_by_id")
        batch_op.drop_column("approved_at")

        batch_op.create_index("ix_inspection_forms_station", ["station_id"])
        batch_op.create_index("ix_inspection_forms_engineer", ["primary_engineer_id"])

    # Drop the now-unused enum types (Postgres only).
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS approval_status")
        op.execute("DROP TYPE IF EXISTS inspection_approval_status")


def downgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    approval_status_enum = sa.Enum(*APPROVAL_STATUS_VALUES, name="approval_status")
    inspection_approval_status_enum = sa.Enum(*APPROVAL_STATUS_VALUES, name="inspection_approval_status")
    if is_postgres:
        approval_status_enum.create(bind, checkfirst=True)
        inspection_approval_status_enum.create(bind, checkfirst=True)

    # -------------------- activities --------------------
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_index("ix_activities_engineer")
        batch_op.drop_index("ix_activities_type")
        batch_op.drop_index("ix_activities_station")

        batch_op.add_column(sa.Column(
            "approval_status", approval_status_enum,
            nullable=False, server_default="pending_approval",
        ))
        batch_op.add_column(sa.Column("approval_remarks", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column(
            "approved_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))

        batch_op.create_index("ix_activities_station_status", ["station_id", "approval_status"])
        batch_op.create_index("ix_activities_type_status", ["activity_type", "approval_status"])
        batch_op.create_index("ix_activities_engineer_status", ["logged_by_id", "approval_status"])
        batch_op.create_index("ix_activities_approval_status", ["approval_status"])
        batch_op.create_index("ix_activities_approved_by_id", ["approved_by_id"])

    # -------------------- inspection_forms --------------------
    with op.batch_alter_table("inspection_forms", schema=None) as batch_op:
        batch_op.drop_index("ix_inspection_forms_engineer")
        batch_op.drop_index("ix_inspection_forms_station")

        batch_op.add_column(sa.Column(
            "approval_status", inspection_approval_status_enum,
            nullable=False, server_default="pending_approval",
        ))
        batch_op.add_column(sa.Column("approval_remarks", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column(
            "approved_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))

        batch_op.create_index("ix_inspection_forms_station_status", ["station_id", "approval_status"])
        batch_op.create_index("ix_inspection_forms_engineer_status", ["primary_engineer_id", "approval_status"])
