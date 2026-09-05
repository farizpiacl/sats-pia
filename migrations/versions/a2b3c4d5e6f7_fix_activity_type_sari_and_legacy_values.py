"""Fix activity_type: remove non-canonical 'sari', remap legacy values

'sari' was added by d4e5f6a7b8c9 but was never wired up in any form, JS,
or route - it is not a real, used activity type (the ActivityType model
enum has been reverted to drop it; QARI is the only Quality/RI type).
Some environments also still carry legacy pre-consolidation values (e.g.
'aircraft_inspection') on `activities`/`inspection_entries` rows that
were never remapped by f1a2b3c4d5e6, causing invalid-enum-value errors
when the app reads those rows.

This migration is idempotent / safe to run against a DB in either state:
    1. Remap any 'sari' rows -> 'qari'.
    2. Remap any remaining legacy rows (aircraft_inspection and the rest
       of the pre-consolidation value set) -> their canonical equivalent,
       using the same mapping as f1a2b3c4d5e6.
    3. Rebuild the activity_type enum type to contain ONLY the 8
       canonical values (no 'sari'), matching app/models/activity.py.

No rows are deleted - every legacy/invalid value is remapped to the
closest existing valid ActivityType.

Revision ID: a2b3c4d5e6f7
Revises: f4b1a2c3d5e6
Create Date: 2026-08-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "f4b1a2c3d5e6"
branch_labels = None
depends_on = None

CANONICAL_VALUES = (
    "maintenance_check", "mic_scheduled_maintenance", "qari", "tsr",
    "pirep_unscheduled_maintenance", "replacement", "cf_removal", "cf",
)

# Anything that isn't already a canonical value gets remapped here.
# Includes 'sari' (never used, dead enum value) and every legacy
# pre-consolidation value that might still be lingering on old rows.
LEGACY_TO_CANONICAL = {
    "sari": "qari",
    "aircraft_inspection": "maintenance_check",
    "technical_inspection": "maintenance_check",
    "transit_inspection": "maintenance_check",
    "flight_inspection": "maintenance_check",
    "maintenance": "maintenance_check",
    "daily_check": "maintenance_check",
    "weekly_check": "maintenance_check",
    "other": "maintenance_check",
    "fixing_rectification": "pirep_unscheduled_maintenance",
    "unscheduled_maintenance": "pirep_unscheduled_maintenance",
    "defect": "pirep_unscheduled_maintenance",
    "wheel_change": "replacement",
    "mic": "mic_scheduled_maintenance",
    "scheduled_maintenance": "mic_scheduled_maintenance",
    "quality_inspection_ri": "qari",
    "carry_forward_maintenance": "cf",
}


def _remap_rows(connection, table):
    for old, new in LEGACY_TO_CANONICAL.items():
        connection.execute(
            sa.text(f"UPDATE {table} SET activity_type = :new WHERE activity_type = :old"),
            {"new": new, "old": old},
        )


def _table_exists(connection, table):
    return connection.dialect.has_table(connection, table)


def upgrade():
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        # 1. Make sure every canonical value exists on the enum type
        #    before we try to UPDATE rows onto it (Postgres requires
        #    the target value to already exist in the type).
        for value in CANONICAL_VALUES:
            op.execute(f"ALTER TYPE activity_type ADD VALUE IF NOT EXISTS '{value}'")
        connection.execute(sa.text("COMMIT"))
        connection.execute(sa.text("BEGIN"))

        # 2. Remap 'sari' and any lingering legacy values to their
        #    canonical equivalent, on every table that has the column.
        for table in ("activities", "inspection_entries"):
            if _table_exists(connection, table):
                _remap_rows(connection, table)

        # 3. Rebuild the enum type containing ONLY the 8 canonical
        #    values, matching app/models/activity.py.
        op.execute("ALTER TYPE activity_type RENAME TO activity_type_old")
        new_enum = sa.Enum(*CANONICAL_VALUES, name="activity_type")
        new_enum.create(connection)
        for table in ("activities", "inspection_entries"):
            if _table_exists(connection, table):
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN activity_type TYPE activity_type "
                    "USING activity_type::text::activity_type"
                )
        op.execute("DROP TYPE activity_type_old")
    else:
        # SQLite: VARCHAR + CHECK constraint.
        for table in ("activities", "inspection_entries"):
            if _table_exists(connection, table):
                _remap_rows(connection, table)

        for table in ("activities", "inspection_entries"):
            if _table_exists(connection, table):
                with op.batch_alter_table(table) as batch_op:
                    batch_op.alter_column(
                        "activity_type",
                        existing_type=sa.String(),
                        type_=sa.Enum(*CANONICAL_VALUES, name="activity_type"),
                        existing_nullable=False,
                    )


def downgrade():
    # 'sari' and the legacy values are gone for good - restoring the
    # wider enum shape doesn't restore the original (already-remapped)
    # data, so this only widens the type back so no future value is
    # stranded; it does not attempt to un-remap rows.
    connection = op.get_bind()
    combined = tuple(dict.fromkeys(CANONICAL_VALUES + ("sari",) + tuple(LEGACY_TO_CANONICAL.keys())))

    if connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE activity_type RENAME TO activity_type_new")
        combined_enum = sa.Enum(*combined, name="activity_type")
        combined_enum.create(connection)
        for table in ("activities", "inspection_entries"):
            if _table_exists(connection, table):
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN activity_type TYPE activity_type "
                    "USING activity_type::text::activity_type"
                )
        op.execute("DROP TYPE activity_type_new")
