"""Top-level API router. Domain routers mount here."""

from fastapi import APIRouter

from app.api.endpoints import health
from app.modules.auth.router import router as auth_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.evidence.router import router as evidence_router
from app.modules.evidence.router import timeline_router
from app.modules.intelligence.router import router as intelligence_router
from app.modules.investigations.router import router as investigations_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api")
router.include_router(health.router, tags=["health"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(investigations_router)
router.include_router(users_router)
router.include_router(evidence_router)
router.include_router(intelligence_router)
router.include_router(timeline_router)
