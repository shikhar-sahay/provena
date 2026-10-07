"""Intelligence service: eligibility, runs, artifacts, correlations.

Authorization (backend-enforced):
- Viewing intelligence: investigation members (admins bypass scoping).
- Initiating analysis: admins; investigators with management access;
  forensic analysts who are members. Custodians are denied (403).
- Archived investigations: admins only for new runs.
- Outsiders: 404 through the standard access check.

Integrity gate (hard rule): only evidence whose current integrity status is
VERIFIED is processed. Everything else becomes an explicit blocked outcome.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.ai import correlate as correlate_engine
from app.ai import extractors
from app.ai import parsers
from app.ai.normalize import normalize
from app.ai.parsers import ParserError, SourceUnit
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.evidence import storage
from app.modules.evidence.models import Evidence, IntegrityStatus
from app.modules.evidence.service import ensure_mutable
from app.modules.intelligence.models import (
    AnalysisRun,
    AnalysisRunEvidence,
    Artifact,
    ArtifactType,
    Correlation,
    CorrelationArtifact,
    RunEvidenceStatus,
    RunStatus,
)
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import Investigation
from app.modules.users.models import Role, User
from app.modules.workspaces import service as workspace_service

PIPELINE_VERSION = "1"

SUPPORTED_EXTENSIONS = {"txt": "txt", "log": "log", "csv": "csv", "json": "json", "pdf": "pdf"}

BLOCK_REASONS = {
    IntegrityStatus.NOT_VERIFIED.value: (
        RunEvidenceStatus.BLOCKED_NOT_VERIFIED,
        "Evidence has no independent verification yet. Verify integrity first.",
    ),
    IntegrityStatus.MISMATCH.value: (
        RunEvidenceStatus.BLOCKED_MISMATCH,
        "Stored bytes do not match the baseline digest. Resolve the mismatch first.",
    ),
    IntegrityStatus.UNAVAILABLE.value: (
        RunEvidenceStatus.BLOCKED_UNAVAILABLE,
        "Stored bytes could not be read. Restore access first.",
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def supported_extension(filename: str) -> str | None:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in name:
        return None
    return SUPPORTED_EXTENSIONS.get(name.rsplit(".", 1)[-1].casefold())


def ensure_analysis_view(db: Session, inv: Investigation | None, user: User) -> Investigation:
    return inv_service.ensure_access(db, inv, user)


def ensure_analysis_initiate(
    db: Session, inv: Investigation | None, user: User
) -> Investigation:
    inv = inv_service.ensure_access(db, inv, user)
    ensure_mutable(inv, user)
    role = workspace_service.role_for(db, user, inv.workspace_id)
    if role == Role.ADMIN.value:
        return inv
    if role == Role.INVESTIGATOR.value and inv_service.can_manage(db, inv, user):
        return inv
    if role == Role.FORENSIC_ANALYST.value and inv_service.is_member(db, inv.id, user.id):
        return inv
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def eligibility(db: Session, inv: Investigation) -> list[dict]:
    """Per-evidence processing eligibility with human-readable reasons."""
    stmt = (
        select(Evidence)
        .where(Evidence.investigation_id == inv.id)
        .order_by(Evidence.id)
    )
    entries = []
    for evidence in db.execute(stmt).scalars().all():
        ext = supported_extension(evidence.original_filename)
        if ext is None:
            entries.append(
                {
                    "evidence_id": evidence.id,
                    "evidence_number": evidence.evidence_number,
                    "title": evidence.title,
                    "integrity_status": evidence.integrity_status,
                    "supported": False,
                    "eligible": False,
                    "reason": "File format is not supported for automated processing.",
                }
            )
            continue
        if evidence.integrity_status != IntegrityStatus.VERIFIED.value:
            _, reason = BLOCK_REASONS.get(
                evidence.integrity_status,
                (RunEvidenceStatus.BLOCKED_NOT_VERIFIED, "Evidence is not verified."),
            )
            entries.append(
                {
                    "evidence_id": evidence.id,
                    "evidence_number": evidence.evidence_number,
                    "title": evidence.title,
                    "integrity_status": evidence.integrity_status,
                    "supported": True,
                    "eligible": False,
                    "reason": reason,
                }
            )
            continue
        entries.append(
            {
                "evidence_id": evidence.id,
                "evidence_number": evidence.evidence_number,
                "title": evidence.title,
                "integrity_status": evidence.integrity_status,
                "supported": True,
                "eligible": True,
                "reason": None,
            }
        )
    return entries


def _next_run_number(db: Session, investigation_id: int) -> int:
    current = db.execute(
        select(func.max(AnalysisRun.run_number)).where(
            AnalysisRun.investigation_id == investigation_id
        )
    ).scalar_one_or_none()
    return (current or 0) + 1


def _get_or_create_artifact(
    db: Session,
    *,
    inv_id: int,
    evidence_id: int,
    run_id: int,
    artifact_type: str,
    raw_value: str,
    normalized_value: str,
    unit: SourceUnit,
    locator_override: dict | None = None,
    extractor,
) -> Artifact:
    stmt = select(Artifact).where(
        Artifact.evidence_id == evidence_id,
        Artifact.artifact_type == artifact_type,
        Artifact.normalized_value == normalized_value,
        Artifact.source_key == unit.locator_key,
        Artifact.extractor_name == extractor.name,
        Artifact.extractor_version == extractors.EXTRACTOR_VERSION,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    artifact = Artifact(
        investigation_id=inv_id,
        evidence_id=evidence_id,
        run_id=run_id,
        artifact_type=artifact_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        locator=locator_override if locator_override is not None else dict(unit.locator),
        source_key=unit.locator_key,
        context=unit.context,
        method=extractor.method,
        extractor_name=extractor.name,
        extractor_version=extractors.EXTRACTOR_VERSION,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _process_evidence(
    db: Session, inv: Investigation, evidence: Evidence, run: AnalysisRun
) -> tuple[str, str | None, int]:
    """Process one evidence item. Returns (outcome_status, error, artifact_count)."""
    if evidence.integrity_status != IntegrityStatus.VERIFIED.value:
        outcome, reason = BLOCK_REASONS.get(
            evidence.integrity_status,
            (RunEvidenceStatus.BLOCKED_NOT_VERIFIED, "Evidence is not verified."),
        )
        return outcome.value, reason, 0
    ext = supported_extension(evidence.original_filename)
    if ext is None:
        return (
            RunEvidenceStatus.UNSUPPORTED.value,
            "File format is not supported for automated processing.",
            0,
        )
    try:
        with storage.open_stored(evidence.storage_key) as handle:
            data = handle.read()
    except (OSError, ValueError):
        return RunEvidenceStatus.FAILED.value, "Stored bytes could not be read.", 0
    try:
        units = parsers.PARSERS[ext](data)
    except parsers.NoTextError as exc:
        return RunEvidenceStatus.FAILED.value, str(exc), 0
    except ParserError as exc:
        return RunEvidenceStatus.FAILED.value, str(exc), 0
    count = 0
    for unit in units:
        for extractor, extraction in extractors.extract_all(unit):
            normalized = normalize(extraction.artifact_type, extraction.raw_value)
            if normalized is None:
                continue
            locator = dict(unit.locator)
            if extraction.span is not None:
                locator["span"] = [extraction.span[0], extraction.span[1]]
            _get_or_create_artifact(
                db,
                inv_id=inv.id,
                evidence_id=evidence.id,
                run_id=run.id,
                artifact_type=extraction.artifact_type,
                raw_value=extraction.raw_value,
                normalized_value=normalized,
                unit=unit,
                locator_override=locator,
                extractor=extractor,
            )
            count += 1
    return RunEvidenceStatus.PROCESSED.value, None, count


def _rebuild_correlations(db: Session, inv: Investigation) -> int:
    """Rebuild shared-value correlations from the canonical artifact store.

    Timestamps are excluded by design: identical clock readings across
    independent logs are usually coincidence, not entity recurrence. They
    remain first-class artifacts for rules and display.
    """
    from app.modules.intelligence.models import ArtifactType

    db.execute(
        Correlation.__table__.delete().where(Correlation.investigation_id == inv.id)
    )
    rows = db.execute(
        select(Artifact.id, Artifact.evidence_id, Artifact.artifact_type, Artifact.normalized_value)
        .where(
            Artifact.investigation_id == inv.id,
            Artifact.artifact_type != ArtifactType.TIMESTAMP.value,
        )
        .order_by(Artifact.id)
    ).all()
    built = correlate_engine.build_correlations(
        [(r[0], r[1], r[2], r[3]) for r in rows]
    )
    for entry in built:
        correlation = Correlation(
            investigation_id=inv.id,
            correlation_type="shared_value",
            artifact_type=entry["artifact_type"],
            normalized_value=entry["normalized_value"],
            evidence_count=len(entry["evidence_ids"]),
            artifact_count=len(entry["artifact_ids"]),
        )
        db.add(correlation)
        db.flush()
        for artifact_id in entry["artifact_ids"]:
            db.add(
                CorrelationArtifact(correlation_id=correlation.id, artifact_id=artifact_id)
            )
    return len(built)


def start_run(
    db: Session, inv: Investigation, evidence_ids: list[int], user: User
) -> AnalysisRun:
    """Run the pipeline synchronously over selected evidence.

    Blocked and unsupported items become explicit per-evidence outcomes, not
    silent skips. Unexpected failures mark the run FAILED without leaving
    half-persisted intelligence state.
    """
    wanted = list(dict.fromkeys(evidence_ids))
    evidence_map = {
        e.id: e
        for e in db.execute(
            select(Evidence).where(
                Evidence.investigation_id == inv.id, Evidence.id.in_(wanted)
            )
        )
        .scalars()
        .all()
    }
    missing = [eid for eid in wanted if eid not in evidence_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")

    run = AnalysisRun(
        investigation_id=inv.id,
        run_number=_next_run_number(db, inv.id),
        initiated_by_id=user.id,
        status=RunStatus.RUNNING.value,
        pipeline_version=PIPELINE_VERSION,
        evidence_count=len(wanted),
    )
    db.add(run)
    db.flush()
    record(
        db,
        action=Actions.AI_ANALYSIS_STARTED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=user.id,
        metadata={
            "run_id": run.id,
            "run_number": run.run_number,
            "evidence_count": len(wanted),
            "pipeline_version": PIPELINE_VERSION,
        },
    )
    try:
        total_artifacts = 0
        for evidence_id in wanted:
            evidence = evidence_map[evidence_id]
            with db.begin_nested():
                outcome, error, count = _process_evidence(db, inv, evidence, run)
                db.add(
                    AnalysisRunEvidence(
                        run_id=run.id,
                        evidence_id=evidence.id,
                        status=outcome,
                        error=error,
                        artifact_count=count,
                    )
                )
                total_artifacts += count
        correlation_count = _rebuild_correlations(db, inv)
        run.status = RunStatus.COMPLETED.value
        run.artifact_count = total_artifacts
        run.correlation_count = correlation_count
        run.completed_at = _now()
        record(
            db,
            action=Actions.AI_ANALYSIS_COMPLETED,
            resource_type=ResourceTypes.INVESTIGATION,
            resource_id=inv.id,
            actor_id=user.id,
            metadata={
                "run_id": run.id,
                "run_number": run.run_number,
                "evidence_count": len(wanted),
                "artifact_count": total_artifacts,
                "correlation_count": correlation_count,
                "pipeline_version": PIPELINE_VERSION,
            },
        )
        db.commit()
    except Exception as exc:
        failure = str(exc)[:1000]
        run_number = run.run_number
        evidence_count = run.evidence_count
        db.rollback()
        # The rollback removes a newly flushed run from the session. Persist a
        # fresh failure record so an unexpected pipeline error never erases
        # the explicit run history or triggers a refresh of a transient row.
        run = AnalysisRun(
            investigation_id=inv.id,
            run_number=run_number,
            initiated_by_id=user.id,
            status=RunStatus.FAILED.value,
            pipeline_version=PIPELINE_VERSION,
            evidence_count=evidence_count,
            error=failure,
            completed_at=_now(),
        )
        db.add(run)
        db.flush()
        record(
            db,
            action=Actions.AI_ANALYSIS_FAILED,
            resource_type=ResourceTypes.INVESTIGATION,
            resource_id=inv.id,
            actor_id=user.id,
            metadata={
                "run_id": run.id,
                "run_number": run.run_number,
                "pipeline_version": PIPELINE_VERSION,
            },
        )
        db.commit()
    db.refresh(run)
    return run


def list_runs(db: Session, inv: Investigation) -> list[AnalysisRun]:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.investigation_id == inv.id)
        .options(selectinload(AnalysisRun.initiated_by))
        .order_by(AnalysisRun.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_run(db: Session, inv: Investigation, run_id: int) -> AnalysisRun | None:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.investigation_id == inv.id, AnalysisRun.id == run_id)
        .options(
            selectinload(AnalysisRun.initiated_by),
            selectinload(AnalysisRun.evidence_outcomes),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def run_label(run_number: int) -> str:
    return f"RUN-{run_number:04d}"


def list_artifacts(
    db: Session,
    inv: Investigation,
    artifact_type: ArtifactType | None = None,
    evidence_id: int | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Artifact], int]:
    stmt = select(Artifact).where(Artifact.investigation_id == inv.id)
    if artifact_type is not None:
        stmt = stmt.where(Artifact.artifact_type == artifact_type.value)
    if evidence_id is not None:
        stmt = stmt.where(Artifact.evidence_id == evidence_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(Artifact.normalized_value.like(like))
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    items = list(
        db.execute(stmt.order_by(Artifact.id).limit(limit).offset(offset)).scalars().all()
    )
    return items, total


def get_artifact(db: Session, inv: Investigation, artifact_id: int) -> Artifact | None:
    stmt = select(Artifact).where(
        Artifact.investigation_id == inv.id, Artifact.id == artifact_id
    )
    return db.execute(stmt).scalar_one_or_none()


def list_correlations(db: Session, inv: Investigation) -> list[Correlation]:
    stmt = (
        select(Correlation)
        .where(Correlation.investigation_id == inv.id)
        .order_by(Correlation.artifact_type, Correlation.normalized_value)
    )
    return list(db.execute(stmt).scalars().all())


def get_correlation(db: Session, inv: Investigation, correlation_id: int) -> Correlation | None:
    stmt = (
        select(Correlation)
        .where(Correlation.investigation_id == inv.id, Correlation.id == correlation_id)
        .options(selectinload(Correlation.members))
    )
    return db.execute(stmt).scalar_one_or_none()
