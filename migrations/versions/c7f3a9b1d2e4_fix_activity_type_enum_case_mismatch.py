"""Fix activity_type enum case mismatch (drop duplicate uppercase values)

The SQLAlchemy `Activity.activity_type` column was missing
`values_callable`, so SQLAlchemy was sending Python Enum *member names*
(e.g. "AIRCRAFT_INSPECTION") to PostgreSQL instead of the intended
lowercase `.value` strings ("aircraft_inspection"). At some point the
uppercase names AIRCRAFT_INSPECTION, TECHNICAL_INSPECTION and
TRANSIT_INSPECTION were added directly to the `activity_type` enum type
in PostgreSQL as a stop-gap, leaving duplicate values side by side with
the correct lowercase ones.

This migration:
  1. Migrates any existing `activities` rows that use the uppercase
     duplicate values to their correct lowercase equivalents.
  2. Rebuilds the `activity_type` enum type containing ONLY the 15
     correct lowercase values (PostgreSQL has no `ALTER TYPE ... DROP
     VALUE`, so the type must be recreated).

The application-level fix (values_callable on the Column) means
SQLAlchemy now always sends the lowercase `.value` strings, matching
this schema.

Revision ID: c7f3a9b1d2e4
Revises: 8d8e7b181a16
Create Date: 2026-08-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c7f3a9b1d2e4"
down_revision = "8d8e7b181a16"
branch_labels = None
depends_on = None

# Only these three duplicate uppercase values are known to exist in the
# enum; everything else is already correct lowercase.
UPPERCASE_TO_LOWERCASE = {
    "AIRCRAFT_INSPECTION": "aircraft_inspection",
    "TECHNICAL_INSPECTION": "technical_inspection",
    "TRANSIT_INSPECTION": "transit_inspection",
}

CORRECT_VALUES = (
    "aircraft_inspection", "technical_inspection", "transit_inspection", "flight_inspection",
    "maintenance", "replacement", "fixing_rectification", "wheel_change", "tsr", "mic",
    "quality_inspection_ri", "scheduled_maintenance", "unscheduled_maintenance",
    "carry_forward_maintenance", "other",
)


def upgrade():
    connection = op.get_bind()

    if connection.dialect.name != "postgresql":
        # SQLite has no native enum type (it's VARCHAR + CHECK, and never
        # had the uppercase-duplicate bug in the first place since that
        # was a PostgreSQL-only artifact), so there's nothing to rebuild.
        return

    # Determine which labels the *current* `activity_type` enum actually
    # has. On a fresh install (or any DB that never had the production
    # hotfix applied), the uppercase duplicates never existed, so we must
    # not try to UPDATE against enum labels the type doesn't contain -
    # PostgreSQL raises InvalidTextRepresentation for that.
    existing_labels = {
        row[0]
        for row in connection.execute(
            sa.text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = :type_name"
            ),
            {"type_name": "activity_type"},
        ).fetchall()
    }

    # 1. Migrate any rows still using an uppercase duplicate value to the
    #    matching lowercase value before the type is rebuilt - but only
    #    for uppercase values that actually exist in the enum today.
    for upper, lower in UPPERCASE_TO_LOWERCASE.items():
        if upper not in existing_labels:
            continue
        connection.execute(
            sa.text(
                "UPDATE activities SET activity_type = :lower "
                "WHERE activity_type = :upper"
            ),
            {"lower": lower, "upper": upper},
        )

    # 2. Rebuild the enum type with only the correct lowercase values.
    #    PostgreSQL doesn't support removing a value from an enum type
    #    directly, so create a new type, repoint the column at it (with
    #    an explicit USING cast), then drop the old type and rename.
    #    Skip the rebuild entirely if the type already matches the target
    #    (fresh installs created it correctly in the first place).
    if existing_labels and existing_labels == set(CORRECT_VALUES):
        return

    op.execute("ALTER TYPE activity_type RENAME TO activity_type_old")

    new_enum = sa.Enum(*CORRECT_VALUES, name="activity_type")
    new_enum.create(connection)

    op.execute(
        "ALTER TABLE activities "
        "ALTER COLUMN activity_type TYPE activity_type "
        "USING activity_type::text::activity_type"
    )

    op.execute("DROP TYPE activity_type_old")


def downgrade():
    connection = op.get_bind()

    if connection.dialect.name != "postgresql":
        return

    # Recreate the old enum type (lowercase values + the three uppercase
    # duplicates) and repoint the column back at it. Data is left using
    # the lowercase values - the duplicates existed only as an artifact
    # of the earlier bug and are not restored to any row.
    op.execute("ALTER TYPE activity_type RENAME TO activity_type_new")

    old_enum = sa.Enum(*CORRECT_VALUES, *UPPERCASE_TO_LOWERCASE.keys(), name="activity_type")
    old_enum.create(connection)

    op.execute(
        "ALTER TABLE activities "
        "ALTER COLUMN activity_type TYPE activity_type "
        "USING activity_type::text::activity_type"
    )

    op.execute("DROP TYPE activity_type_new")
