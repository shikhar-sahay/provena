# Security and evidence controls

This document describes application behavior visible in the repository and the AWS deployment. Provena is not certified forensic software.

## Identity and authorization

### Workspace administration (M0)

`GET /api/admin/users` and `PATCH /api/admin/users/{id}` are scoped to the
administrator's current workspace. Their `role` and `is_active` fields describe
workspace membership, not the global account. The existing PATCH payload is
retained; setting `is_active=false` suspends access to this workspace only.
Sign-in and other authorized workspaces remain available. There is no supported
platform-superadministrator API; global account availability is not editable by
workspace administrators.

Suspended memberships remain visible in administration lists, but are excluded
from active team-selection lists. Restoration is an explicit administrator
action; an invitation cannot bypass suspension. Membership changes are audited.
The acting administrator cannot suspend their own membership. Role changes and
suspensions protect the last active administrator of the affected workspace,
counting active memberships of globally active users, rather than cached global
roles. Both operations lock the workspace row on PostgreSQL before checking.

Every case access requires active membership in an active workspace, the selected
workspace must match, and case-team or workspace-administrator permission must
also hold. Surviving case membership does not bypass suspension. These checks
cover evidence, downloads, analysis, findings, notes, reports, custody and audit.
An unavailable selected workspace is projected as absent in auth responses;
onboarding offers the user's remaining authorized workspaces. Existing browser
state may require a refresh after suspension; backend checks apply immediately.
No schema migration is needed because membership already stores `is_active`.

### Multipart dependencies and CI

`python-multipart>=0.0.27,<0.1` excludes versions affected by
[GHSA-pp6c-gr5w-3c5g](https://github.com/Kludex/python-multipart/security/advisories/GHSA-pp6c-gr5w-3c5g).
M0 tested python-multipart 0.0.33 with FastAPI 0.116.2 and Starlette 0.48.0;
M1 replaces those framework versions with the audited resolution below. Synthetic tests cover ordinary uploads, exact size limits,
oversized and empty files, missing boundaries, malformed headers, incomplete
parts and excessive part-header values. Rejected requests must not register
evidence or leave stored files.

CI runs `python -m pip_audit -r backend/requirements.txt` in a separate job.
It checks freshly resolved direct and transitive requirements against published
advisories; it does not attest to production's installed packages, unpublished
vulnerabilities, frontend packages or operating-system packages. Advisory service
and package-index access are required. Findings fail the job; no blanket ignore
or automatic production upgrade is configured. Backend requirements remain
bounded ranges, not an exact deployment lockfile.

M1 resolves the M0 dependency findings using a compatible FastAPI/Starlette
upgrade and pytest >=9.0.3. The tested clean resolution is FastAPI 0.149.0,
Starlette 1.10.0 and pytest 9.2.0; pip check and pip-audit pass without ignores.
The M0 scan reported pytest PYSEC-2026-1845 (fixed in 9.0.3), and Starlette
PYSEC-2026-1942 (0.49.1), PYSEC-2026-161 (1.0.1), PYSEC-2026-2281 and
PYSEC-2026-2280 (1.1.0), PYSEC-2026-248 (1.3.0), and PYSEC-2026-249 (1.3.1).
Repeated entries in run 29 were duplicates, not separate application exploits.
FastAPI's old <0.117 constraint capped Starlette below 0.49, so upgrading only
Starlette would have produced an incompatible environment. M1 lets the resolver
select compatible versions instead of forcing an installation. Advisory data
is available in [run 29](https://github.com/shikhar-sahay/provena/actions/runs/41858064380)
and the [Starlette security advisories](https://github.com/Kludex/starlette/security/advisories).

CI uses Node 24-compatible official checkout/setup actions, keeps Python 3.13
and Node 22 application runtimes, and explicitly runs frontend type checking.
An isolated PostgreSQL 16 service checks fresh migrations and schema drift.
Docker was unavailable locally. A standalone PostgreSQL 16.15 cluster in a
new temporary directory, bound only to loopback port 55477, verified the full
migration chain, `alembic check`, and parallel idempotent registration. It used
only a fresh synthetic database and was stopped afterward. The drift check
exposed legacy workspace metadata declaring unique indexes where the published
migration creates unique constraints plus ordinary indexes. Model declarations
now match that existing schema; published migrations were not rewritten.
SQLite tests alone still do not prove PostgreSQL concurrency safety.

Local migration backups are excluded by `/migration-backup/` in `.gitignore`.
Ignore rules do not protect already tracked files or deliberate force-adds.
Operators must still review the staged diff; backup contents are never test data.

Provena hashes passwords with bcrypt and issues signed JWT bearer tokens. Workspace membership establishes the first authorization boundary. Investigation membership and roles further restrict case access and actions. Administrators are scoped to their workspace. Backend checks enforce access to evidence, analysis, findings, reports, and downloads; frontend controls are only user-interface guidance.

The browser stores the token in `localStorage`. Page JavaScript can read it if script injection occurs. Keep dependencies current, review content security policy and Nginx headers, and consider HttpOnly cookies in a future authentication change. Never log tokens or place them in URLs. Production must use a strong unique `SECRET_KEY` and exact allowed origins.

## Evidence and provenance

Evidence registration streams bytes and records an immutable SHA-256 baseline. Later verification hashes stored bytes and records `verified`, `mismatch`, or `unavailable` with expected and observed digests. Unverified or failed evidence cannot enter analysis. Original filenames do not become storage paths; external API responses omit internal storage keys. Custody and audit records are append-only through the application API.

The current EC2 deployment uses local evidence files. Back up the directory with PostgreSQL and test restoration against recorded baselines. A separate S3 backend exists in code but is not selected by the live deployment. See [evidence integrity](evidence-integrity.md).

## AWS boundaries

The deployment uses a public-subnet EC2 instance, security groups, a scoped IAM instance role, private S3 buckets, and Systems Manager Session Manager. Verify that only intended web ports are public, while FastAPI port 8000 and PostgreSQL port 5432 stay local. An S3 gateway endpoint affects EC2-to-S3 routing only when associated with its route table. IAM and bucket policies should permit only the active operational backup or migration prefixes, with no embedded access keys.

PostgreSQL, evidence files, and the frontend share one EC2 failure domain. Confirm EBS encryption, filesystem permissions, backups, restore testing, disk alarms, log retention, and instance patching in the AWS account. The repository cannot attest that these operational checks have been completed.

## Transport security

The deployed domain uses a Let's Encrypt certificate with Nginx TLS termination. Port 80 redirects to HTTPS; DuckDNS IP updates and certificate renewal are configured, and a renewal dry run succeeded on October 19, 2026. The certificate expires January 17, 2027 unless renewed. The DuckDNS token is held in a root-protected file outside the repository. HTTPS protects transport but does not replace secret rotation, patching, backups, access review, or application security testing. Keep `CORS_ORIGINS` restricted to the exact production origin and verify uploads and downloads after web-server changes.

## Reporting and AI trust

The deterministic rule engine proposes findings with cited evidence, locators, factors, and recommendations. Human acceptance is required for reports. M2 excludes free-form model narration from authoritative reports even if legacy Ollama settings are enabled; deterministic assembly preserves accepted finding meaning. Neither a generated narrative nor a confidence score proves an allegation. Reports are immutable content-hashed snapshots, not cryptographic signatures.
