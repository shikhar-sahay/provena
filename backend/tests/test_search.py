"""Tests for global search functionality and RBAC isolation."""

from app.modules.evidence.models import Evidence
from app.modules.intelligence.models import Artifact, Finding
from app.modules.investigations.models import Investigation, InvestigationMember
from app.modules.users.models import Role
from tests.conftest import auth_headers, login, make_user


def test_search_short_query_returns_empty(client, investigator):
    token = login(client, investigator.username)
    res = client.get("/api/search?q=a", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_search_investigator_rbac_isolation(client, db_session, investigator):
    other_user = make_user(db_session, "other_inv", Role.INVESTIGATOR)

    # Inv 1: accessible to investigator
    inv1 = Investigation(
        case_number="CASE-2026-001",
        workspace_id=investigator.active_workspace_id,
        title="Project Helios Breach",
        description="Investigation into unauthorized access",
        status="open",
        created_by_id=investigator.id,
        lead_investigator_id=investigator.id,
    )
    # Inv 2: accessible only to other_user
    inv2 = Investigation(
        case_number="CASE-2026-002",
        workspace_id=other_user.active_workspace_id,
        title="Project Helios Financial Fraud",
        description="Confidential fraud probe",
        status="open",
        created_by_id=other_user.id,
        lead_investigator_id=other_user.id,
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()
    db_session.refresh(inv1)
    db_session.refresh(inv2)

    # Add memberships
    db_session.add(InvestigationMember(investigation_id=inv1.id, user_id=investigator.id, team_role="lead"))
    db_session.add(InvestigationMember(investigation_id=inv2.id, user_id=other_user.id, team_role="lead"))
    db_session.commit()

    token = login(client, investigator.username)
    res = client.get("/api/search?q=Helios", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    # Investigator should only see Inv 1, not Inv 2
    inv_ids = [r["id"] for r in data["results"] if r["category"] == "investigation"]
    assert inv1.id in inv_ids
    assert inv2.id not in inv_ids


def test_search_admin_sees_all(client, db_session, admin, investigator):
    inv = Investigation(
        case_number="CASE-2026-099",
        workspace_id=investigator.active_workspace_id,
        title="Admin Test Case Secret",
        description="Test case",
        status="open",
        created_by_id=investigator.id,
        lead_investigator_id=investigator.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    token = login(client, admin.username)
    res = client.get("/api/search?q=Secret", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    inv_ids = [r["id"] for r in data["results"] if r["category"] == "investigation"]
    assert inv.id in inv_ids


def test_search_returns_evidence_findings_artifacts(client, db_session, investigator):
    inv = Investigation(
        case_number="CASE-2026-010",
        workspace_id=investigator.active_workspace_id,
        title="Network Intrusion Probe",
        description="Test case",
        status="open",
        created_by_id=investigator.id,
        lead_investigator_id=investigator.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    db_session.add(InvestigationMember(investigation_id=inv.id, user_id=investigator.id, team_role="lead"))
    db_session.commit()

    evidence = Evidence(
        investigation_id=inv.id,
        evidence_number="EVD-001",
        title="Firewall Log Alpha",
        original_filename="firewall_alpha.log",
        storage_key="test-storage-key-1",
        content_type="text/plain",
        file_size=1024,
        sha256="abc123hash",
        integrity_status="verified",
        registered_by_id=investigator.id,
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)

    finding = Finding(
        investigation_id=inv.id,
        rule_id="RULE-EXFIL-001",
        title="Alpha Data Exfiltration Alert",
        summary="Suspicious outbound transfer detected",
        severity="high",
        status="pending_review",
        confidence=85,
        inputs_key="RULE-EXFIL-001:test-inputs",
    )
    db_session.add(finding)

    artifact = Artifact(
        investigation_id=inv.id,
        evidence_id=evidence.id,
        artifact_type="ip_address",
        raw_value="10.0.0.99",
        normalized_value="10.0.0.99",
        locator={"kind": "line", "line": 1},
        source_key="line:1",
        method="regex",
        extractor_name="regex",
        extractor_version="1.0",
        context="Alpha packet source",
    )
    db_session.add(artifact)
    db_session.commit()

    token = login(client, investigator.username)
    res = client.get("/api/search?q=Alpha", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    categories = {r["category"] for r in data["results"]}
    assert "evidence" in categories
    assert "finding" in categories
    assert "artifact" in categories
