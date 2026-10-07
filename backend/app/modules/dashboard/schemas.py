"""Dashboard summary schemas. Every number derives from records the user may see."""

from datetime import datetime

from pydantic import BaseModel


class ActivityItem(BaseModel):
    id: int
    action: str
    actor_username: str | None
    investigation_id: int
    investigation_title: str
    evidence_number: str | None = None
    created_at: datetime


class LastAnalysis(BaseModel):
    run_id: int
    run_label: str
    investigation_id: int
    investigation_title: str
    status: str
    completed_at: datetime | None
    artifact_count: int
    correlation_count: int


class DashboardSummary(BaseModel):
    investigations_total: int
    by_status: dict[str, int]
    evidence_total: int
    integrity_issues: int
    open_investigations: list[int]
    recent_activity: list[ActivityItem]
    pending_analysis: int = 0
    findings_pending_review: int = 0
    last_analysis: LastAnalysis | None = None
