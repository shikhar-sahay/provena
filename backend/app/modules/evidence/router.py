"""Evidence endpoints: registration, metadata, verification, custody, timelines, download."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.auth.dependencies import get_current_user
from app.modules.evidence import service
from app.modules.evidence.models import EvidenceType, IntegrityStatus
from app.modules.evidence.schemas import (
    CustodyCreate,
    CustodyEventRead,
    EvidenceRead,
    EvidenceUpdate,
    TimelineEntry,
    VerificationRead,
)
from app.modules.evidence.storage import open_stored
from app.modules.investigations import service as inv_service
from app.modules.users.models import User
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/investigations/{investigation_id}/evidence", tags=["evidence"])


def _to_read(db: Session, evidence) -> EvidenceRead:
    data = EvidenceRead.model_validate(evidence)
    holder = service.current_holder(db, evidence)
    data.current_holder = UserRead.model_validate(holder) if holder else None
    return data


def _investigation(db: Session, investigation_id: int, user: User):
    inv = inv_service.get_investigation(db, investigation_id)
    return inv_service.ensure_access(db, inv, user)


@router.get("", response_model=list[EvidenceRead])
def list_evidence(
    investigation_id: int,
    evidence_type: EvidenceType | None = Query(default=None),
    integrity_status: IntegrityStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return [_to_read(db, e) for e in service.list_evidence(db, inv, evidence_type, integrity_status, q)]


@router.post("", response_model=EvidenceRead, status_code=201)
def register_evidence(
    investigation_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(default=""),
    evidence_type: EvidenceType = Form(default=EvidenceType.OTHER),
    source: str = Form(default=""),
    acquired_at: datetime | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = inv_service.ensure_manage(
        db, inv_service.get_investigation(db, investigation_id), user
    )
    service.ensure_mutable(inv, user)
    evidence = service.register_evidence(
        db,
        inv,
        title=title,
        description=description,
        evidence_type=evidence_type,
        source=source,
        acquired_at=acquired_at,
        filename=file.filename or "unnamed",
        content_type=file.content_type,
        stream=file.file,
        actor=user,
    )
    return _to_read(db, evidence)


@router.get("/{evidence_id}", response_model=EvidenceRead)
def get_evidence(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return _to_read(db, service.ensure_evidence_access(db, inv, evidence_id, user))


@router.patch("/{evidence_id}", response_model=EvidenceRead)
def update_evidence(
    investigation_id: int,
    evidence_id: int,
    payload: EvidenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = inv_service.get_investigation(db, investigation_id)
    evidence = service.ensure_evidence_manage(db, inv, evidence_id, user)
    return _to_read(db, service.update_evidence_metadata(db, inv, evidence, payload, user))


@router.post("/{evidence_id}/verify", response_model=VerificationRead)
def verify_evidence(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    service.ensure_mutable(inv, user)
    evidence = service.ensure_evidence_access(db, inv, evidence_id, user)
    return VerificationRead.model_validate(service.verify_evidence(db, inv, evidence, user))


@router.get("/{evidence_id}/verifications", response_model=list[VerificationRead])
def list_verifications(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    evidence = service.ensure_evidence_access(db, inv, evidence_id, user)
    return [VerificationRead.model_validate(v) for v in service.list_verifications(db, evidence)]


@router.get("/{evidence_id}/custody", response_model=list[CustodyEventRead])
def list_custody(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    evidence = service.ensure_evidence_access(db, inv, evidence_id, user)
    return [CustodyEventRead.model_validate(e) for e in service.list_custody(db, evidence)]


@router.post("/{evidence_id}/custody", response_model=CustodyEventRead, status_code=201)
def record_custody(
    investigation_id: int,
    evidence_id: int,
    payload: CustodyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    evidence = service.ensure_custody_permission(db, inv, evidence_id, user)
    return CustodyEventRead.model_validate(
        service.record_custody(db, inv, evidence, payload, user)
    )


@router.get("/{evidence_id}/timeline", response_model=list[TimelineEntry])
def evidence_timeline(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    evidence = service.ensure_evidence_access(db, inv, evidence_id, user)
    return service.evidence_timeline(db, evidence)


@router.get("/{evidence_id}/download")
def download_evidence(
    investigation_id: int,
    evidence_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    evidence = service.ensure_evidence_access(db, inv, evidence_id, user)
    try:
        handle = open_stored(evidence.storage_key)
        handle.close()
    except (OSError, ValueError):
        from fastapi import HTTPException, status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Stored file is unavailable.",
        )
    from app.modules.evidence.storage import resolve

    record(
        db,
        action=Actions.EVIDENCE_DOWNLOADED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=user.id,
        metadata={
            "evidence_id": evidence.id,
            "evidence_number": evidence.evidence_number,
        },
    )
    db.commit()
    return FileResponse(
        path=resolve(evidence.storage_key),
        filename=evidence.original_filename,
        media_type="application/octet-stream",
    )


timeline_router = APIRouter(prefix="/investigations/{investigation_id}", tags=["timeline"])


@timeline_router.get("/timeline", response_model=list[TimelineEntry])
def investigation_timeline(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return service.investigation_timeline(db, inv)


@timeline_router.get("/custody")
def investigation_custody(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return service.investigation_custody(db, inv)
