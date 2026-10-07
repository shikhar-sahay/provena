"""Audit writer. Events are recorded by application actions, never by users directly."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent


class Actions:
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_CREATED = "USER_CREATED"
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_JOINED = "WORKSPACE_JOINED"
    WORKSPACE_INVITE_CREATED = "WORKSPACE_INVITE_CREATED"
    WORKSPACE_ROLE_CHANGED = "WORKSPACE_ROLE_CHANGED"
    INVESTIGATION_CREATED = "INVESTIGATION_CREATED"
    INVESTIGATION_UPDATED = "INVESTIGATION_UPDATED"
    INVESTIGATION_STATUS_CHANGED = "INVESTIGATION_STATUS_CHANGED"
    INVESTIGATION_MEMBER_ADDED = "INVESTIGATION_MEMBER_ADDED"
    INVESTIGATION_MEMBER_REMOVED = "INVESTIGATION_MEMBER_REMOVED"
    EVIDENCE_REGISTERED = "EVIDENCE_REGISTERED"
    EVIDENCE_METADATA_UPDATED = "EVIDENCE_METADATA_UPDATED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    EVIDENCE_INTEGRITY_MISMATCH = "EVIDENCE_INTEGRITY_MISMATCH"
    EVIDENCE_DOWNLOADED = "EVIDENCE_DOWNLOADED"
    CUSTODY_TRANSFERRED = "CUSTODY_TRANSFERRED"
    EVIDENCE_CUSTODY_UPDATED = "EVIDENCE_CUSTODY_UPDATED"
    AI_ANALYSIS_STARTED = "AI_ANALYSIS_STARTED"
    AI_ANALYSIS_COMPLETED = "AI_ANALYSIS_COMPLETED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    AI_FINDING_GENERATED = "AI_FINDING_GENERATED"
    AI_FINDING_ACCEPTED = "AI_FINDING_ACCEPTED"
    AI_FINDING_REJECTED = "AI_FINDING_REJECTED"
    INVESTIGATION_NOTE_ADDED = "INVESTIGATION_NOTE_ADDED"
    INVESTIGATION_NOTE_UPDATED = "INVESTIGATION_NOTE_UPDATED"
    REPORT_GENERATED = "REPORT_GENERATED"


class ResourceTypes:
    USER = "user"
    INVESTIGATION = "investigation"
    SESSION = "session"
    WORKSPACE = "workspace"


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    actor_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        actor_id=actor_id,
        event_metadata=metadata,
    )
    db.add(event)
    db.flush()
    return event


def list_for_investigation(db: Session, investigation_id: int) -> list[AuditEvent]:
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.resource_type == ResourceTypes.INVESTIGATION,
            AuditEvent.resource_id == str(investigation_id),
        )
        .order_by(AuditEvent.id)
    )
    return list(db.execute(stmt).scalars().all())
