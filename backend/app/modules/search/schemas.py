"""Global search schemas for authorized multi-entity search."""

from pydantic import BaseModel, ConfigDict


class SearchResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str  # "investigation", "evidence", "finding", "artifact"
    id: int
    title: str
    subtitle: str | None = None
    url: str
    investigation_id: int
    investigation_title: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
