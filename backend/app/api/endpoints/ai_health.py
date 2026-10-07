"""Authenticated local narrative provider status."""

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import get_current_user
from app.modules.intelligence.narrative import provider_health
from app.modules.users.models import User

router = APIRouter()


@router.get("/ai/provider-health")
def ai_provider_health(_: User = Depends(get_current_user)):
    return provider_health()
