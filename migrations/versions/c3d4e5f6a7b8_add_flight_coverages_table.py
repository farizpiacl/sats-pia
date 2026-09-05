"""Add flight_coverages table for Flight Coverage tracking

Revision ID: c3d4e5f6a7b8
Revises: a9c4e1f7b3d2
Create Date: 2026-08-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a9c4e1f7b3d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('flight_coverages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.Integer(), nullable=False),
    sa.Column('activity_performed', sa.Text(), nullable=False),
    sa.Column('logged_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['logged_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('flight_coverages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_flight_coverages_station_id'), ['station_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_flight_coverages_logged_by_id'), ['logged_by_id'], unique=False)
        batch_op.create_index('ix_flight_coverages_station', ['station_id'], unique=False)
        batch_op.create_index('ix_flight_coverages_engineer', ['logged_by_id'], unique=False)


def downgrade():
    with op.batch_alter_table('flight_coverages', schema=None) as batch_op:
        batch_op.drop_index('ix_flight_coverages_engineer')
        batch_op.drop_index('ix_flight_coverages_station')
        batch_op.drop_index(batch_op.f('ix_flight_coverages_logged_by_id'))
        batch_op.drop_index(batch_op.f('ix_flight_coverages_station_id'))

    op.drop_table('flight_coverages')
