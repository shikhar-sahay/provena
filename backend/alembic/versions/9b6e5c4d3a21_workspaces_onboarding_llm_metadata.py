"""workspaces onboarding and report narrative metadata

Revision ID: 9b6e5c4d3a21
Revises: 000a8976b7f1
Create Date: 2026-10-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9b6e5c4d3a21"
down_revision: str | None = "000a8976b7f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])
    op.create_index("ix_workspace_memberships_role", "workspace_memberships", ["role"])
    op.create_table(
        "workspace_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hint", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("ix_workspace_invites_workspace_id", "workspace_invites", ["workspace_id"])
    op.create_index("ix_workspace_invites_code_hash", "workspace_invites", ["code_hash"])

    op.add_column("users", sa.Column("active_workspace_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_workspace", "users", "workspaces", ["active_workspace_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_active_workspace_id", "users", ["active_workspace_id"])
    op.add_column("investigations", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_investigations_workspace", "investigations", "workspaces", ["workspace_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_investigations_workspace_id", "investigations", ["workspace_id"])

    # Preserve all existing development data in one seeded workspace. Fresh
    # databases have no users at migration time, so the regular seed creates it.
    op.execute(sa.text(
        "INSERT INTO workspaces (name, slug, created_by_id) "
        "SELECT 'Provena Demo Workspace', 'provena-demo', id FROM users ORDER BY id LIMIT 1"
    ))
    op.execute(sa.text(
        "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
        "SELECT w.id, u.id, u.role FROM users u CROSS JOIN workspaces w WHERE w.slug = 'provena-demo'"
    ))
    op.execute(sa.text(
        "UPDATE users SET active_workspace_id = (SELECT id FROM workspaces WHERE slug = 'provena-demo') "
        "WHERE EXISTS (SELECT 1 FROM workspaces WHERE slug = 'provena-demo')"
    ))
    op.execute(sa.text(
        "UPDATE investigations SET workspace_id = (SELECT id FROM workspaces WHERE slug = 'provena-demo') "
        "WHERE workspace_id IS NULL"
    ))
    op.alter_column("investigations", "workspace_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_investigations_workspace_id", table_name="investigations")
    op.drop_constraint("fk_investigations_workspace", "investigations", type_="foreignkey")
    op.drop_column("investigations", "workspace_id")
    op.drop_index("ix_users_active_workspace_id", table_name="users")
    op.drop_constraint("fk_users_active_workspace", "users", type_="foreignkey")
    op.drop_column("users", "active_workspace_id")
    op.drop_index("ix_workspace_invites_code_hash", table_name="workspace_invites")
    op.drop_index("ix_workspace_invites_workspace_id", table_name="workspace_invites")
    op.drop_table("workspace_invites")
    op.drop_index("ix_workspace_memberships_role", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
