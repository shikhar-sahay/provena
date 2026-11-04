"""Immutable correlation support and run artifact membership.
Revision ID: d94e30a6b125
Revises: c83d2f95a014
"""
from alembic import op
import sqlalchemy as sa
revision = 'd94e30a6b125'
down_revision = 'c83d2f95a014'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('analysis_run_artifacts',
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('analysis_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('artifact_id', sa.Integer(), sa.ForeignKey('artifacts.id', ondelete='RESTRICT'), primary_key=True))
    op.add_column('correlations', sa.Column('semantic_key', sa.String(64), nullable=True))
    op.add_column('correlations', sa.Column('is_current', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.drop_constraint('uq_correlation_value', 'correlations', type_='unique')
    op.create_unique_constraint('uq_correlation_semantic', 'correlations', ['investigation_id', 'semantic_key'])
    op.add_column('findings', sa.Column('support_snapshot', sa.JSON(), nullable=True))
    # No historic memberships/identities/approvals are inferred or rewritten.


def downgrade():
    raise RuntimeError('Forward-only analytical provenance migration.')
