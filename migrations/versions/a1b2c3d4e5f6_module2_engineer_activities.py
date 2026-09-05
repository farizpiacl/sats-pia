"""Module 2: rebuild activities table for full Engineer Operations schema

Revision ID: a1b2c3d4e5f6
Revises: fb88ee4f90bc
Create Date: 2026-08-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fb88ee4f90bc"
branch_labels = None
depends_on = None


def _enum_type(is_pg, *values, name):
    """Build the right Enum column type for the current dialect.

    On postgres this must be the dialect-specific `postgresql.ENUM` with
    `create_type=False` - the generic `sa.Enum(..., create_type=False)`
    does NOT reliably suppress the implicit `CREATE TYPE` that
    op.create_table() issues (the generic Enum's create_type flag isn't
    honored the same way), so plain sa.Enum would still try to (and
    fail to) create a type that already exists. On sqlite there's no
    native enum type at all, so the plain sa.Enum (VARCHAR + CHECK) is
    used and create_type is irrelevant.
    """
    if is_pg:
        return PG_ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def _create_pg_enum_if_missing(connection, name, values):
    """Create a PostgreSQL enum type only if it doesn't already exist.

    Alembic's op.create_table() does not check for pre-existing named
    types before emitting `CREATE TYPE` for enum columns (checkfirst is
    not applied there the way it is for plain metadata.create_all()), so
    if the type already exists in the database - e.g. left over from a
    previous partial run, or created manually - the migration fails with
    `psycopg2.errors.DuplicateObject`. Creating it explicitly here, only
    when missing, makes the migration safe to run against a database
    that already has the type, without touching any existing data.
    """
    exists = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name},
    ).first()
    if exists:
        return
    enum = sa.Enum(*values, name=name)
    enum.create(connection, checkfirst=True)


def upgrade():
    connection = op.get_bind()
    is_pg = connection.dialect.name == "postgresql"

    # Module 1 shipped `activities` as a placeholder schema only (no data
    # is seeded anywhere in this system), so it's safe to rebuild it here
    # for the full Engineer Operations module.
    op.drop_table("activities")

    if is_pg:
        # Create every enum type used by this table up front, but only if
        # it isn't already present (see _create_pg_enum_if_missing). The
        # columns below then reference these types with create_type=False
        # so op.create_table() never tries to create them itself.
        _create_pg_enum_if_missing(connection, "activity_type", (
            "aircraft_inspection", "technical_inspection", "transit_inspection", "flight_inspection",
            "maintenance", "replacement", "fixing_rectification", "wheel_change", "tsr", "mic",
            "quality_inspection_ri", "scheduled_maintenance", "unscheduled_maintenance",
            "carry_forward_maintenance", "other",
        ))
        _create_pg_enum_if_missing(connection, "maintenance_type", ("scheduled", "unscheduled", "carry_forward"))
        _create_pg_enum_if_missing(connection, "maintenance_status", ("completed", "in_progress", "carry_forward", "overdue"))
        _create_pg_enum_if_missing(connection, "tsr_status", ("open", "in_progress", "closed"))
        _create_pg_enum_if_missing(connection, "mic_status", ("open", "in_progress", "closed"))
        _create_pg_enum_if_missing(connection, "quality_status", ("passed", "failed", "observation", "pending"))
        _create_pg_enum_if_missing(connection, "approval_status", ("pending_approval", "approved", "rejected"))

    # create_type=False on every Enum below: on postgres the types are
    # already guaranteed to exist (created idempotently above); on
    # sqlite create_type has no effect (Enum becomes VARCHAR + CHECK).
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),

        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("logged_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("aircraft_id", sa.Integer(), sa.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True),

        sa.Column(
            "activity_type",
            _enum_type(
                is_pg,
                "aircraft_inspection", "technical_inspection", "transit_inspection", "flight_inspection",
                "maintenance", "replacement", "fixing_rectification", "wheel_change", "tsr", "mic",
                "quality_inspection_ri", "scheduled_maintenance", "unscheduled_maintenance",
                "carry_forward_maintenance", "other",
                name="activity_type",
            ),
            nullable=False,
        ),

        sa.Column("num_aircraft_checked", sa.Integer(), nullable=True),
        sa.Column("inspection_details", sa.Text(), nullable=True),
        sa.Column("inspection_result", sa.String(length=50), nullable=True),

        sa.Column("flight_number", sa.String(length=20), nullable=True),
        sa.Column("engineer_sent_with_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("departure_time", sa.Time(), nullable=True),
        sa.Column("arrival_time", sa.Time(), nullable=True),
        sa.Column("inspection_performed", sa.Boolean(), nullable=True),

        sa.Column(
            "maintenance_type",
            _enum_type(is_pg, "scheduled", "unscheduled", "carry_forward", name="maintenance_type"),
            nullable=True,
        ),
        sa.Column("component", sa.String(length=150), nullable=True),
        sa.Column("maintenance_details", sa.Text(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column(
            "maintenance_status",
            _enum_type(is_pg, "completed", "in_progress", "carry_forward", "overdue", name="maintenance_status"),
            nullable=True,
        ),

        sa.Column("tsr_number", sa.String(length=50), nullable=True),
        sa.Column("tsr_status", _enum_type(is_pg, "open", "in_progress", "closed", name="tsr_status"), nullable=True),

        sa.Column("mic_number", sa.String(length=50), nullable=True),
        sa.Column("mic_status", _enum_type(is_pg, "open", "in_progress", "closed", name="mic_status"), nullable=True),

        sa.Column("quality_inspection_type", sa.String(length=100), nullable=True),
        sa.Column("quality_finding", sa.Text(), nullable=True),
        sa.Column(
            "quality_status",
            _enum_type(is_pg, "passed", "failed", "observation", "pending", name="quality_status"),
            nullable=True,
        ),

        sa.Column("remarks", sa.Text(), nullable=True),

        sa.Column(
            "approval_status",
            _enum_type(is_pg, "pending_approval", "approved", "rejected", name="approval_status"),
            nullable=False,
            server_default="pending_approval",
        ),
        sa.Column("approval_remarks", sa.String(length=500), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.create_index("ix_activities_activity_date", ["activity_date"], unique=False)
        batch_op.create_index("ix_activities_station_id", ["station_id"], unique=False)
        batch_op.create_index("ix_activities_shift_id", ["shift_id"], unique=False)
        batch_op.create_index("ix_activities_logged_by_id", ["logged_by_id"], unique=False)
        batch_op.create_index("ix_activities_aircraft_id", ["aircraft_id"], unique=False)
        batch_op.create_index("ix_activities_activity_type", ["activity_type"], unique=False)
        batch_op.create_index("ix_activities_engineer_sent_with_id", ["engineer_sent_with_id"], unique=False)
        batch_op.create_index("ix_activities_maintenance_status", ["maintenance_status"], unique=False)
        batch_op.create_index("ix_activities_approval_status", ["approval_status"], unique=False)
        batch_op.create_index("ix_activities_approved_by_id", ["approved_by_id"], unique=False)
        batch_op.create_index("ix_activities_station_status", ["station_id", "approval_status"], unique=False)
        batch_op.create_index("ix_activities_type_status", ["activity_type", "approval_status"], unique=False)
        batch_op.create_index("ix_activities_engineer_status", ["logged_by_id", "approval_status"], unique=False)


def downgrade():
    op.drop_table("activities")

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("aircraft_id", sa.Integer(), sa.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True),
        sa.Column("logged_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "completed", "cancelled", name="activity_status"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_activities_aircraft_id"), ["aircraft_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_activities_logged_by_id"), ["logged_by_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_activities_shift_id"), ["shift_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_activities_station_id"), ["station_id"], unique=False)
        batch_op.create_index("ix_activities_station_status", ["station_id", "status"], unique=False)
        batch_op.create_index(batch_op.f("ix_activities_status"), ["status"], unique=False)
