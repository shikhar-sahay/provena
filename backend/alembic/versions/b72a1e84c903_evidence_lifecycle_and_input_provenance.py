"""Evidence registration lifecycle and exact input provenance.

Revision ID: b72a1e84c903
Revises: 9b6e5c4d3a21
"""
from alembic import op
import sqlalchemy as sa

revision = "b72a1e84c903"
down_revision = "9b6e5c4d3a21"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("evidence", sa.Column("registration_status", sa.String(16), server_default="ready", nullable=False))
    op.add_column("evidence", sa.Column("registration_key", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_evidence_registration_key", "evidence", ["investigation_id", "registration_key"])
    op.add_column("evidence_verifications", sa.Column("purpose", sa.String(32), server_default="manual", nullable=False))
    op.add_column("analysis_run_evidence", sa.Column("input_sha256", sa.String(64), nullable=True))
    op.add_column("analysis_run_evidence", sa.Column("verification_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_run_evidence_verification", "analysis_run_evidence", "evidence_verifications", ["verification_id"], ["id"], ondelete="RESTRICT")
    op.add_column("artifacts", sa.Column("input_sha256", sa.String(64), nullable=True))
    # Historical results are intentionally not backfilled as freshly verified.


def downgrade():
    raise RuntimeError("This evidence-provenance migration is forward-only. Restore a reviewed backup instead.")
