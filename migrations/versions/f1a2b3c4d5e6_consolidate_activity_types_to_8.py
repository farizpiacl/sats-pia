"""Consolidate activity_type to the 8 canonical Activity Types

Remaps all existing `activities` and `inspection_entries` rows from the
old 18-value ActivityType enum onto the new 8 canonical values:

    maintenance_check, mic_scheduled_maintenance, qari, tsr,
    pirep_unscheduled_maintenance, replacement, cf_removal, cf

Mapping applied to existing data:
    aircraft_inspection, technical_inspection, transit_inspection,
    flight_inspection, maintenance, daily_check, weekly_check, other
        -> maintenance_check
    fixing_rectification, unscheduled_maintenance, defect
        -> pirep_unscheduled_maintenance
    wheel_change            -> replacement
    mic, scheduled_maintenance -> mic_scheduled_maintenance
    quality_inspection_ri   -> qari
    carry_forward_maintenance -> cf
    replacement, tsr        -> unchanged (values match)

`cf_removal` has no legacy source data - it's a new value going forward.

Revision ID: f1a2b3c4d5e6
Revises: e4a7c1f9b2d3
Create Date: 2026-08-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e4a7c1f9b2d3"
branch_labels = None
depends_on = None

OLD_VALUES = (
    "aircraft_inspection", "technical_inspection", "transit_inspection", "flight_inspection",
    "maintenance", "replacement", "fixing_rectification", "wheel_change", "tsr", "mic",
    "quality_inspection_ri", "scheduled_maintenance", "unscheduled_maintenance",
    "carry_forward_maintenance", "daily_check", "weekly_check", "defect", "other",
)

NEW_VALUES = (
    "maintenance_check", "mic_scheduled_maintenance", "qari", "tsr",
    "pirep_unscheduled_maintenance", "replacement", "cf_removal", "cf",
)

OLD_TO_NEW = {
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
    # unchanged values
    "replacement": "replacement",
    "tsr": "tsr",
}


def _remap_rows(connection, table):
    for old, new in OLD_TO_NEW.items():
        if old == new:
            continue
        connection.execute(
            sa.text(f"UPDATE {table} SET activity_type = :new WHERE activity_type = :old"),
            {"new": new, "old": old},
        )


def upgrade():
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        # 1. Add the new enum values alongside the old ones (Postgres can
        #    only add, not remove/rename, in place).
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE activity_type ADD VALUE IF NOT EXISTS '{value}'")

        # Alembic runs each migration in its own transaction; newly added
        # enum values can't be used in the same transaction they were
        # added in on PostgreSQL, so commit before remapping rows.
        connection.execute(sa.text("COMMIT"))
        connection.execute(sa.text("BEGIN"))

        # 2. Remap existing rows in both tables that use `activity_type`.
        _remap_rows(connection, "activities")
        _remap_rows(connection, "inspection_entries")

        # 3. Rebuild the enum type containing ONLY the 8 canonical values.
        op.execute("ALTER TYPE activity_type RENAME TO activity_type_old")
        new_enum = sa.Enum(*NEW_VALUES, name="activity_type")
        new_enum.create(connection)
        op.execute(
            "ALTER TABLE activities ALTER COLUMN activity_type TYPE activity_type "
            "USING activity_type::text::activity_type"
        )
        op.execute(
            "ALTER TABLE inspection_entries ALTER COLUMN activity_type TYPE activity_type "
            "USING activity_type::text::activity_type"
        )
        op.execute("DROP TYPE activity_type_old")
    else:
        # SQLite: VARCHAR + CHECK constraint. Remap data, then swap the
        # CHECK constraint via batch mode.
        _remap_rows(connection, "activities")
        _remap_rows(connection, "inspection_entries")

        with op.batch_alter_table("activities") as batch_op:
            batch_op.alter_column(
                "activity_type",
                existing_type=sa.Enum(*OLD_VALUES, name="activity_type"),
                type_=sa.Enum(*NEW_VALUES, name="activity_type"),
                existing_nullable=False,
            )
        with op.batch_alter_table("inspection_entries") as batch_op:
            batch_op.alter_column(
                "activity_type",
                existing_type=sa.Enum(*OLD_VALUES, name="activity_type"),
                type_=sa.Enum(*NEW_VALUES, name="activity_type"),
                existing_nullable=False,
            )


def downgrade():
    # Data loss is unavoidable on downgrade (many old values collapsed
    # onto the same new value), so this restores the old enum shape only;
    # rows keep whichever of the 8 new values they currently hold, which
    # remain valid strings under the restored (superset) old enum only if
    # we widen it. We take the safe route: recreate the old enum type
    # with BOTH old and new values so no data is stranded.
    connection = op.get_bind()
    combined = tuple(dict.fromkeys(OLD_VALUES + NEW_VALUES))

    if connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE activity_type RENAME TO activity_type_new")
        combined_enum = sa.Enum(*combined, name="activity_type")
        combined_enum.create(connection)
        op.execute(
            "ALTER TABLE activities ALTER COLUMN activity_type TYPE activity_type "
            "USING activity_type::text::activity_type"
        )
        op.execute(
            "ALTER TABLE inspection_entries ALTER COLUMN activity_type TYPE activity_type "
            "USING activity_type::text::activity_type"
        )
        op.execute("DROP TYPE activity_type_new")
    else:
        with op.batch_alter_table("activities") as batch_op:
            batch_op.alter_column(
                "activity_type",
                existing_type=sa.Enum(*NEW_VALUES, name="activity_type"),
                type_=sa.Enum(*combined, name="activity_type"),
                existing_nullable=False,
            )
        with op.batch_alter_table("inspection_entries") as batch_op:
            batch_op.alter_column(
                "activity_type",
                existing_type=sa.Enum(*NEW_VALUES, name="activity_type"),
                type_=sa.Enum(*combined, name="activity_type"),
                existing_nullable=False,
            )
