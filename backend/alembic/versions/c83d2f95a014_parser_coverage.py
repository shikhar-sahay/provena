"""Persist parser coverage without inventing historical coverage.

Revision ID: c83d2f95a014
Revises: b72a1e84c903
"""
from alembic import op
import sqlalchemy as sa

revision = "c83d2f95a014"
down_revision = "b72a1e84c903"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_run_evidence", sa.Column("coverage", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError("Forward-only analytical provenance migration.")
