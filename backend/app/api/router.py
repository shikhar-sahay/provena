"""Top-level API router. Future domain routers mount here."""

from fastapi import APIRouter

from app.api.endpoints import health

router = APIRouter(prefix="/api")
router.include_router(health.router, tags=["health"])
