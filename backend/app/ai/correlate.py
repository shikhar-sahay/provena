"""Shared-value correlation over persisted-style artifact rows.

A correlation exists when the same (artifact_type, normalized_value) appears
in two or more distinct evidence items within one investigation. Correlation
is deterministic, investigation-scoped, and explains itself: every
correlation links back to its contributing artifacts, each of which links to
its evidence and source locator. No conclusions, scores, or hypotheses.
"""

from __future__ import annotations


def build_correlations(rows: list[tuple[int, int, str, str]]) -> list[dict]:
    """Group (artifact_id, evidence_id, artifact_type, normalized_value).

    Returns one entry per distinct (type, value) seen in 2+ evidence items:
    {"artifact_type", "normalized_value", "artifact_ids", "evidence_ids"}.
    Ordering is deterministic: sorted by (artifact_type, normalized_value).
    """
    groups: dict[tuple[str, str], dict[str, set[int]]] = {}
    for artifact_id, evidence_id, artifact_type, normalized_value in rows:
        key = (artifact_type, normalized_value)
        bucket = groups.setdefault(key, {"artifacts": set(), "evidence": set()})
        bucket["artifacts"].add(artifact_id)
        bucket["evidence"].add(evidence_id)
    correlations = []
    for (artifact_type, normalized_value) in sorted(groups):
        bucket = groups[(artifact_type, normalized_value)]
        if len(bucket["evidence"]) < 2:
            continue
        correlations.append(
            {
                "artifact_type": artifact_type,
                "normalized_value": normalized_value,
                "artifact_ids": sorted(bucket["artifacts"]),
                "evidence_ids": sorted(bucket["evidence"]),
            }
        )
    return correlations
