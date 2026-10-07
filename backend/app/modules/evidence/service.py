"""Evidence service: registration, verification, custody, timelines, authorization.

Authorization (backend-enforced):
- Viewing evidence, verifying integrity, and downloading: any investigation
  member (admins bypass scoping).
- Registering evidence and editing metadata: investigation managers
  (admin, creator, lead investigator).
- Recording custody events: managers, plus evidence custodians who are
  members of the investigation.
- Mutations on archived investigations: admins only.
"""

from datetime import datetime, timezone
from typing import BinaryIO

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.audit.service import Actions, ResourceTypes, list_for_investigation, record
from app.modules.evidence import storage
from app.modules.evidence.models import (
    CustodyAction,
    CustodyEvent,
    Evidence,
    EvidenceType,
    EvidenceVerification,
    IntegrityStatus,
)
from app.modules.evidence.schemas import CustodyCreate, EvidenceUpdate, TimelineEntry
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import Investigation, InvestigationStatus
from app.modules.users.models import Role, User
from app.modules.workspaces import service as workspace_service
from app.modules.users.service import get_by_id


def ensure_mutable(inv: Investigation, user: User) -> None:
    if inv.status == InvestigationStatus.ARCHIVED.value and user.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Archived investigations are read-only.",
        )


def ensure_evidence_access(db: Session, inv: Investigation, evidence_id: int, user: User) -> Evidence:
    inv_service.ensure_access(db, inv, user)
    evidence = _get_evidence(db, inv.id, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return evidence


def ensure_evidence_manage(db: Session, inv: Investigation, evidence_id: int, user: User) -> Evidence:
    inv_service.ensure_manage(db, inv, user)
    ensure_mutable(inv, user)
    evidence = _get_evidence(db, inv.id, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return evidence


def ensure_custody_permission(
    db: Session, inv: Investigation, evidence_id: int, user: User
) -> Evidence:
    inv_service.ensure_access(db, inv, user)
    ensure_mutable(inv, user)
    evidence = _get_evidence(db, inv.id, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    if inv_service.can_manage(db, inv, user):
        return evidence
    if workspace_service.role_for(db, user, inv.workspace_id) == Role.EVIDENCE_CUSTODIAN.value and inv_service.is_member(db, inv.id, user.id):
        return evidence
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def ensure_custodian_permission(db: Session, inv: Investigation, user: User) -> None:
    """Allow case managers or an assigned evidence custodian."""
    if inv_service.can_manage(db, inv, user):
        return
    if (
        workspace_service.role_for(db, user, inv.workspace_id)
        == Role.EVIDENCE_CUSTODIAN.value
        and inv_service.is_member(db, inv.id, user.id)
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def _get_evidence(db: Session, investigation_id: int, evidence_id: int) -> Evidence | None:
    stmt = (
        select(Evidence)
        .where(Evidence.investigation_id == investigation_id, Evidence.id == evidence_id)
        .options(selectinload(Evidence.registered_by))
    )
    return db.execute(stmt).scalar_one_or_none()


def _generate_evidence_number(db: Session, investigation_id: int) -> str:
    stmt = select(Evidence.evidence_number).where(
        Evidence.investigation_id == investigation_id,
        Evidence.evidence_number.like("E-%"),
    )
    best = 0
    for (number,) in db.execute(stmt).all():
        try:
            best = max(best, int(number.split("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"E-{best + 1:03d}"


def current_holder(db: Session, evidence: Evidence) -> User | None:
    """Derive the current holder from the latest custody event (history is truth)."""
    stmt = (
        select(CustodyEvent)
        .where(CustodyEvent.evidence_id == evidence.id)
        .order_by(CustodyEvent.id.desc())
        .limit(1)
    )
    latest = db.execute(stmt).scalar_one_or_none()
    if latest is None:
        return None
    holder_id = latest.to_user_id or latest.performed_by_id
    return get_by_id(db, holder_id) if holder_id else None


def register_evidence(
    db: Session,
    inv: Investigation,
    *,
    title: str,
    description: str,
    evidence_type: EvidenceType,
    source: str,
    acquired_at,
    filename: str,
    content_type: str | None,
    stream: BinaryIO,
    actor: User,
) -> Evidence:
    title = title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Title is required."
        )
    safe_name = filename.split("/")[-1].split("\\")[-1].strip()[:255] or "unnamed"
    try:
        storage_key, staged, digest, size = storage.save_stream(
            stream, inv.id, settings.evidence_max_upload_bytes
        )
    except OverflowError:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File exceeds the maximum upload size.",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty.",
        )

    evidence = Evidence(
        investigation_id=inv.id,
        evidence_number="",
        title=title,
        description=description.strip(),
        evidence_type=evidence_type.value,
        original_filename=safe_name,
        content_type=(content_type or None),
        source=source.strip(),
        acquired_at=acquired_at,
        registered_by_id=actor.id,
        file_size=size,
        storage_key="",
        sha256=digest,
        integrity_status=IntegrityStatus.NOT_VERIFIED.value,
    )
    try:
        for _ in range(5):
            evidence.evidence_number = _generate_evidence_number(db, inv.id)
            evidence.storage_key = storage_key
            db.add(evidence)
            try:
                db.flush()
                break
            except IntegrityError:
                db.rollback()
        else:  # pragma: no cover - defensive; effectively unreachable at this scale
            raise HTTPException(status_code=500, detail="Could not register evidence.")
        db.add(
            CustodyEvent(
                evidence_id=evidence.id,
                action=CustodyAction.REGISTERED.value,
                to_user_id=actor.id,
                performed_by_id=actor.id,
                notes="Evidence registered.",
            )
        )
        record(
            db,
            action=Actions.EVIDENCE_REGISTERED,
            resource_type=ResourceTypes.INVESTIGATION,
            resource_id=inv.id,
            actor_id=actor.id,
            metadata={
                "evidence_id": evidence.id,
                "evidence_number": evidence.evidence_number,
                "title": evidence.title,
                "sha256": digest,
                "file_size": size,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.discard_staged(staged)
        raise
    storage.commit_staged(staged)
    db.refresh(evidence)
    return evidence


def update_evidence_metadata(
    db: Session, inv: Investigation, evidence: Evidence, payload: EvidenceUpdate, actor: User
) -> Evidence:
    changes: list[str] = []
    if payload.title is not None and payload.title.strip() != evidence.title:
        if not payload.title.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Title is required."
            )
        evidence.title = payload.title.strip()
        changes.append("title")
    if payload.description is not None and payload.description.strip() != evidence.description:
        evidence.description = payload.description.strip()
        changes.append("description")
    if payload.evidence_type is not None and payload.evidence_type.value != evidence.evidence_type:
        evidence.evidence_type = payload.evidence_type.value
        changes.append("evidence_type")
    if payload.source is not None and payload.source.strip() != evidence.source:
        evidence.source = payload.source.strip()
        changes.append("source")
    if payload.acquired_at is not None and payload.acquired_at != evidence.acquired_at:
        evidence.acquired_at = payload.acquired_at
        changes.append("acquired_at")
    # Bytes, baseline digest, uploader, and registration time are immutable
    # and are never touched here.
    if changes:
        record(
            db,
            action=Actions.EVIDENCE_METADATA_UPDATED,
            resource_type=ResourceTypes.INVESTIGATION,
            resource_id=inv.id,
            actor_id=actor.id,
            metadata={
                "evidence_id": evidence.id,
                "evidence_number": evidence.evidence_number,
                "changes": changes,
            },
        )
    db.commit()
    db.refresh(evidence)
    return evidence


def verify_evidence(db: Session, inv: Investigation, evidence: Evidence, actor: User):
    """Recompute SHA-256 and compare against the immutable baseline digest."""
    try:
        path = storage.resolve(evidence.storage_key)
        observed = storage.sha256_file(path) if path.exists() else None
    except (OSError, ValueError):
        observed = None
    if observed is None:
        result = IntegrityStatus.UNAVAILABLE
        reason = "Stored object could not be accessed."
    elif observed == evidence.sha256:
        result = IntegrityStatus.VERIFIED
        reason = None
    else:
        result = IntegrityStatus.MISMATCH
        reason = "Observed digest does not match the baseline digest."

    verification = EvidenceVerification(
        evidence_id=evidence.id,
        performed_by_id=actor.id,
        expected_sha256=evidence.sha256,
        observed_sha256=observed,
        result=result.value,
        reason=reason,
    )
    db.add(verification)
    evidence.integrity_status = result.value
    evidence.last_verified_at = datetime.now(timezone.utc)
    # Verified and unavailable attempts share the verification event; a digest
    # mismatch is a forensic event with its own action.
    audit_action = (
        Actions.EVIDENCE_INTEGRITY_MISMATCH
        if result == IntegrityStatus.MISMATCH
        else Actions.EVIDENCE_VERIFIED
    )
    record(
        db,
        action=audit_action,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=actor.id,
        metadata={
            "evidence_id": evidence.id,
            "evidence_number": evidence.evidence_number,
            "result": result.value,
        },
    )
    db.commit()
    db.refresh(verification)
    db.refresh(evidence)
    return verification


def list_evidence(
    db: Session,
    inv: Investigation,
    evidence_type: EvidenceType | None = None,
    integrity: IntegrityStatus | None = None,
    query: str | None = None,
) -> list[Evidence]:
    stmt = (
        select(Evidence)
        .where(Evidence.investigation_id == inv.id)
        .options(selectinload(Evidence.registered_by))
        .order_by(Evidence.id)
    )
    if evidence_type is not None:
        stmt = stmt.where(Evidence.evidence_type == evidence_type.value)
    if integrity is not None:
        stmt = stmt.where(Evidence.integrity_status == integrity.value)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            (Evidence.title.like(like))
            | (Evidence.evidence_number.like(like))
            | (Evidence.original_filename.like(like))
        )
    return list(db.execute(stmt).scalars().all())


def list_verifications(db: Session, evidence: Evidence) -> list[EvidenceVerification]:
    stmt = (
        select(EvidenceVerification)
        .where(EvidenceVerification.evidence_id == evidence.id)
        .options(selectinload(EvidenceVerification.performed_by))
        .order_by(EvidenceVerification.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def list_custody(db: Session, evidence: Evidence) -> list[CustodyEvent]:
    stmt = (
        select(CustodyEvent)
        .where(CustodyEvent.evidence_id == evidence.id)
        .options(
            selectinload(CustodyEvent.from_user),
            selectinload(CustodyEvent.to_user),
            selectinload(CustodyEvent.performed_by),
        )
        .order_by(CustodyEvent.id)
    )
    return list(db.execute(stmt).scalars().all())


def record_custody(
    db: Session, inv: Investigation, evidence: Evidence, payload: CustodyCreate, actor: User
) -> CustodyEvent:
    to_user = None
    if payload.action == CustodyAction.TRANSFERRED:
        if payload.to_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Transfers require a target user.",
            )
        to_user = get_by_id(db, payload.to_user_id)
        if to_user is None or not to_user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target user.")
        if not inv_service.is_member(db, inv.id, to_user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user is not a member of this investigation.",
            )
    elif payload.to_user_id is not None:
        to_user = get_by_id(db, payload.to_user_id)
        if to_user is None or not to_user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target user.")

    holder = current_holder(db, evidence)
    event = CustodyEvent(
        evidence_id=evidence.id,
        action=payload.action.value,
        from_user_id=holder.id if holder else None,
        to_user_id=to_user.id if to_user else None,
        performed_by_id=actor.id,
        notes=payload.notes.strip(),
    )
    db.add(event)
    db.flush()
    record(
        db,
        action=(
            Actions.CUSTODY_TRANSFERRED
            if payload.action == CustodyAction.TRANSFERRED
            else Actions.EVIDENCE_CUSTODY_UPDATED
        ),
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=actor.id,
        metadata={
            "evidence_id": evidence.id,
            "evidence_number": evidence.evidence_number,
            "custody_action": payload.action.value,
            "to_user_id": to_user.id if to_user else None,
        },
    )
    db.commit()
    db.refresh(event)
    return event


def evidence_timeline(db: Session, evidence: Evidence) -> list[TimelineEntry]:
    entries = [
        TimelineEntry(
            occurred_at=evidence.created_at,
            kind="evidence",
            title=f"{evidence.evidence_number} registered",
            detail=evidence.title,
            actor_username=evidence.registered_by.username if evidence.registered_by else None,
            evidence_number=evidence.evidence_number,
        )
    ]
    for event in list_custody(db, evidence):
        entries.append(
            TimelineEntry(
                occurred_at=event.created_at,
                kind="custody",
                title=f"{evidence.evidence_number}: custody {event.action.replace('_', ' ')}",
                detail=event.notes or describe_transition(event),
                actor_username=event.performed_by.username if event.performed_by else None,
                evidence_number=evidence.evidence_number,
            )
        )
    for verification in list_verifications(db, evidence):
        entries.append(
            TimelineEntry(
                occurred_at=verification.created_at,
                kind="integrity",
                title=f"{evidence.evidence_number}: integrity {verification.result.replace('_', ' ')}",
                detail=verification.reason or "Recomputed digest matches the baseline.",
                actor_username=verification.performed_by.username
                if verification.performed_by
                else None,
                evidence_number=evidence.evidence_number,
            )
        )
    entries.sort(key=lambda e: (e.occurred_at, e.title))
    return entries


def describe_transition(event: CustodyEvent) -> str:
    frm = event.from_user.username if event.from_user else "unknown holder"
    to = event.to_user.username if event.to_user else "unknown holder"
    return f"Custody moved from {frm} to {to}."


def investigation_timeline(db: Session, inv: Investigation) -> list[TimelineEntry]:
    """Deterministic chronological narrative assembled from real records."""
    creator = get_by_id(db, inv.created_by_id)
    entries = [
        TimelineEntry(
            occurred_at=inv.created_at,
            kind="investigation",
            title="Investigation created",
            detail=f"{inv.case_number}: {inv.title}",
            actor_username=creator.username if creator else None,
        )
    ]
    for evidence in list_evidence(db, inv):
        entries.extend(evidence_timeline(db, evidence))
    for event in list_for_investigation(db, inv.id):
        if event.action == Actions.INVESTIGATION_STATUS_CHANGED:
            meta = event.event_metadata or {}
            actor = get_by_id(db, event.actor_id) if event.actor_id else None
            entries.append(
                TimelineEntry(
                    occurred_at=event.created_at,
                    kind="investigation",
                    title="Investigation status changed",
                    detail=f"{meta.get('from', '?')} to {meta.get('to', '?')}",
                    actor_username=actor.username if actor else None,
                )
            )
    entries.sort(key=lambda e: (e.occurred_at, e.title))
    return entries


def investigation_custody(db: Session, inv: Investigation, limit: int = 100) -> list[dict]:
    """Recent custody events across all evidence in the investigation."""
    stmt = (
        select(CustodyEvent, Evidence.evidence_number, Evidence.title)
        .join(Evidence, Evidence.id == CustodyEvent.evidence_id)
        .where(Evidence.investigation_id == inv.id)
        .options(
            selectinload(CustodyEvent.from_user),
            selectinload(CustodyEvent.to_user),
            selectinload(CustodyEvent.performed_by),
        )
        .order_by(CustodyEvent.id.desc())
        .limit(limit)
    )
    rows = []
    for event, number, title in db.execute(stmt).all():
        rows.append(
            {
                "id": event.id,
                "evidence_id": event.evidence_id,
                "evidence_number": number,
                "evidence_title": title,
                "action": event.action,
                "from_user": event.from_user.username if event.from_user else None,
                "to_user": event.to_user.username if event.to_user else None,
                "performed_by": event.performed_by.username if event.performed_by else None,
                "notes": event.notes,
                "created_at": event.created_at,
            }
        )
    return rows
