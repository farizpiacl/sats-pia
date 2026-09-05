"""Module 5 - Engineer Inspection Form

Adds the dedicated Engineer Inspection Form feature:

* Renames the "beta" shift to "bravo" (Alpha / Bravo / Charlie / Delta),
  updating any existing rows so no data is lost.
* Creates inspection_forms, inspection_entries and inspection_credits.
* Seeds the Lahore station (if missing) and the four airlines required by
  the inspection form (PIA, Saudi Airlines, Qatar Airways, Singapore
  Airlines) so the feature works out of the box - purely additive,
  skipped if the rows already exist.

Existing activities/approval/audit data is untouched.

Revision ID: d3f4a5b6c7e8
Revises: 6b595f6ff038
Create Date: 2026-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

# revision identifiers, used by Alembic.
revision = "d3f4a5b6c7e8"
down_revision = "6b595f6ff038"
branch_labels = None
depends_on = None


# NOTE: the `shifts.name` column is `db.Enum(ShiftName)` on the model side
# WITHOUT `values_callable`, so SQLAlchemy persists the Python Enum
# *member names* (ALPHA/BETA/CHARLIE/DELTA), not their lowercase
# `.value` strings - matching how the initial migration created the
# `shift_name` type ('ALPHA', 'BETA', 'CHARLIE', 'DELTA'). The rename
# below must therefore operate on the uppercase labels that are actually
# stored in the database.
OLD_SHIFT_VALUES = ("ALPHA", "BETA", "CHARLIE", "DELTA")
NEW_SHIFT_VALUES = ("ALPHA", "BRAVO", "CHARLIE", "DELTA")

ACTIVITY_TYPE_VALUES = (
    "aircraft_inspection", "technical_inspection", "transit_inspection", "flight_inspection",
    "maintenance", "replacement", "fixing_rectification", "wheel_change", "tsr", "mic",
    "quality_inspection_ri", "scheduled_maintenance", "unscheduled_maintenance",
    "carry_forward_maintenance", "daily_check", "weekly_check", "defect", "other",
)
APPROVAL_STATUS_VALUES = ("pending_approval", "approved", "rejected")


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # --- 1. Rename shift "BETA" -> "BRAVO" -------------------------------
    if is_pg:
        existing_labels = {
            row[0]
            for row in bind.execute(
                sa.text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = :type_name"
                ),
                {"type_name": "shift_name"},
            ).fetchall()
        }
        if "BETA" in existing_labels and "BRAVO" not in existing_labels:
            op.execute("ALTER TYPE shift_name RENAME VALUE 'BETA' TO 'BRAVO'")
    else:
        # SQLite has no native enum - the column is VARCHAR + CHECK. Widen
        # the CHECK to a superset first so existing 'BETA' rows stay valid
        # while we rewrite them, then narrow it down to the final values.
        TRANSITION_VALUES = ("ALPHA", "BETA", "BRAVO", "CHARLIE", "DELTA")
        with op.batch_alter_table("shifts") as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.Enum(*OLD_SHIFT_VALUES, name="shift_name"),
                type_=sa.Enum(*TRANSITION_VALUES, name="shift_name_transition"),
                existing_nullable=False,
            )
        op.execute("UPDATE shifts SET name = 'BRAVO' WHERE name = 'BETA'")
        with op.batch_alter_table("shifts") as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.Enum(*TRANSITION_VALUES, name="shift_name_transition"),
                type_=sa.Enum(*NEW_SHIFT_VALUES, name="shift_name"),
                existing_nullable=False,
            )

    # --- 2. inspection_forms ----------------------------------------------
    op.create_table(
        "inspection_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inspection_date", sa.Date(), nullable=False),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("airline_id", sa.Integer(), sa.ForeignKey("airlines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("aircraft_id", sa.Integer(), sa.ForeignKey("aircraft.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("primary_engineer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("second_engineer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overall_remarks", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.Enum(*APPROVAL_STATUS_VALUES, name="inspection_approval_status"), nullable=False, server_default="pending_approval"),
        sa.Column("approval_remarks", sa.String(500), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inspection_forms_inspection_date", "inspection_forms", ["inspection_date"])
    op.create_index("ix_inspection_forms_station_id", "inspection_forms", ["station_id"])
    op.create_index("ix_inspection_forms_shift_id", "inspection_forms", ["shift_id"])
    op.create_index("ix_inspection_forms_airline_id", "inspection_forms", ["airline_id"])
    op.create_index("ix_inspection_forms_aircraft_id", "inspection_forms", ["aircraft_id"])
    op.create_index("ix_inspection_forms_primary_engineer_id", "inspection_forms", ["primary_engineer_id"])
    op.create_index("ix_inspection_forms_second_engineer_id", "inspection_forms", ["second_engineer_id"])
    op.create_index("ix_inspection_forms_approval_status", "inspection_forms", ["approval_status"])
    op.create_index("ix_inspection_forms_approved_by_id", "inspection_forms", ["approved_by_id"])
    op.create_index("ix_inspection_forms_station_status", "inspection_forms", ["station_id", "approval_status"])
    op.create_index("ix_inspection_forms_engineer_status", "inspection_forms", ["primary_engineer_id", "approval_status"])

    # --- 3. inspection_entries (the Yes/No + remarks checklist) -----------
    op.create_table(
        "inspection_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inspection_form_id", sa.Integer(), sa.ForeignKey("inspection_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "activity_type",
            # The `activity_type` enum type already exists in postgres by
            # this point (created in migration a1b2c3d4e5f6, or already
            # present in the database) - this column just reuses it via
            # the dialect-specific ENUM with create_type=False, so it must
            # not try to CREATE TYPE again. Plain sa.Enum(create_type=False)
            # is not reliable here - see a1b2c3d4e5f6 for why.
            PG_ENUM(*ACTIVITY_TYPE_VALUES, name="activity_type", create_type=False)
            if is_pg else sa.Enum(*ACTIVITY_TYPE_VALUES, name="activity_type"),
            nullable=False,
        ),
        sa.Column("performed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("inspection_form_id", "activity_type", name="uq_inspection_entry_type"),
    )
    op.create_index("ix_inspection_entries_form_id", "inspection_entries", ["inspection_form_id"])

    # --- 4. inspection_credits (rebuilt wholesale on every save) ----------
    op.create_table(
        "inspection_credits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inspection_form_id", sa.Integer(), sa.ForeignKey("inspection_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credit_type", sa.String(50), nullable=False),
        sa.Column("credit_value", sa.Numeric(4, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inspection_credits_form_id", "inspection_credits", ["inspection_form_id"])
    op.create_index("ix_inspection_credits_engineer_id", "inspection_credits", ["engineer_id"])
    op.create_index("ix_inspection_credits_credit_type", "inspection_credits", ["credit_type"])
    op.create_index("ix_inspection_credits_engineer_type", "inspection_credits", ["engineer_id", "credit_type"])

    # --- 5. Seed data required by the form (idempotent) --------------------
    connection = op.get_bind()
    stations = sa.table(
        "stations", sa.column("id", sa.Integer), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("city", sa.String), sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    airlines = sa.table(
        "airlines", sa.column("id", sa.Integer), sa.column("iata_code", sa.String), sa.column("icao_code", sa.String),
        sa.column("name", sa.String), sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )

    now = sa.func.now()

    existing_station = connection.execute(
        sa.text("SELECT id FROM stations WHERE code = 'LHE' OR name ILIKE '%Lahore%'")
        if is_pg else sa.text("SELECT id FROM stations WHERE code = 'LHE' OR name LIKE '%Lahore%'")
    ).first()
    if not existing_station:
        connection.execute(
            stations.insert().values(
                code="LHE", name="Lahore", city="Lahore", is_active=True, created_at=now, updated_at=now,
            )
        )

    for name, iata in (
        ("PIA", "PK"),
        ("Saudi Airlines", "SV"),
        ("Qatar Airways", "QR"),
        ("Singapore Airlines", "SQ"),
    ):
        existing_airline = connection.execute(
            sa.text("SELECT id FROM airlines WHERE name = :name"), {"name": name}
        ).first()
        if not existing_airline:
            connection.execute(
                airlines.insert().values(
                    iata_code=iata, icao_code=None, name=name, is_active=True, created_at=now, updated_at=now,
                )
            )


def downgrade():
    op.drop_index("ix_inspection_credits_engineer_type", table_name="inspection_credits")
    op.drop_index("ix_inspection_credits_credit_type", table_name="inspection_credits")
    op.drop_index("ix_inspection_credits_engineer_id", table_name="inspection_credits")
    op.drop_index("ix_inspection_credits_form_id", table_name="inspection_credits")
    op.drop_table("inspection_credits")

    op.drop_index("ix_inspection_entries_form_id", table_name="inspection_entries")
    op.drop_table("inspection_entries")

    op.drop_index("ix_inspection_forms_engineer_status", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_station_status", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_approved_by_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_approval_status", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_second_engineer_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_primary_engineer_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_aircraft_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_airline_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_shift_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_station_id", table_name="inspection_forms")
    op.drop_index("ix_inspection_forms_inspection_date", table_name="inspection_forms")
    op.drop_table("inspection_forms")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE shift_name RENAME VALUE 'bravo' TO 'beta'")
        op.execute("DROP TYPE IF EXISTS inspection_approval_status")
    else:
        TRANSITION_VALUES = ("alpha", "beta", "bravo", "charlie", "delta")
        with op.batch_alter_table("shifts") as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.Enum(*NEW_SHIFT_VALUES, name="shift_name"),
                type_=sa.Enum(*TRANSITION_VALUES, name="shift_name_transition"),
                existing_nullable=False,
            )
        op.execute("UPDATE shifts SET name = 'beta' WHERE name = 'bravo'")
        with op.batch_alter_table("shifts") as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.Enum(*TRANSITION_VALUES, name="shift_name_transition"),
                type_=sa.Enum(*OLD_SHIFT_VALUES, name="shift_name"),
                existing_nullable=False,
            )
