"""Development seed: create one login per Provena role. Idempotent.

Usage (from backend/):
    python -m app.seed

Passwords come from SEED_DEV_PASSWORD (default: provena-dev). These are
LOCAL DEVELOPMENT credentials only: clearly insecure, easy to override,
never for production. The script refuses to run when APP_ENV=production.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.modules.users.models import Role, User
from app.modules.workspaces.models import Workspace, WorkspaceMembership

DEV_USERS = [
    ("admin", "Admin User", Role.ADMIN),
    ("investigator", "Case Investigator", Role.INVESTIGATOR),
    ("analyst", "Forensic Analyst", Role.FORENSIC_ANALYST),
    ("custodian", "Evidence Custodian", Role.EVIDENCE_CUSTODIAN),
]


def main() -> None:
    if settings.app_env == "production":
        raise SystemExit("Refusing to seed in production.")
    if SessionLocal is None or engine is None:
        raise SystemExit("DATABASE_URL is not configured.")
    password = os.environ.get("SEED_DEV_PASSWORD", "provena-dev")
    with SessionLocal() as db:
        for username, full_name, role in DEV_USERS:
            existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if existing is not None:
                print(f"exists: {username} ({existing.role})")
                continue
            db.add(
                User(
                    username=username,
                    email=f"{username}@provena.local",
                    full_name=full_name,
                    password_hash=hash_password(password),
                    role=role.value,
                    is_active=True,
                )
            )
            print(f"created: {username} ({role.value})")
        db.commit()
        users = list(db.execute(select(User).where(User.username.in_([u[0] for u in DEV_USERS]))).scalars())
        workspace = db.execute(select(Workspace).where(Workspace.slug == "provena-demo")).scalar_one_or_none()
        if workspace is None:
            admin = next(user for user in users if user.username == "admin")
            workspace = Workspace(
                name="Provena Demo Workspace", slug="provena-demo", created_by_id=admin.id
            )
            db.add(workspace)
            db.flush()
            print("created: Provena Demo Workspace")
        for user in users:
            membership = db.execute(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )).scalar_one_or_none()
            if membership is None:
                db.add(WorkspaceMembership(
                    workspace_id=workspace.id, user_id=user.id, role=user.role, is_active=True
                ))
            user.active_workspace_id = workspace.id
        db.commit()
    print("Seed complete. Development logins: admin, investigator, analyst, custodian.")


if __name__ == "__main__":
    main()
