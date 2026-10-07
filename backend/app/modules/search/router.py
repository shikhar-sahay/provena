"""Search API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.search import service
from app.modules.search.schemas import SearchResponse
from app.modules.users.models import User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(default="", min_length=0, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.search_all(db, user, q)
