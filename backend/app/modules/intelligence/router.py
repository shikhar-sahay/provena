"""Intelligence endpoints: runs, eligibility, artifacts, correlations."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.evidence.models import Evidence
from app.modules.intelligence import service
from app.modules.intelligence.models import Artifact, ArtifactType, CorrelationArtifact
from app.modules.intelligence.schemas import (
    AnalysisRunRead,
    ArtifactRead,
    CorrelationArtifactRead,
    CorrelationDetailRead,
    CorrelationEvidence,
    CorrelationRead,
    EligibilityEntry,
    RunEvidenceRead,
    RunStart,
)
from app.modules.investigations import service as inv_service
from app.modules.users.models import User

router = APIRouter(prefix="/investigations/{investigation_id}/analysis", tags=["analysis"])


def _investigation(db: Session, investigation_id: int, user: User):
    inv = inv_service.get_investigation(db, investigation_id)
    return service.ensure_analysis_view(db, inv, user)


def _evidence_lookup(db: Session, inv_id: int) -> dict[int, Evidence]:
    rows = db.execute(
        select(Evidence).where(Evidence.investigation_id == inv_id)
    ).scalars().all()
    return {row.id: row for row in rows}


@router.get("/eligibility", response_model=list[EligibilityEntry])
def analysis_eligibility(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return [EligibilityEntry(**entry) for entry in service.eligibility(db, inv)]


@router.post("/runs", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def start_analysis_run(
    investigation_id: int,
    payload: RunStart,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = inv_service.get_investigation(db, investigation_id)
    inv = service.ensure_analysis_initiate(db, inv, user)
    run = service.start_run(db, inv, payload.evidence_ids, user)
    return _to_run_read(db, run)


def _to_run_read(db: Session, run) -> AnalysisRunRead:
    evidence_map = _evidence_lookup(db, run.investigation_id)
    data = AnalysisRunRead.model_validate(run)
    data.run_label = service.run_label(run.run_number)
    data.initiated_by_username = run.initiated_by.username if run.initiated_by else None
    data.evidence_outcomes = [
        RunEvidenceRead(
            id=outcome.id,
            evidence_id=outcome.evidence_id,
            evidence_number=(
                evidence_map[outcome.evidence_id].evidence_number
                if outcome.evidence_id in evidence_map
                else None
            ),
            status=outcome.status,
            error=outcome.error,
            artifact_count=outcome.artifact_count,
        )
        for outcome in run.evidence_outcomes
    ]
    return data


@router.get("/runs", response_model=list[AnalysisRunRead])
def list_analysis_runs(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    return [_to_run_read(db, run) for run in service.list_runs(db, inv)]


@router.get("/runs/{run_id}", response_model=AnalysisRunRead)
def get_analysis_run(
    investigation_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    run = service.get_run(db, inv, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    return _to_run_read(db, run)


@router.get("/artifacts", response_model=dict)
def list_artifacts(
    investigation_id: int,
    artifact_type: ArtifactType | None = Query(default=None),
    evidence_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    items, total = service.list_artifacts(
        db, inv, artifact_type, evidence_id, q, limit, offset
    )
    evidence_map = _evidence_lookup(db, inv.id)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_to_artifact_read(evidence_map, item) for item in items],
    }


def _to_artifact_read(evidence_map: dict, item) -> ArtifactRead:
    data = ArtifactRead.model_validate(item)
    evidence = evidence_map.get(item.evidence_id)
    data.evidence_number = evidence.evidence_number if evidence else None
    data.evidence_title = evidence.title if evidence else None
    return data


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(
    investigation_id: int,
    artifact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    item = service.get_artifact(db, inv, artifact_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    return _to_artifact_read(_evidence_lookup(db, inv.id), item)


@router.get("/correlations", response_model=list[CorrelationRead])
def list_correlations(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    out = []
    for correlation in service.list_correlations(db, inv):
        data = CorrelationRead.model_validate(correlation)
        data.evidence_items = _correlation_evidence(db, inv, correlation)
        out.append(data)
    return out


def _correlation_evidence(db: Session, inv, correlation) -> list:
    rows = db.execute(
        select(
            Artifact.evidence_id,
            Evidence.evidence_number,
            Evidence.title,
            func.count(Artifact.id),
        )
        .join(Evidence, Evidence.id == Artifact.evidence_id)
        .join(CorrelationArtifact, CorrelationArtifact.artifact_id == Artifact.id)
        .where(CorrelationArtifact.correlation_id == correlation.id)
        .group_by(Artifact.evidence_id, Evidence.evidence_number, Evidence.title)
        .order_by(Evidence.evidence_number)
    ).all()
    return [
        CorrelationEvidence(
            evidence_id=row[0],
            evidence_number=row[1],
            evidence_title=row[2],
            artifact_count=row[3],
        )
        for row in rows
    ]


@router.get("/correlations/{correlation_id}", response_model=CorrelationDetailRead)
def get_correlation(
    investigation_id: int,
    correlation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _investigation(db, investigation_id, user)
    correlation = service.get_correlation(db, inv, correlation_id)
    if correlation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correlation not found.")
    data = CorrelationDetailRead.model_validate(correlation)
    data.evidence_items = _correlation_evidence(db, inv, correlation)
    members = db.execute(
        select(Artifact, Evidence.evidence_number)
        .join(Evidence, Evidence.id == Artifact.evidence_id)
        .join(CorrelationArtifact, CorrelationArtifact.artifact_id == Artifact.id)
        .where(CorrelationArtifact.correlation_id == correlation.id)
        .order_by(Evidence.evidence_number, Artifact.id)
    ).all()
    data.artifacts = [
        CorrelationArtifactRead(
            id=artifact.id,
            evidence_id=artifact.evidence_id,
            evidence_number=number,
            artifact_type=artifact.artifact_type,
            raw_value=artifact.raw_value,
            normalized_value=artifact.normalized_value,
            locator=artifact.locator,
            source_key=artifact.source_key,
            context=artifact.context,
            method=artifact.method,
            extractor_name=artifact.extractor_name,
            extractor_version=artifact.extractor_version,
        )
        for artifact, number in members
    ]
    return data
