"""Health endpoint.

Always returns HTTP 200 so load balancers / smoke tests can rely on it.
Database state is reported in the body, never as an error status, so the
endpoint stays non-fragile when Postgres is down or unconfigured.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_database

router = APIRouter()


@router.get("/health")
def health() -> dict:
    db = check_database()
    db_status = "ok" if db["reachable"] else ("not_configured" if not db["configured"] else "unreachable")
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "db": db_status,
    }
