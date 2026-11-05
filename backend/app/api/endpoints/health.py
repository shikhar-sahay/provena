"""Health endpoint.

Always returns HTTP 200 so load balancers / smoke tests can rely on it.
Database state is reported in the body, never as an error status, so the
endpoint stays non-fragile when Postgres is down or unconfigured.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.db.session import check_database
from app.ops.preflight import diagnostics
from app.version import VERSION

router = APIRouter()


@router.get('/live')
def liveness():
    """No dependency probes, tokens or paths in the public liveness response."""
    return {'status':'alive','app':settings.app_name,'version':VERSION}


def readiness_checks():
    return diagnostics(settings,database=True,storage=True)


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


@router.get("/ready")
def readiness() -> dict:
    """Dependency readiness with no private diagnostic details in public responses."""
    result=readiness_checks()
    if not result['ready']:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required application dependencies are not ready.",
        )
    return {"status": "ready", "db": "ok"}
