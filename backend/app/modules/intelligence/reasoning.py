"""Reasoning services: rule evaluation, human validation, notes, reports.

Findings are generated deterministically from the artifact store and never
auto-validated: new proposals start pending, human decisions on existing
rows are preserved across regenerations, and only accepted findings enter
reports. Reports are deterministic snapshots with a content hash.
"""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai import rules
from app.ai.rules import ArtifactFact, FactView
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.evidence import service as ev_service
from app.modules.evidence.models import Evidence
from app.modules.evidence.service import ensure_mutable
from app.modules.intelligence.models import (
    AnalysisRun,
    Artifact,
    Correlation,
    Finding,
    FindingStatus,
    InvestigationNote,
    Report,
)
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import Investigation
from app.modules.users.models import Role, User
from app.modules.workspaces import service as workspace_service
from app.modules.users.service import get_by_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_finding_produce(db: Session, inv: Investigation | None, user: User) -> Investigation:
    """Analysts may produce findings on assigned work; managers and admins too."""
    inv = inv_service.ensure_access(db, inv, user)
    ensure_mutable(inv, user)
    role = workspace_service.role_for(db, user, inv.workspace_id)
    if role == Role.ADMIN.value:
        return inv
    if role == Role.FORENSIC_ANALYST.value and inv_service.is_member(db, inv.id, user.id):
        return inv
    if inv_service.can_manage(db, inv, user):
        return inv
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def ensure_finding_review(db: Session, inv: Investigation | None, user: User) -> Investigation:
    """Final validation is reserved for managers (admin, creator, lead)."""
    inv = inv_service.ensure_manage(db, inv, user)
    ensure_mutable(inv, user)
    return inv


def build_facts(db: Session, inv: Investigation) -> FactView:
    artifacts = db.execute(
        select(Artifact).where(Artifact.investigation_id == inv.id).order_by(Artifact.id)
    ).scalars().all()
    evidence_numbers = {
        row.id: row.evidence_number
        for row in db.execute(
            select(Evidence).where(Evidence.investigation_id == inv.id)
        ).scalars().all()
    }
    facts = []
    for a in artifacts:
        span = None
        raw_span = (a.locator or {}).get("span")
        if (
            isinstance(raw_span, list)
            and len(raw_span) == 2
            and all(isinstance(v, int) for v in raw_span)
        ):
            span = (raw_span[0], raw_span[1])
        facts.append(
            ArtifactFact(
                id=a.id,
                evidence_id=a.evidence_id,
                evidence_number=evidence_numbers.get(a.evidence_id, f"#{a.evidence_id}"),
                artifact_type=a.artifact_type,
                normalized_value=a.normalized_value,
                locator_key=a.source_key,
                context=a.context,
                span=span,
            )
        )
    correlations = {
        (c.artifact_type, c.normalized_value): c.id
        for c in db.execute(
            select(Correlation).where(Correlation.investigation_id == inv.id)
        ).scalars().all()
    }
    verified = db.execute(
        select(func.count())
        .select_from(Evidence)
        .where(
            Evidence.investigation_id == inv.id,
            Evidence.integrity_status != "verified",
        )
    ).scalar_one() == 0
    return FactView(artifacts=facts, correlations=correlations, all_verified=verified)


def generate_findings(
    db: Session, inv: Investigation, user: User, run_id: int | None = None
) -> tuple[list[Finding], int]:
    """Evaluate every rule; create new pending findings, refresh untouched ones.

    Returns (all findings sorted by confidence, new count). Human decisions
    (accepted/rejected) are never overwritten.
    """
    proposed = rules.evaluate_all(build_facts(db, inv))
    created = 0
    for item in proposed:
        existing = db.execute(
            select(Finding).where(
                Finding.investigation_id == inv.id,
                Finding.rule_id == item.rule_id,
                Finding.inputs_key == item.inputs_key(),
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status == FindingStatus.PENDING_REVIEW.value:
                existing.title = item.title
                existing.summary = item.summary
                existing.confidence = item.confidence
                existing.factors = [dict(f) for f in item.factors]
                existing.evidence_ids = list(item.evidence_ids)
                existing.artifact_ids = list(item.artifact_ids)
                existing.correlation_ids = list(item.correlation_ids)
                existing.recommendations = list(item.recommendations)
                existing.generated_by_run_id = run_id
            continue
        db.add(
            Finding(
                investigation_id=inv.id,
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                title=item.title,
                summary=item.summary,
                severity=item.severity,
                confidence=item.confidence,
                factors=[dict(f) for f in item.factors],
                evidence_ids=list(item.evidence_ids),
                artifact_ids=list(item.artifact_ids),
                correlation_ids=list(item.correlation_ids),
                inputs_key=item.inputs_key(),
                recommendations=list(item.recommendations),
                status=FindingStatus.PENDING_REVIEW.value,
                generated_by_run_id=run_id,
            )
        )
        created += 1
    db.flush()
    record(
        db,
        action=Actions.AI_FINDING_GENERATED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=user.id,
        metadata={
            "new_count": created,
            "rules": sorted({item.rule_id for item in proposed}),
            "run_id": run_id,
        },
    )
    db.commit()
    findings = db.execute(
        select(Finding)
        .where(Finding.investigation_id == inv.id)
        .order_by(Finding.confidence.desc(), Finding.id)
    ).scalars().all()
    return list(findings), created


def list_findings(
    db: Session, inv: Investigation, status_filter: FindingStatus | None = None
) -> list[Finding]:
    stmt = (
        select(Finding)
        .where(Finding.investigation_id == inv.id)
        .options(selectinload(Finding.reviewer), selectinload(Finding.investigation))
        .order_by(Finding.confidence.desc(), Finding.id)
    )
    if status_filter is not None:
        stmt = stmt.where(Finding.status == status_filter.value)
    return list(db.execute(stmt).scalars().all())


def get_finding(db: Session, inv: Investigation, finding_id: int) -> Finding | None:
    stmt = (
        select(Finding)
        .where(Finding.investigation_id == inv.id, Finding.id == finding_id)
        .options(selectinload(Finding.reviewer), selectinload(Finding.investigation))
    )
    return db.execute(stmt).scalar_one_or_none()


def review_finding(
    db: Session, inv: Investigation, finding: Finding, status_value: str,
    note: str | None, reviewer: User,
) -> Finding:
    finding.status = status_value
    finding.reviewer_id = reviewer.id
    finding.reviewed_at = _now()
    finding.review_note = note.strip()[:1000] if note and note.strip() else None
    record(
        db,
        action=(
            Actions.AI_FINDING_ACCEPTED
            if status_value == FindingStatus.ACCEPTED.value
            else Actions.AI_FINDING_REJECTED
        ),
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=reviewer.id,
        metadata={"finding_id": finding.id, "rule_id": finding.rule_id},
    )
    db.commit()
    db.refresh(finding)
    return finding


def list_notes(
    db: Session, inv: Investigation, finding_id: int | None = None
) -> list[InvestigationNote]:
    stmt = (
        select(InvestigationNote)
        .where(InvestigationNote.investigation_id == inv.id)
        .options(selectinload(InvestigationNote.author))
        .order_by(InvestigationNote.id)
    )
    if finding_id is not None:
        stmt = stmt.where(InvestigationNote.finding_id == finding_id)
    return list(db.execute(stmt).scalars().all())


def create_note(
    db: Session, inv: Investigation, body: str, author: User, finding_id: int | None = None
) -> InvestigationNote:
    text = body.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Note body is required."
        )
    if finding_id is not None and get_finding(db, inv, finding_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")
    note = InvestigationNote(
        investigation_id=inv.id, finding_id=finding_id, author_id=author.id, body=text[:2000]
    )
    db.add(note)
    db.flush()
    record(
        db,
        action=Actions.INVESTIGATION_NOTE_ADDED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=author.id,
        metadata={"note_id": note.id, "finding_id": finding_id},
    )
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, inv: Investigation, note_id: int, body: str, user: User):
    note = db.get(InvestigationNote, note_id)
    if note is None or note.investigation_id != inv.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
    if note.author_id != user.id and not workspace_service.is_admin(db, user, inv.workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    text = body.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Note body is required."
        )
    note.body = text[:2000]
    record(
        db,
        action=Actions.INVESTIGATION_NOTE_UPDATED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=user.id,
        metadata={"note_id": note.id},
    )
    db.commit()
    db.refresh(note)
    return note


def _next_report_number(db: Session, investigation_id: int) -> int:
    from app.modules.intelligence.models import Report

    current = db.execute(
        select(func.max(Report.report_number)).where(
            Report.investigation_id == investigation_id
        )
    ).scalar_one_or_none()
    return (current or 0) + 1


def generate_report(
    db: Session, inv: Investigation, user: User, *, force_deterministic: bool = False
) -> Report:
    """Snapshot accepted findings, deterministic records, and grounded narrative."""
    from app.modules.intelligence.models import Report
    from app.modules.intelligence.narrative import deterministic_narrative, generate_narrative

    full = inv_service.get_investigation(db, inv.id)
    assert full is not None
    evidence_items = ev_service.list_evidence(db, full)
    accepted = [
        f for f in list_findings(db, full)
        if f.status == FindingStatus.ACCEPTED.value
    ]
    notes = list_notes(db, full)
    evidence_summary = []
    for item in evidence_items:
        holder = ev_service.current_holder(db, item)
        evidence_summary.append(
            {
                "evidence_number": item.evidence_number,
                "title": item.title,
                "evidence_type": item.evidence_type,
                "original_filename": item.original_filename,
                "file_size": item.file_size,
                "sha256": item.sha256,
                "integrity_status": item.integrity_status,
                "last_verified_at": (
                    item.last_verified_at.isoformat() if item.last_verified_at else None
                ),
                "registered_by": (
                    item.registered_by.username if item.registered_by else None
                ),
                "current_holder": holder.username if holder else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    findings_payload = []
    for finding in accepted:
        reviewer = get_by_id(db, finding.reviewer_id) if finding.reviewer_id else None
        findings_payload.append(
            {
                "id": finding.id,
                "rule_id": finding.rule_id,
                "rule_version": finding.rule_version,
                "title": finding.title,
                "summary": finding.summary,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "factors": finding.factors,
                "evidence_ids": finding.evidence_ids,
                "artifact_ids": finding.artifact_ids,
                "correlation_ids": finding.correlation_ids,
                "recommendations": finding.recommendations,
                "reviewer": reviewer.username if reviewer else None,
                "reviewed_at": finding.reviewed_at.isoformat() if finding.reviewed_at else None,
                "review_note": finding.review_note,
            }
        )
    recommendations: list[str] = []
    for payload in findings_payload:
        for recommendation in payload["recommendations"]:
            if recommendation not in recommendations:
                recommendations.append(recommendation)
    custody_payload = []
    for row in ev_service.investigation_custody(db, full):
        entry = dict(row)
        created = entry.get("created_at")
        entry["created_at"] = created.isoformat() if created else None
        custody_payload.append(entry)
    from app.modules.workspaces.models import WorkspaceMembership
    workspace_roles = dict(db.execute(select(
        WorkspaceMembership.user_id, WorkspaceMembership.role
    ).where(WorkspaceMembership.workspace_id == full.workspace_id)).all())
    grounded_context = {
        "investigation": {
            "case_number": full.case_number,
            "title": full.title,
            "description": full.description,
            "status": full.status,
            "priority": full.priority,
        },
        "accepted_findings": findings_payload,
        "evidence_count": len(evidence_summary),
        "confidence_scale": "0-100 deterministic weighted score, not a probability",
        "recommendations": recommendations,
        "investigator_notes": [
            {"finding_id": n.finding_id, "body": n.body} for n in notes
        ],
    }
    narrative_result = (
        deterministic_narrative(grounded_context)
        if force_deterministic
        else generate_narrative(grounded_context)
    )
    content = {
        "investigation": {
            "case_number": full.case_number,
            "title": full.title,
            "description": full.description,
            "status": full.status,
            "priority": full.priority,
            "created_by": full.created_by.username if full.created_by else None,
            "lead_investigator": (
                full.lead_investigator.username if full.lead_investigator else None
            ),
            "team": [
                {"username": m.user.username,
                 "full_name": m.user.full_name,
                 "role": workspace_roles.get(m.user_id, m.user.role),
                 "team_role": m.team_role}
                for m in full.members
            ],
            "created_at": full.created_at.isoformat() if full.created_at else None,
        },
        "evidence_summary": evidence_summary,
        "custody_summary": custody_payload,
        "timeline": [
            {"occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
             "kind": e.kind, "title": e.title, "detail": e.detail,
             "actor_username": e.actor_username, "evidence_number": e.evidence_number}
            for e in ev_service.investigation_timeline(db, full)
        ],
        "accepted_findings": findings_payload,
        "recommendations": recommendations,
        "investigator_notes": [
            {"author": n.author.username if n.author else None,
             "finding_id": n.finding_id, "body": n.body,
             "created_at": n.created_at.isoformat() if n.created_at else None}
            for n in notes
        ],
        "generated_by": user.username,
        "generated_at": _now().isoformat(),
        "generator": "grounded-report-v2",
        "narrative": narrative_result.narrative,
        "generation_metadata": narrative_result.metadata,
    }
    canonical = json.dumps(content, sort_keys=True, default=str)
    report = Report(
        investigation_id=full.id,
        report_number=_next_report_number(db, full.id),
        generated_by_id=user.id,
        content=content,
        content_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )
    db.add(report)
    db.flush()
    record(
        db,
        action=Actions.REPORT_GENERATED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=full.id,
        actor_id=user.id,
        metadata={
            "report_id": report.id,
            "report_number": report.report_number,
            "accepted_findings": len(findings_payload),
            "content_sha256": report.content_sha256,
        },
    )
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, inv: Investigation):
    from app.modules.intelligence.models import Report

    stmt = (
        select(Report)
        .where(Report.investigation_id == inv.id)
        .order_by(Report.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_report(db: Session, inv: Investigation, report_id: int):
    from app.modules.intelligence.models import Report

    stmt = select(Report).where(
        Report.investigation_id == inv.id, Report.id == report_id
    )
    return db.execute(stmt).scalar_one_or_none()
