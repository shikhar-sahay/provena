"""Run a fresh HTTP acceptance workflow against a local Provena API.

This uses only public API endpoints and synthetic repository sample data. It
does not modify the database directly. Run from the repository root:

    python scripts/acceptance_e2e.py http://127.0.0.1:8001
"""

import json
import sys
import time
from pathlib import Path

import httpx


BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "E2E-pass-123"
STAMP = str(int(time.time()))


class Api:
    def __init__(self, token: str | None = None):
        self.client = httpx.Client(
            base_url=BASE,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=120,
        )

    def request(self, method: str, path: str, expected: int | tuple[int, ...] = 200, **kwargs):
        response = self.client.request(method, path, **kwargs)
        allowed = (expected,) if isinstance(expected, int) else expected
        if response.status_code not in allowed:
            raise AssertionError(f"{method} {path}: expected {allowed}, got {response.status_code}: {response.text}")
        if response.status_code == 204:
            return None
        return response.json()


def register(label: str) -> tuple[Api, dict]:
    username = f"e2e_{label}_{STAMP}"
    payload = {
        "username": username,
        "email": f"{username}@example.test",
        "full_name": f"E2E {label.title()}",
        "password": PASSWORD,
    }
    result = Api().request("POST", "/api/auth/register", expected=201, json=payload)
    return Api(result["access_token"]), result["user"]


def invite_and_join(owner: Api, label: str, role: str) -> tuple[Api, dict]:
    invite = owner.request(
        "POST", "/api/workspaces/current/invites", expected=201,
        json={"role": role, "expires_in_days": 7, "max_uses": 3},
    )
    account, user = register(label)
    joined = account.request("POST", "/api/workspaces/join", json={"code": invite["code"]})
    assert joined["role"] == role
    account.request("POST", "/api/workspaces/join", expected=409, json={"code": invite["code"]})
    return account, user


def upload(api: Api, investigation_id: int, filename: str, content: bytes) -> dict:
    return api.request(
        "POST", f"/api/investigations/{investigation_id}/evidence", expected=201,
        data={
            "title": f"Fresh E2E {filename}", "description": "Synthetic acceptance evidence.",
            "evidence_type": "log", "source": "Provena synthetic sample data",
        },
        files={"file": (filename, content, "text/plain")},
    )


def main() -> None:
    summary: dict = {"base_url": BASE, "stamp": STAMP}
    assert Api().request(
        "POST", "/api/auth/login", expected=401,
        json={"username_or_email": f"missing_{STAMP}", "password": "wrong-password"},
    )["detail"] == "Invalid credentials."

    owner, owner_user = register("owner")
    duplicate_payload = {
        "username": owner_user["username"], "email": f"other_{STAMP}@example.test",
        "full_name": "Duplicate", "password": PASSWORD,
    }
    Api().request("POST", "/api/auth/register", expected=409, json=duplicate_payload)
    workspace = owner.request("POST", "/api/workspaces", expected=201, json={"name": f"Fresh E2E Lab {STAMP}"})
    owner.request("POST", "/api/workspaces/join", expected=400, json={"code": "PRV-invalid-code"})

    investigator, investigator_user = invite_and_join(owner, "investigator", "investigator")
    analyst, analyst_user = invite_and_join(owner, "analyst", "forensic_analyst")
    custodian, custodian_user = invite_and_join(owner, "custodian", "evidence_custodian")

    investigation = owner.request(
        "POST", "/api/investigations", expected=201,
        json={
            "title": f"Fresh Suspected Internal Data Exfiltration {STAMP}",
            "description": "Synthetic fresh acceptance scenario.",
            "priority": "high", "lead_investigator_id": investigator_user["id"],
        },
    )
    inv_id = investigation["id"]
    for user in (analyst_user, custodian_user):
        owner.request("POST", f"/api/investigations/{inv_id}/members", json={"user_id": user["id"]})

    outsider, _ = register("outsider")
    outsider.request("POST", "/api/workspaces", expected=201, json={"name": f"Isolated Lab {STAMP}"})
    outsider.request("GET", f"/api/investigations/{inv_id}", expected=404)
    assert outsider.request("GET", "/api/search?q=Fresh")["total"] == 0
    assert outsider.request("GET", "/api/findings") == []

    empty = custodian.client.post(
        f"/api/investigations/{inv_id}/evidence",
        data={"title": "Empty", "evidence_type": "log"},
        files={"file": ("empty.log", b"", "text/plain")},
    )
    assert empty.status_code == 422, empty.text

    sample_names = ["authentication.log", "usb_activity.log", "file_access.log", "network_activity.log"]
    evidence = [
        upload(custodian, inv_id, name, (ROOT / "sample-data" / name).read_bytes())
        for name in sample_names
    ]

    blocked = analyst.request(
        "POST", f"/api/investigations/{inv_id}/analysis/runs", expected=201,
        json={"evidence_ids": [evidence[0]["id"]]},
    )
    assert blocked["evidence_outcomes"][0]["status"] == "blocked_not_verified"

    for item in evidence:
        result = custodian.request("POST", f"/api/investigations/{inv_id}/evidence/{item['id']}/verify")
        assert result["result"] == "verified"
    custodian.request(
        "POST", f"/api/investigations/{inv_id}/evidence/{evidence[0]['id']}/custody", expected=201,
        json={"action": "transferred", "to_user_id": custodian_user["id"], "notes": "Fresh E2E custody handoff."},
    )

    run = analyst.request(
        "POST", f"/api/investigations/{inv_id}/analysis/runs", expected=201,
        json={"evidence_ids": [item["id"] for item in evidence]},
    )
    assert run["status"] == "completed"
    artifacts = analyst.request("GET", f"/api/investigations/{inv_id}/analysis/artifacts?limit=200")
    correlations = analyst.request("GET", f"/api/investigations/{inv_id}/analysis/correlations")
    assert artifacts["total"] > 0 and correlations
    first_artifact = analyst.request("GET", f"/api/investigations/{inv_id}/analysis/artifacts/{artifacts['items'][0]['id']}")
    assert first_artifact["locator"] and first_artifact["context"]

    generated = analyst.request("POST", f"/api/investigations/{inv_id}/analysis/findings/generate")
    findings = generated["findings"]
    assert len(findings) >= 2
    accepted = investigator.request(
        "POST", f"/api/investigations/{inv_id}/analysis/findings/{findings[0]['id']}/review",
        json={"status": "accepted", "note": "Accepted after provenance and factor review."},
    )
    rejected = investigator.request(
        "POST", f"/api/investigations/{inv_id}/analysis/findings/{findings[1]['id']}/review",
        json={"status": "rejected", "note": "Rejected because additional human context is required."},
    )
    investigator.request(
        "POST", f"/api/investigations/{inv_id}/analysis/notes", expected=201,
        json={"body": "Fresh acceptance note grounded in the reviewed provenance.", "finding_id": accepted["id"]},
    )

    report = investigator.request("POST", f"/api/investigations/{inv_id}/analysis/reports", expected=201)
    content = report["content"]
    assert [item["id"] for item in content["accepted_findings"]] == [accepted["id"]]
    assert rejected["id"] not in content["narrative"]["used_finding_ids"]
    assert len(report["content_sha256"]) == 64

    for status in ("in_progress", "under_review", "closed"):
        investigator.request("PATCH", f"/api/investigations/{inv_id}", json={"status": status})
    owner.request("PATCH", f"/api/investigations/{inv_id}", json={"status": "archived"})
    investigator.request("PATCH", f"/api/investigations/{inv_id}", expected=403, json={"title": "Blocked archived edit"})
    audit = investigator.request("GET", f"/api/investigations/{inv_id}/audit")
    assert len(audit) >= 10
    assert not any("Synthetic acceptance evidence" in json.dumps(item.get("event_metadata")) for item in audit)

    summary.update({
        "workspace_id": workspace["id"], "investigation_id": inv_id,
        "case_number": investigation["case_number"], "evidence_count": len(evidence),
        "artifact_count": artifacts["total"], "correlation_count": len(correlations),
        "finding_count": len(findings), "accepted_finding_id": accepted["id"],
        "rejected_finding_id": rejected["id"], "report_id": report["id"],
        "report_sha256": report["content_sha256"],
        "narrative_mode": content["generation_metadata"]["mode"],
        "narrative_provider": content["generation_metadata"]["provider"],
        "narrative_model": content["generation_metadata"]["model"],
        "audit_events": len(audit), "workspace_isolation": "passed",
        "archived_read_only": "passed",
    })
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
