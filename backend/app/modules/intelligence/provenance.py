"""Stable analytical support identities and current-run selection."""
import hashlib
import json
from sqlalchemy import select, func
from app.ai import extractors, parsers
from app.modules.evidence.models import Evidence
from app.modules.intelligence.models import AnalysisRun, AnalysisRunEvidence, AnalysisRunArtifact, Artifact


def semantic_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def artifact_identity(artifact: Artifact) -> str:
    return semantic_hash({'evidence_id': artifact.evidence_id, 'input_sha256': artifact.input_sha256,
        'type': artifact.artifact_type, 'value': artifact.normalized_value,
        'source_key': artifact.source_key, 'extractor': artifact.extractor_name,
        'version': artifact.extractor_version})


def active_artifacts(db, investigation_id: int) -> list[Artifact]:
    """Only artifacts actually emitted by each item's latest completed parse.

    Historical artifacts stay resolvable. A newer rejected/blocked attempt does
    not silently reactivate an older parse. Running outcomes are visible only
    to the transaction constructing them under the investigation row lock.
    """
    from app.modules.intelligence.service import PIPELINE_VERSION
    latest = select(func.max(AnalysisRunEvidence.id)).join(AnalysisRun).where(
        AnalysisRun.investigation_id == investigation_id,
        AnalysisRun.pipeline_version == PIPELINE_VERSION,
        AnalysisRun.status.in_(['running', 'completed']),
    ).group_by(AnalysisRunEvidence.evidence_id)
    return list(db.execute(select(Artifact).join(Evidence, Evidence.id == Artifact.evidence_id)
        .join(AnalysisRunArtifact, AnalysisRunArtifact.artifact_id == Artifact.id)
        .join(AnalysisRunEvidence, (AnalysisRunEvidence.run_id == AnalysisRunArtifact.run_id)
              & (AnalysisRunEvidence.evidence_id == Artifact.evidence_id))
        .where(AnalysisRunEvidence.id.in_(latest), AnalysisRunEvidence.status.in_(['processed', 'partial']),
            Artifact.investigation_id == investigation_id,
            Artifact.extractor_version == f'{extractors.EXTRACTOR_VERSION}.p{parsers.PARSER_VERSION}',
            Evidence.registration_status == 'ready', Evidence.integrity_status == 'verified',
            Artifact.input_sha256 == Evidence.sha256)
        .order_by(Artifact.id)).scalars().unique())


def coverage_for_artifacts(db, artifacts) -> dict[int, dict]:
    evidence_ids = {a.evidence_id for a in artifacts}
    return {row.evidence_id: row.coverage or {'status': 'unknown'} for row in db.execute(
        select(AnalysisRunEvidence).where(AnalysisRunEvidence.evidence_id.in_(evidence_ids))
        .order_by(AnalysisRunEvidence.id)).scalars()}
