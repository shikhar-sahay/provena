"""Global search service: searches across authorized investigations, evidence, findings, and artifacts.

Server-side authorization is strictly enforced: users only see records from investigations
they are members of (admins see all). Empty queries or queries shorter than 2 characters
return empty results immediately.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.evidence.models import Evidence
from app.modules.intelligence.models import Artifact, Finding
from app.modules.investigations.models import Investigation, InvestigationMember
from app.modules.search.schemas import SearchResponse, SearchResultItem
from app.modules.users.models import Role, User
from app.modules.workspaces import service as workspace_service


def search_all(db: Session, user: User, query: str, limit_per_category: int = 5) -> SearchResponse:
    q = query.strip()
    if len(q) < 2:
        return SearchResponse(query=q, total=0, results=[])

    term = f"%{q}%"

    # 1. Accessible investigation IDs
    membership = workspace_service.require_membership(db, user)
    inv_stmt = select(Investigation.id, Investigation.title, Investigation.case_number, Investigation.status).where(
        Investigation.workspace_id == membership.workspace_id
    )
    if membership.role != Role.ADMIN.value:
        inv_stmt = inv_stmt.where(
            Investigation.id.in_(
                select(InvestigationMember.investigation_id).where(
                    InvestigationMember.user_id == user.id
                )
            )
        )
    accessible_rows = db.execute(inv_stmt).all()
    accessible_map = {row.id: (row.title, row.case_number) for row in accessible_rows}
    accessible_ids = list(accessible_map.keys())

    if not accessible_ids:
        return SearchResponse(query=q, total=0, results=[])

    results: list[SearchResultItem] = []

    # 2. Match Investigations
    inv_matches = [
        row for row in accessible_rows
        if q.lower() in row.title.lower() or q.lower() in row.case_number.lower()
    ][:limit_per_category]

    for inv in inv_matches:
        results.append(
            SearchResultItem(
                category="investigation",
                id=inv.id,
                title=inv.title,
                subtitle=f"{inv.case_number} · {inv.status}",
                url=f"/investigations/{inv.id}",
                investigation_id=inv.id,
                investigation_title=inv.title,
            )
        )

    # 3. Match Evidence
    ev_stmt = (
        select(Evidence)
        .where(
            Evidence.investigation_id.in_(accessible_ids),
            Evidence.title.ilike(term) | Evidence.evidence_number.ilike(term) | Evidence.original_filename.ilike(term),
        )
        .order_by(Evidence.id.desc())
        .limit(limit_per_category)
    )
    ev_matches = db.execute(ev_stmt).scalars().all()
    for ev in ev_matches:
        inv_title, inv_case = accessible_map.get(ev.investigation_id, ("Investigation", ""))
        results.append(
            SearchResultItem(
                category="evidence",
                id=ev.id,
                title=f"{ev.evidence_number}: {ev.title}",
                subtitle=f"{inv_case} · {ev.original_filename} ({ev.integrity_status})",
                url=f"/investigations/{ev.investigation_id}/evidence/{ev.id}",
                investigation_id=ev.investigation_id,
                investigation_title=inv_title,
            )
        )

    # 4. Match Findings
    f_stmt = (
        select(Finding)
        .where(
            Finding.investigation_id.in_(accessible_ids),
            Finding.title.ilike(term) | Finding.summary.ilike(term) | Finding.rule_id.ilike(term),
        )
        .order_by(Finding.confidence.desc())
        .limit(limit_per_category)
    )
    f_matches = db.execute(f_stmt).scalars().all()
    for f in f_matches:
        inv_title, inv_case = accessible_map.get(f.investigation_id, ("Investigation", ""))
        results.append(
            SearchResultItem(
                category="finding",
                id=f.id,
                title=f.title,
                subtitle=f"{inv_case} · {f.severity.upper()} · {f.status} ({f.confidence}/100)",
                url=f"/investigations/{f.investigation_id}/analysis",
                investigation_id=f.investigation_id,
                investigation_title=inv_title,
            )
        )

    # 5. Match Artifacts
    art_stmt = (
        select(Artifact)
        .where(
            Artifact.investigation_id.in_(accessible_ids),
            Artifact.normalized_value.ilike(term)
            | Artifact.raw_value.ilike(term)
            | Artifact.context.ilike(term)
            | Artifact.artifact_type.ilike(term),
        )
        .order_by(Artifact.id.desc())
        .limit(limit_per_category)
    )
    art_matches = db.execute(art_stmt).scalars().all()
    for art in art_matches:
        inv_title, inv_case = accessible_map.get(art.investigation_id, ("Investigation", ""))
        results.append(
            SearchResultItem(
                category="artifact",
                id=art.id,
                title=f"{art.artifact_type}: {art.normalized_value}",
                subtitle=f"{inv_case} · {art.context[:60]}",
                url=f"/investigations/{art.investigation_id}/analysis",
                investigation_id=art.investigation_id,
                investigation_title=inv_title,
            )
        )

    return SearchResponse(query=q, total=len(results), results=results)
