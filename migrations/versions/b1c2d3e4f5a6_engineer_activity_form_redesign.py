"""Engineer Activity Form redesign - new UX fields (additive, non-breaking)

Adds nullable columns to `activities` for: airline_id, manual aircraft
registration/model (Other-airline path), coverage_type (Ground/Flight),
maintenance_check_type (Daily/Weekly/Transit), and CRS association
(crs_engineer_id, second_engineer_id, is_crs).

Adds a new `qari_entries` table (up to 2 rows per QARI activity, enforced
in the application layer) so a single QARI activity can carry more than
one QARI line item.

No existing column, enum value, or table is altered or dropped - all
existing activities/inspection_forms/reports keep working unchanged, and
every new column is nullable so old rows are valid with the new schema
as-is.

Revision ID: b1c2d3e4f5a6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    coverage_type = sa.Enum("ground", "flight", name="coverage_type")
    maintenance_check_type = sa.Enum("daily", "weekly", "transit", name="maintenance_check_type")
    qari_severity = sa.Enum("significant", "minor", name="qari_severity")
    qari_entry_status = sa.Enum("open", "closed", name="qari_entry_status")

    bind = op.get_bind()
    coverage_type.create(bind, checkfirst=True)
    maintenance_check_type.create(bind, checkfirst=True)
    qari_severity.create(bind, checkfirst=True)
    qari_entry_status.create(bind, checkfirst=True)

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("airline_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("aircraft_registration_manual", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("aircraft_model_manual", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("coverage_type", coverage_type, nullable=True))
        batch_op.add_column(sa.Column("maintenance_check_type", maintenance_check_type, nullable=True))
        batch_op.add_column(sa.Column("crs_engineer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("second_engineer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_crs", sa.Boolean(), nullable=True))

        batch_op.create_index("ix_activities_airline_id", ["airline_id"], unique=False)
        batch_op.create_index("ix_activities_crs_engineer_id", ["crs_engineer_id"], unique=False)
        batch_op.create_index("ix_activities_second_engineer_id", ["second_engineer_id"], unique=False)

        batch_op.create_foreign_key(
            "fk_activities_airline_id", "airlines", ["airline_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_activities_crs_engineer_id", "users", ["crs_engineer_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_activities_second_engineer_id", "users", ["second_engineer_id"], ["id"], ondelete="SET NULL"
        )

    op.create_table(
        "qari_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("severity", qari_severity, nullable=False),
        sa.Column("qari_number", sa.String(length=50), nullable=True),
        sa.Column("sari_closed_count", sa.Integer(), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("status", qari_entry_status, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qari_entries_activity_id", "qari_entries", ["activity_id"], unique=False)


def downgrade():
    op.drop_index("ix_qari_entries_activity_id", table_name="qari_entries")
    op.drop_table("qari_entries")

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_constraint("fk_activities_second_engineer_id", type_="foreignkey")
        batch_op.drop_constraint("fk_activities_crs_engineer_id", type_="foreignkey")
        batch_op.drop_constraint("fk_activities_airline_id", type_="foreignkey")
        batch_op.drop_index("ix_activities_second_engineer_id")
        batch_op.drop_index("ix_activities_crs_engineer_id")
        batch_op.drop_index("ix_activities_airline_id")
        batch_op.drop_column("is_crs")
        batch_op.drop_column("second_engineer_id")
        batch_op.drop_column("crs_engineer_id")
        batch_op.drop_column("maintenance_check_type")
        batch_op.drop_column("coverage_type")
        batch_op.drop_column("aircraft_model_manual")
        batch_op.drop_column("aircraft_registration_manual")
        batch_op.drop_column("airline_id")

    bind = op.get_bind()
    sa.Enum(name="qari_entry_status").drop(bind, checkfirst=True)
    sa.Enum(name="qari_severity").drop(bind, checkfirst=True)
    sa.Enum(name="maintenance_check_type").drop(bind, checkfirst=True)
    sa.Enum(name="coverage_type").drop(bind, checkfirst=True)
