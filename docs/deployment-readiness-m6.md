# M6 production deployment readiness and gated upgrade runbook

Assessment date: 2026-11-06 (India). Target application source:
`b9ad5c50421337b8b1364a13e407cca00fd2c75d`, version `0.1.0-beta.0`, schema
`ee5b99eb5ce4`. [CI #60](https://github.com/shikhar-sahay/provena/actions/runs/42106948839)
passed all eight jobs on that exact commit. The final inventory below identifies the
production checkout and the pinned CI #61 deployment candidate. The newer preparation
commit is a handoff/tooling revision, not an instruction to deploy moving main.

## 1. Decision and assessment boundary

**NO-GO for deployment now.** Live inventory and the six-migration path are established;
production-consistent backup, real-baseline restore, capacity/configuration acceptance
and owner authorization remain open. See section 13 and the
[execution checklist](deployment-execution-checklist.md). A working login is not
migration proof. This document prepares an upgrade; it does not authorize execution.

The initial pass used only public HTTPS. The continuation used an owner-opened authorized
SSM session for bounded read-only metadata queries and AWS Console inventory. Nonsecret
configuration fields were projected through an explicit allowlist; credentials, signing
secrets and investigation contents were not returned. No original evidence bytes or
backup contents were read. No production backup, migration, file/configuration change,
service restart, certificate renewal or infrastructure mutation was performed. Browser
automation later stopped because its safety check could not determine the current URL;
that blocked navigation was not retried. The session was not terminated.

Evidence labels used below: **R** repository-verified; **P** public observation;
**H** historical team documentation; **U** unknown; **D** disposable validation;
**L** authorized live metadata observed in the continuation.

## 2. Current-state evidence

Public observations at approximately **2026-11-05 23:49 UTC** (2026-11-06 IST), using
normal certificate/hostname validation and bounded response reads:

| Item | Observation and limit |
| --- | --- |
| P: `/login` | HTTPS 200, HTML, `Server: nginx/1.30.5`; no Cache-Control header observed on this response |
| P: `/api/health` | HTTPS 200, JSON with `status=ok`, `db=ok`; no Cache-Control header observed |
| P: `/api/live`, `/api/ready` | Both HTTPS 404, JSON content type; no authenticated probes attempted |
| P: TLS | TLS 1.3 handshake passed hostname/CA validation; leaf validity October 19, 2026 04:52:29 GMT to January 17, 2027 04:52:28 GMT |
| L: checkout/schema | Continuation established checkout 9024ccd55c89c84876aeb5d7ea3b352f108fb5c1 and schema 9b6e5c4d3a21; public responses alone did not establish them |

The deployed source's health module defines only /health. Its old implementation explains
the missing M6 routes; inspected Nginx preserves /api/. A source checkout is not a signed
runtime attestation. Nginx 1.30.5 was also confirmed on the host, rather than inferred
only from a header. TLS success does not establish renewal, origin isolation or IAM.
The web browsing connector could not retrieve the site; direct bounded Python HTTPS
requests succeeded. No availability incident is inferred from the connector failure.

[Historical AWS notes](aws-deployment.md) and the
[team guide](AWS_ARCHITECTURE_AND_DEPLOYMENT_GUIDE.md) describe October 19, 2026:
Amazon Linux 2023, a t3.micro, 20 GB root EBS, 2 GB swap, Mumbai, Session Manager,
Nginx, `provena.service` on loopback 8000, local PostgreSQL 16 and local evidence.
They also describe three S3 buckets, a gateway endpoint, DuckDNS timer and Certbot.
**These records remain H; section 13 independently verifies selected current facts.**
Amazon Linux 2023.12, rather than Ubuntu, is now confirmed. Do not use Ubuntu package
commands on this host.
S3 resource existence would not prove S3-backed evidence or actual backup retention.

## 3. Repository architecture and path inventory

| Concern | R: implementation | H/U: live value to resolve |
| --- | --- | --- |
| API | `backend/app/main.py`, modular monolith; no automatic startup migrations | L: provena.service, ssm-user, existing backend working directory and .venv/bin/python; record resolved paths privately before execution |
| Startup | `uvicorn app.main:app`; retain one worker for the proposed deployment | L: Python 3.13.15 and loopback 8000; do not substitute historical example paths |
| Frontend | React 19, Vite 8, TypeScript 6; locked npm graph; `frontend/dist` output | L: static document root and index digest verified; private document-root path withheld here; cache directives still require rollout smoke tests |
| API origin | `frontend/src/api/client.ts` uses same-origin when VITE_API_URL is unset | Preserve `/api/` prefix in proxy; do not use an E2E build with ephemeral API port |
| Database | SQLAlchemy 2, Alembic; PostgreSQL/psycopg2 tested | L: PostgreSQL 16.15, database provena, schema 9b6e5c4d3a21; DB directory and secret/grant recovery still private operator responsibilities |
| Originals | `backend/app/modules/evidence/storage.py`, generated keys | L: local root outside checkout, owned by service user, mode 700; do not commit its actual path or move it during checkout |
| Exports | `backend/app/modules/exports/artifacts.py`, separate private root | L: old backend default cache directory absent; explicitly approve a new absolute, separate, non-nested root |
| Reports | Immutable JSON and content hashes in PostgreSQL | No independent report directory is required by current code; preserve legacy extra files if any |
| Temporary copies | Verified snapshots use Python TemporaryFile; export builders use private cache subdirectories | Service TMPDIR/filesystem capacity and access policy unknown |
| Logs | Safe structured request logs and correlation IDs; preparation duration only | systemd/journal/Nginx rotation, retention and disk alerts unknown |
| Diagnostics | `/api/live`, `/api/ready`, legacy `/api/health`; `app.ops.preflight` CLI | Current 404s must be resolved in the future upgrade |
| Deployment assets | Tracked Dockerfile and Compose are local-development validation | No tracked live Nginx site, systemd unit, EC2 bootstrap or CD; local Compose auto-migrates and is not production configuration |

Use operator-resolved variables rather than these historical example paths:
`OLD_RELEASE`, `NEW_RELEASE`, `OLD_PYTHON`, `NEW_PYTHON`, `API_SERVICE`,
`SERVICE_USER`, `ENV_FILE`, `FRONTEND_ROOT`, `EVIDENCE_ROOT`, `EXPORTS_ROOT`,
`PRIVATE_BACKUP_PARENT`, `PG_BIN`, and private named PostgreSQL connection services.
All must be recorded in an access-controlled change record, never committed with secrets.
Do not place mutable evidence, cache or configuration inside versioned release roots.

## 4. Deferred read-only inspection checklist

Section 13 supersedes the earlier unknown baseline. Recheck changed facts and fill the
remaining U fields, rather than repeating completed inspection. Run only against
the positively identified host, with existing authorized access. Commands below are
inspection templates, **not commands executed in this assessment**. Never paste raw
environment, process command lines, Nginx configuration or journals into this repository.

```sh
# Replace every placeholder first. Do not run a discovery scan or seek credentials.
date -u
cat /etc/os-release
uname -m
git -C "$OLD_RELEASE" rev-parse HEAD
git -C "$OLD_RELEASE" status --short
"$OLD_PYTHON" --version
"$OLD_PYTHON" -m pip check
systemctl show "$API_SERVICE" --property=FragmentPath,DropInPaths,User,Group,WorkingDirectory,MainPID,ActiveState,SubState,EnvironmentFiles
systemctl list-timers --all --no-pager
ss -lnt
df -hT
df -i
free -h
vmstat 1 5
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
stat -c '%U %G %a %n' "$EVIDENCE_ROOT" "$EXPORTS_ROOT"
"$PG_BIN/pg_dump" --version
"$PG_BIN/pg_restore" --version
```

If an export root does not yet exist, record that fact; do not create it during inspection.
Inspect service ExecStart and proxy configuration privately, extracting only sanitized
bind/worker/path/timeout/header/cache settings. Avoid `systemctl show Environment`,
`ps e`, raw `nginx -T`, broad environment dumps or reading secret files into task output.
Review renewal/timer outcomes privately without triggering renewals or DuckDNS updates.

Use a preconfigured protected read-only PostgreSQL service, not a password in a command:

```sh
PGSERVICE=APPROVED_READONLY_SERVICE \
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=2000' \
psql -X -v ON_ERROR_STOP=1 -c "SELECT current_setting('server_version'), pg_database_size(current_database()); SELECT version_num FROM alembic_version;"
```

Missing/multiple Alembic revisions, local migration edits, an unknown revision or a
schema created outside Alembic are hard stops. Do not fix them by stamping head.
The operator must also privately inventory service account access, actual roots and
free bytes on DB/WAL, temp, evidence, exports and backup filesystems. Aggregate usage
may be measured later with separately approved metadata-only traversal; no original
bytes are needed for this assessment.

Authorized AWS Console read-only inspection must confirm instance/AMI/type, EBS size,
encryption and DeleteOnTermination, security groups, local-only DB/API listeners,
SSM/IAM access, existing backup objects/retention and snapshot policies. Do not launch
resources, create snapshots, read private S3 objects or query instance credentials.
Record capacities and mechanisms without account identifiers or tokens. No AWS charges
were created or account-side backup/encryption guarantees verified here.

## 5. Compatibility and configuration gates

R: CI/Docker use Python 3.13, Node 22 and PostgreSQL 16. Other versions are not certified
by that result. Keep one API worker initially; measure before increasing concurrency.
Node/Chromium are build/test tools, not runtime dependencies for Nginx static serving.
Build off the small host where practical; do not replace a live venv in place.

`backend/requirements.txt` currently permits FastAPI >=0.140,<0.150; Starlette >=1.3.1,<2;
SQLAlchemy >=2.0,<2.1; Alembic >=1.13,<2; Uvicorn >=0.30,<0.35; psycopg2-binary >=2.9,<3;
Pydantic >=2.7,<3; multipart >=0.0.27,<0.1; pypdf >=6.21.4,<7. These differ substantially
from possible older installs. Do not force new Starlette into an old FastAPI environment.
Create a new environment, resolve together, run pip check/audit and record the resolved
inventory and artifact hashes. Backend ranges are not a lockfile; source SHA alone does
not reproduce the installed graph. Frontend uses npm ci with its committed lockfile.
Use `postgresql+psycopg2://` for the installed driver; a validator accepting a psycopg3
URL does not install psycopg3. No runtime package upgrade was executed on production.

| Setting/check | Required preparation |
| --- | --- |
| APP_ENV | Explicit production, never inherited development default |
| DATABASE_URL | Correct private PostgreSQL target, installed driver, dedicated role; migration owner privileges separately reviewed |
| SECRET_KEY | Random, >=32 characters and varied; protect outside Git; preserve intentionally or rotate with explicit session invalidation plan |
| ACCESS_TOKEN_EXPIRE_MINUTES | 1-1440; default 480; confirm acceptable lifetime |
| CORS_ORIGINS | Exact HTTPS origin without path, wildcard or credentials; same-origin builds need no additional origin; remove localhost default |
| TRUSTED_PROXY_IPS | Explicit actual loopback/proxy IPs or narrow CIDRs; no wildcard/all-address trust; review Uvicorn forwarding settings too |
| EVIDENCE_STORAGE_BACKEND/ROOT | Preserve actual local root and opaque keys; absolute paths prevent WorkingDirectory changes redirecting evidence |
| EXPORT_STORAGE_ROOT | Private separate/non-nested absolute root outside web/release tree, service read/write/execute access |
| Upload/export limits | Upload default 100 MiB, export default 512 MiB, metadata 32 MiB, retention 24 h; configurable bounds in config.py |
| TMPDIR | Private supported temp filesystem with sufficient snapshot space; externally supplied process environment, not an application setting |
| BUILD_ID | Exact deploy source SHA (up to 80 permitted characters), visible through private CLI diagnostics |
| LLM_ENABLED | False; no model dependency required for authoritative reports |
| Restore marker | No RESTORE_INCOMPLETE marker on the selected active local storage root |

R: production settings reject weak/placeholding secrets, non-PostgreSQL URLs, wildcard
origins/proxies and nested roots. They do not prove real TLS, disk headroom, a valid DB
password, service ownership, writable files or a correct proxy. Preflight examines the
nearest existing directory, so success does not prove the intended root already exists.
Do not indiscriminately chown existing evidence or expose its directory under Nginx.
An application backup omits configuration secrets, PostgreSQL roles/ACLs, systemd,
Nginx, certificates and DuckDNS credentials; preserve those through separate approved
encrypted operator records, not public exports.

Nginx review: same-origin production build, SPA fallback only for non-API paths,
`proxy_pass http://127.0.0.1:8000` preserving `/api/`, Authorization forwarding,
sanitized forwarding headers and actual HTTPS termination. Do not cache authenticated
API responses. Review no-store headers, index.html revalidation and hashed-asset caching;
retain old hashed assets during cutover if old browser sessions still reference them.
Body limits need multipart overhead beyond EVIDENCE_MAX_UPLOAD_BYTES. Set measured
synchronous request/download timeouts; do not treat a timed-out request as rollback.
Inspect proxy buffering/temp directories, download integrity and stale browser caches.
Do not expose ports 8000 or 5432 publicly. No Nginx/TLS setting was changed here.

## 6. Complete migration review

R: one linear chain, eleven revisions. Apply only the suffix after the verified source
revision. M6 itself adds no migration. Full source is in `backend/alembic/versions/`.
The confirmed source is already 9b6e5c4d3a21: only the final six rows below apply.
The workspace backfill is not pending and must not be repeated or reseeded. All five
source-era migration files match the target history byte-for-byte in Git.

| Revision, predecessor | Upgrade behavior and populated-data risk |
| --- | --- |
| c1de33e96662, base | Creates users, cases, membership and audit; unique username/email/case number; existing unmanaged tables conflict |
| e1dfb83d651b, c1de33e96662 | Evidence, verification and custody tables; unique storage keys/case evidence numbers and FKs |
| 4bd235c589d2, e1dfb83d651b | Analysis runs/artifacts/correlations and memberships; unique artifact/run/correlation identities |
| 000a8976b7f1, 4bd235c589d2 | Findings, notes, immutable reports; unique case report number and finding input identity |
| 9b6e5c4d3a21, 000a8976b7f1 | Creates workspace tables, copies existing users/roles into one demo workspace, assigns existing cases, makes workspace_id NOT NULL; owner must approve this legacy isolation interpretation; scans/updates users/cases and adds FKs/indexes |
| b72a1e84c903, 9b6e5c4d3a21 | Adds ready default and registration key uniqueness; adds verification purpose and nullable input digest/verification links; ready default does not verify old bytes |
| c83d2f95a014, b72a1e84c903 | Nullable parser coverage; historical completeness is not invented |
| d94e30a6b125, c83d2f95a014 | Adds run/artifact memberships, nullable semantic/support snapshots and false current flag; replaces old correlation unique constraint; no historical supports/approvals inferred |
| 294d21d0205e, d94e30a6b125 | Immutable source profiles, ingestion/events/run membership; composite indexes and semantic uniqueness; no events fabricated for old evidence |
| 53d6b8a0e88b, 294d21d0205e | Explicit event sets/members, detection runs/finding membership; FKs and stable set uniqueness |
| ee5b99eb5ce4, 53d6b8a0e88b | Durable exports with case/actor/request-key uniqueness and case index |

ALTER TABLE, FK/unique validation and ordinary index creation can take strong locks,
scan populated tables and block writers. There is no concurrent-index migration or
batched live backfill. Workspace reassignment is data-changing, not a harmless table
addition. Invalid pre-existing FKs, unexpected nulls, unmanaged constraints, invalid role
data or long transactions can fail migration. Recent constant-default optimizations
do not eliminate locks or all validation work. See PostgreSQL's
[ALTER TABLE reference](https://www.postgresql.org/docs/16/sql-altertable.html).

Use a maintenance window with every application/CLI writer, pruning and schema task
fenced. Nginx maintenance alone does not fence localhost/API workers. Configure reviewed
PGOPTIONS lock_timeout and statement_timeout based on rehearsal, and abort on failure;
do not increase timeouts blindly or stamp a partial schema. Current Alembic uses
PostgreSQL transactional DDL, but inspect actual revision/schema after failure rather
than assuming rollback. M1 and later downgrades explicitly refuse destructive reversal.
Old code is **not proven compatible** with the new schema and must never run concurrently
against it. Nullable historical fields/retained tables are not backward-write guarantees.
Rollback after migration is fresh-target recovery, not an old-code symlink alone.

R/D: migrations retain report content/hashes and decisions, leave old missing support
metadata null and do not silently turn old analyses into current verified findings.
Expect historical support warnings. Reprocess only by explicit analyst action; never
rewrite baselines or approvals to make the migration appear successful.

## 7. Backup strategy: select by actual source schema

**Critical gate:** `app.ops.recovery.backup` rejects any revision other than its own
expected head. Its SQL requires M1 evidence lifecycle and M5 export tables. Current
restore also requires a manifest matching the application's expected revision. Do not
run the M6 tool on a pre-M5 production DB or migrate first merely to enable backup.
Do not pass a native dump to the Provena backup verifier and expect that schema.

### A. Source already at ee5b99eb5ce4

Use matching code, local storage configuration and matching native PostgreSQL utilities.
Fence writers for the upgrade's rollback boundary even though the tool uses an exported
REPEATABLE READ snapshot for pg_dump, row fingerprints and inventory. Pause pruning,
migrations and external evidence writers throughout. Every original is copied from an
exact snapshot and checked against its baseline; completed cache ZIPs are hash checked,
including completed records whose files are missing. Resolve incomplete registrations,
integrity failures or missing caches safely before the approved backup; do not delete
history or run cleanup as part of this assessment. Running operations remain running in
the snapshot and need explicit recovery after restoration. Reports are DB content.

Future authorized commands from the matching release's backend directory:

```sh
# SOURCE_DATABASE_URL is already loaded privately; never print it or enable set -x.
"$NEW_PYTHON" -m app.ops.recovery backup --database-url-env SOURCE_DATABASE_URL --confirm-database "$SOURCE_DB_NAME" --pg-bin "$PG_BIN" --acknowledge-sensitive-backup --output "$NEW_BACKUP_PATH"
"$NEW_PYTHON" -m app.ops.archive --kind backup "$NEW_BACKUP_PATH"
```

Tool limits: 4 GiB package, 10000 files and 2 million fingerprinted rows, with a 2 MiB
manifest budget; exceeding a budget fails rather than truncates. Evidence/cache inventory
and database dump share the package budget. Do not raise limits without testing.
Protect plaintext staging and output, encrypt using an approved operator mechanism,
verify ciphertext and decryption, copy encrypted bytes to an existing approved off-host
destination, and retain an independently trusted package SHA-256 and decryption method.
Neither encryption, off-host copy nor scheduling is implemented by this tool.

### B. Source older than ee5b99eb5ce4 or schema not yet verified

Unknown revision means stop. For a recognized legacy revision, prepare a **separately
reviewed native legacy backup/restore procedure** before upgrade authorization. Its
consistency boundary is total application/external-writer quiescence, not independent
live directory copies. Preserve the old code/venv dependency inventory and private
configuration as well as database and complete original storage tree with keys/metadata.
Include any old generated persistent files/cache if present; inspect actual old code.
Record source revision, file inventory, sizes/digests and report-hash verification in
a protected sidecar. Hashes and signing secrets are different controls.

Native command templates, only after fencing all writers and approving fresh private
destinations, using a protected libpq service for the confirmed source database:

```sh
umask 077
# PRIVATE_BACKUP_PARENT exists outside Git/web/evidence roots; this creates a fresh directory.
LEGACY_BACKUP=$(mktemp -d "$PRIVATE_BACKUP_PARENT/provena-upgrade.XXXXXXXX")
PGSERVICE=APPROVED_SOURCE_SERVICE "$PG_BIN/pg_dump" --format=custom --no-owner --no-acl --file="$LEGACY_BACKUP/database.dump"
"$PG_BIN/pg_restore" --list "$LEGACY_BACKUP/database.dump" > "$LEGACY_BACKUP/database.toc"
tar --create --file="$LEGACY_BACKUP/evidence.tar" --directory="$EVIDENCE_ROOT" .
# Also archive a separate legacy export/generated root if it exists and is required.
sha256sum "$LEGACY_BACKUP/database.dump" "$LEGACY_BACKUP/evidence.tar" > "$LEGACY_BACKUP/SHA256SUMS"
```

Run commands with fail-on-error handling and check every exit status. These are gated
templates, not an automated legacy backup validator. Listing a dump/hash of a tar is
not a restore drill or proof it contains every DB-referenced original. The authorized
operator must reconcile a privately held DB key/digest inventory with the copy, verify
report hashes, and check archive paths/symlinks before trusted fresh-target extraction.
Do not follow evidence symlinks outside its root or omit hidden pending files blindly.
Use a dedicated encrypted operator bundle for secrets, roles/grants and system settings.
The no-owner/no-acl dump intentionally does not recreate them. If privileges, free space,
consistent copying or this validation cannot be established, **abort the upgrade**.

PostgreSQL [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html) gives a consistent
single-database snapshot, not cross-filesystem atomicity or roles/tablespaces backup.
Trusted SQL restoration executes database definitions; never restore an untrusted dump.
No legacy production backup, evidence inventory or real data restore was performed here.

## 8. Gated deployment runbook, future authorization only

These phases are sequential. Fill the path/identity worksheet and sign each gate.
Shell snippets are Linux templates; stop on any error. Do not execute them in the
current assessment or copy unresolved uppercase placeholders into a terminal.

### Gate 0: authorization and baseline

1. Obtain explicit deployment, migration, private backup access, downtime and rollback
   authorization. Name change owner, database operator, reviewer and abort decision maker.
2. Complete section 4, identify exact old commit/schema, compare installed migrations
   with target history, and record sanitized configuration and service/root ownership.
3. Agree RPO, downtime/RTO and maximum wait/lock times from rehearsal. There is no
   measured production RTO/RPO or downtime estimate in this assessment.
4. Confirm privately recoverable old artifacts, encrypted off-host backup, secret/role
   recovery and sufficient space. An EBS volume or S3 bucket is not a verified backup.
5. Rehearse restore at the actual old revision in an isolated private environment, then
   forward migration and all smoke tests with no public traffic. Real backup access or
   transport needs separate authorization; synthetic rehearsals do not replace it.

### Gate 1: prepare independently of the running checkout

1. Choose exact approved target SHA; M6 app code is b9ad5c5. Verify final CI head_sha,
   candidate whole digest from a trusted source and per-file manifest. Candidates are
   unsigned, validation-only; never treat publishable=false as release approval.
2. On an isolated build host, use a clean committed checkout and Node 22 npm ci/build
   with VITE_API_URL unset. Run pip check/audit in a separate Python 3.13 environment.
   Keep resolved dependencies, source and frontend assets together. Never install into
   the live venv, run git pull there or build on a memory-starved host during cutover.
3. Stage the reviewed release into a new non-overwriting release directory through the
   approved transfer mechanism. Preserve old release/venv/assets. Do not extract an
   untrusted archive as root or overwrite evidence/configuration through archive paths.
4. Privately prepare production environment and export/temp capacity. Preserve original
   evidence keys/root. A fresh export root must not conceal existing required cache files.
5. Review actual systemd and Nginx changes in advance, including service user, working
   directory, absolute paths, one worker, environment file, proxy/timeouts/caches and TLS.
   No live edit or service reload occurs until the separately authorized window.
6. In NEW_RELEASE/backend with privately loaded proposed settings:

```sh
"$NEW_PYTHON" -m app.ops.preflight
```

Configuration-only preflight does not contact the DB. Against the old schema, full
M6 readiness is expected to fail until migration; do not bypass the schema check.

### Gate 2: maintenance, consistent final backup and forward migration

1. Start the approved maintenance window. Isolate browser/API traffic and stop/fence
   every writer, operator task and pruning timer. A UI banner alone is insufficient.
   Record active operations and resolve ambiguous completion before proceeding.

```sh
# This changes production state: execute only under the future signed change approval.
sudo systemctl stop "$API_SERVICE"
if systemctl is-active --quiet "$API_SERVICE"; then
    printf '%s\n' 'Abort: the API service is still active.'
    exit 1
fi
```

2. Prove writer exclusion operationally, make the final section 7 backup with the correct
   legacy/current branch, verify/encrypt/off-host it and confirm the rehearsed recovery
   remains feasible. Keep the old DB/storage untouched except the approved migration.
3. Set reviewed migration connection/lock timeouts. From NEW_RELEASE/backend, privately
   load the confirmed target DB configuration. Do not allow old workers to restart.

```sh
"$NEW_PYTHON" -m alembic current
"$NEW_PYTHON" -m alembic upgrade head
"$NEW_PYTHON" -m alembic current
"$NEW_PYTHON" -m alembic check
"$NEW_PYTHON" -m app.ops.preflight --database --storage
```

4. Require sole head ee5b99eb5ce4, no drift, ready configuration/database/storage and
   retained report hashes/decisions/digests. Abort on any failure; no downgrade or stamp.
   Do not initialize new source profiles, events or detections for historical evidence.

### Gate 3: start privately, validate, then admit traffic

1. Apply only reviewed unit/release/frontend changes through the approved change method.
   If the unit changed, daemon-reload is an explicitly authorized operation, not a
   read-only inspection. Confirm it references the new venv/release and retained roots.
2. Start only the intended API service while public writers remain isolated:

```sh
sudo systemctl start "$API_SERVICE"
systemctl is-active "$API_SERVICE"
curl --fail --silent --show-error http://127.0.0.1:8000/api/live
curl --fail --silent --show-error http://127.0.0.1:8000/api/ready
```

3. Validate JSON meaning, not just HTTP 200. Privately run preflight to check BUILD_ID;
   public version 0.1.0-beta.0 does not identify the exact SHA. Check sanitized errors,
   OOM/swap/disk pressure and schema state. Optional Ollama must not affect readiness.
4. If approved Nginx changes are needed, validate then reload, never restart blindly:

```sh
sudo nginx -t
sudo systemctl reload nginx
curl --fail --silent --show-error https://provena-app.duckdns.org/api/live
curl --fail --silent --show-error https://provena-app.duckdns.org/api/ready
```

5. Complete section 10 with a dedicated synthetic workspace through HTTPS before lifting
   the writer fence. No production credentials in shell history or committed screenshots.
6. Return traffic only after reviewer acceptance; observe agreed health/error/latency and
   disk thresholds. Keep rollback resources/old assets until the signed observation period
   ends. Configure approved retention/alerts separately; no scheduler was installed here.

## 9. Rollback and fresh-target recovery

| Abort point | Required response |
| --- | --- |
| Backup incomplete, unverifiable, unencrypted/off-host copy unavailable, insufficient disk or restore drill missing | Do not migrate; keep/return the unchanged old stack only after confirming its safe state |
| Unknown revision, drift, failed configuration or incompatible native utilities | Stop before mutation and investigate privately |
| Migration error/timeout | Keep writers fenced; inspect actual revision/schema; preserve diagnostics; use verified old-state recovery if not demonstrably unchanged |
| Startup/readiness/proxy failure | Keep traffic isolated; correct only within the approved time budget or recover compatible old state |
| Login/workspace/authorization/evidence/history/report regression | Stop new writes, preserve failed-state metadata, invoke rollback decision maker |
| Failure after traffic resumed | Fence writers; record post-boundary writes and approved RPO loss; never silently discard new investigations or merge DBs |

Before any schema change, a code-only rollback is possible only if DB/storage/config
are confirmed unchanged. After schema change, restore old DB, matching old code/config,
evidence and required cache into **fresh targets**, keep the failed targets offline and
preserve them. Never point old code at the new schema and hope it works.

For an M5-format backup matching the restoring application's head, follow the
[guarded restore procedure](operations.md), including trusted whole digest and an empty
DB with no user objects. M6 cannot restore a pre-M5 native dump through that CLI.

For the legacy native branch, the operator must first provision a new empty DB and
fresh private roots under the previously rehearsed, approved procedure. Check the
DB target name independently and all user objects (tables, views, functions, types,
non-default schemas and large objects), not just table count; refuse existing targets.
Use the matching old runtime and trusted native archive. Example DB restoration step:

```sh
# APPROVED_FRESH_RESTORE_SERVICE must resolve to the independently checked empty DB.
PGSERVICE=APPROVED_FRESH_RESTORE_SERVICE "$PG_BIN/pg_restore" --single-transaction --exit-on-error --no-owner --no-acl --dbname="$FRESH_RESTORE_DB_NAME" "$VERIFIED_LEGACY_DUMP"
```

No --clean, dropdb, overwrite, downgrade or automatic retry against a populated target.
Restore only vetted trusted storage archives into previously nonexistent roots; preserve
keys and metadata, validate inventory/baseline digests, all historical report hashes,
review decisions, membership and migration state before selecting the restored DB/roots.
An incomplete restore stays disconnected; retry into different fresh resources.
Native legacy restore lacks M5's RESTORE_INCOMPLETE enforcement, so operational fencing
is mandatory. Reapply intended least-privilege roles/grants and private configuration.

Change backend/frontend/proxy targets together to the matching recovered release only
under approval. Verify local then HTTPS health/auth/permissions/history with synthetic
credentials before returning traffic. Keep DuckDNS/TLS unchanged for same-host recovery;
new-host/IP/DNS cutover requires separate infrastructure approval, validated TLS and TTL
planning. Do not reprocess legacy evidence or change report hashes as a recovery shortcut.
Total RTO is unmeasured: provisioning, transfer/decryption, native restore, evidence
validation, configuration and smoke tests dominate beyond small fixture timings.

## 10. Post-upgrade and rollback smoke checklist

- [ ] Login, invalid login, logout/session refresh and correct workspace selection.
- [ ] Existing case inventory accessible to permitted roles; nonmember/suspended member
  requests denied; unrelated workspace remains usable; analyst cannot review/bundle originals.
- [ ] Historical evidence IDs, immutable digest metadata, custody and report hashes retained;
  actual private evidence verification only with specifically approved forensic access.
- [ ] Create an isolated synthetic case, upload/verify all three M4 fixtures and inspect
  custody. Never deliberately tamper with production originals to test a warning.
- [ ] Create Linux/Windows/Sysmon profiles; explicit timestamp assumptions and coverage;
  ingest, filter/paginate and reingest with stable logical identities/counts.
- [ ] Select an explicit event set; run all five families; inspect uncertainty lanes and
  account/IP/host pivots; accept/reject with notes; rerun without approval transfer/duplicates.
- [ ] Generate deterministic report with selected event set and accepted-only conclusions;
  historical report content/hash unchanged; stale supports remain visibly historical.
- [ ] Export metadata then explicitly authorized synthetic originals; browser download,
  offline `python -m app.ops.archive PACKAGE.zip`, safe retry/history and correct limits.
- [ ] Deep links, fresh/stale browser cache, static assets, multipart size errors, API error
  content types and long synchronous requests work through HTTPS/Nginx.
- [ ] No secrets/raw records in routine logs; readiness remains correct; available disk,
  inodes, memory/swap and error rates meet the rehearsed thresholds.

Archive the sanitized results and exact source/schema/artifact/backup references in the
private change record. Do not export private data to CI or leave synthetic admin accounts
without an explicitly approved lifecycle. Cleanup is a later authorized action.

## 11. Capacity, disk model and prioritized risks

H: t3.micro/20 GB EBS/2 GB swap is a constrained shared DB/API/storage failure domain,
not a verified current allocation. Swap does not make memory pressure safe. Keep one
worker, build elsewhere and limit simultaneous uploads/ingestion/exports during testing.
CPU credit balance, actual RAM, baseline utilization and storage headroom are unknown.

For each filesystem budget independently: old+new source/venvs/assets, current PG data
and WAL, retained originals/cache, largest simultaneous upload staging and verified
snapshots, export builders and completed packages, backup staging plus encrypted copy,
and fresh DB/storage restore targets. The backup uses stored ZIP entries; do not assume
evidence compresses. A legacy tar also approaches originals' size. In-place upgrades still
need WAL/index space; preserving a same-disk rollback can require another DB and another
full evidence copy. Off-host storage does not eliminate local staging requirements.
Count separate mounts/tmpfs and inodes; agreed reserve must cover measured peaks, log/WAL
growth and rollback, not an arbitrary free-space percentage. No safe minimum GB is known.

| Risk | Severity / evidence | Impact / mitigation |
| --- | --- | --- |
| Unknown deployed source/schema | High, U; health/readiness mismatch P | Wrong migration or startup; inventory and actual-baseline rehearsal first |
| M6 backup used on old schema | High, R/D confirmed rejection | No rollback backup; choose section 7 native legacy branch before migration |
| Unproven off-host/encrypted recovery | High, U | Single EBS failure loses metadata+originals; verified encrypted copy and restore drill |
| Small shared filesystem/memory | High, H/U | OOM, full disk, failed snapshots/migration; measured budgets and off-host builds |
| Legacy workspace backfill and schema locks | High, R | Access interpretation change/blocking; owner review, maintenance and bounded rehearsal |
| Wrong relative root or permissions | High, R/U | Evidence appears missing/new cache misplaced; absolute preserved roots, service checks |
| Old/new code overlap or code-only rollback | High, R/U | Incompatible writes/history; fence writers, matching fresh-target recovery |
| Proxy timeouts/cache/upload settings | Medium, P/R/U | Lost response, stale assets, blocked exports; actual HTTPS synthetic smoke and durable history |
| Unsigned archives/secret recovery gap | High, R/U | Altered source accepted or unusable restore; independent digests and approved secret recovery |
| DNS/cert renewal/IAM/SG assumptions | Medium, H/U | Outage/exposure; read-only operator verification, separately approved corrections |

Development evidence only: M5's 2000-event/16 MiB originals export was about 22.9 MB,
14.54 s with allocation tracing and about 10 MB traced Python peak on Windows/SQLite;
native PostgreSQL synthetic backup/restore were 1.77/1.90 s for about 294 KB.
M6's 1000-event full browser scenario was 7.6-11.1 s locally and 2.8 s in CI, not parser
CPU time or EC2 capacity. No production throughput, RSS, RTO or latency promise follows.

Controlled staging must measure peak process RSS, DB/WAL growth, CPU/credits, swap,
temp/cache disk, dump/restore duration, migration locks and HTTPS ingestion/detection/
pagination/report/export latency on representative supported sizes. Include bounded
concurrent requests, slow downloads, disk reserve and recovery time. Do not load test
the live host or increase infrastructure charges under this assessment.

Application budgets are not instance sizing guarantees: event ingestion accepts up to
10 MiB, 20000 records and 32768 characters per record; detection sets are bounded to
10000 events. Artifact parsing has separate limits, including 50 PDF pages and explicit
partial coverage. A 100 MiB accepted upload is not automatically ingestible as events.
Read current coverage and omission metadata rather than raising budgets to fit a demo.

## 12. Verification record and final approvals

Repository inspection covered current guides, historical AWS records, config/startup,
all eleven migrations, storage/snapshot/export/backup/preflight code, Docker/Compose,
frontend build metadata and both CI workflows. No private local infrastructure file was
needed. Current public observations are limited to section 2 and can change after it.

Disposable PostgreSQL 16.15 on loopback 55482 was newly initialized solely for this
assessment. Fresh upgrade to ee5b99eb5ce4 and alembic check passed. Existing PostgreSQL
concurrency, populated M3/M4 history and native recovery tests plus operational checks
passed **19 tests**. Additional synthetic populated pre-workspace and workspace-era
upgrades exercise 000a8976b7f1 and 9b6e5c4d3a21, preserving report hashes, accepted/rejected
decisions and baseline metadata while leaving historical support null and events empty.
They also prove the old-schema backup refusal before evidence access: both legacy cases
passed. This documentation revision's CI is recorded in the handoff; no production-schema
compatibility or production backup is claimed from these synthetic fixtures.

Final local command from backend/, with APP_ENV=test, the dedicated loopback
M1_POSTGRES_TEST_URL and matching M5_PG_BIN, was
`python -m pytest tests/test_postgres_evidence.py tests/test_m5_recovery.py tests/test_m5_operations.py tests/test_m6_tools.py -q`:
**35 passed in 40.58 s**, one existing Starlette test-client deprecation warning. It
includes eight PostgreSQL cases, not SQLite claims about concurrent database behavior.
The newly owned local cluster is stopped after validation; no existing cluster or
production service is restarted. Documentation checks cover 30 tracked Markdown files.

M6 baseline CI already passed backend 410 plus 6 dedicated PostgreSQL checks, frontend
84, Chromium 6, dependencies, documentation, candidate and container readiness. Application
code is not changed by this assessment. Documentation checks and updated migration tests
must pass on the final documentation/test commit as well. No need to repeat the entire
M6 browser journey locally merely to claim a production rehearsal.

Deployment approval requires all of: identified host/source/schema; approved path/config
worksheet; actual-baseline rehearsal; verified encrypted off-host rollback backup and
trusted artifact; adequate measured capacity; owner-approved legacy workspace treatment;
maintenance and post-write RPO decision; signed migration/service/proxy change plan;
named rollback operator; complete synthetic smoke checklist. Public release/license/tag
and production infrastructure changes remain separate owner decisions. A deployment
approval must explicitly authorize private backup/evidence access and mutations; this
assessment does not. Until those gates are met, the production upgrade remains NO-GO.

## 13. Final authorized production inventory and decision record

The owner supplied an active SSM session on 2026-11-06. Inspection began around
14:04 IST (08:34 UTC); the public health response was rechecked at 14:21 IST.
Resource IDs, account identifiers, IP addresses, original storage paths, session IDs,
secrets and backup contents are intentionally absent from this public document.
Resolved live paths belong in the owner's private execution worksheet. No production
credentials were requested, discovered or copied. SSM metadata queries used read-only transactions
with five-second statement timeouts; no investigation records were queried.

| L: fact | Verified result |
| --- | --- |
| Host | Amazon Linux 2023.12.20261016, x86-64; t3.micro in Mumbai, ap-south-1a |
| Root volume | 20 GiB encrypted EBS; DeleteOnTermination enabled; about 16 GiB available at inspection |
| Memory | 913 MiB total, about 442 MiB available; 2 GiB swap, about 24 MiB in use |
| Temporary filesystem | /tmp is roughly 457 MiB tmpfs; not an appropriate default for large verification/restore copies |
| Inodes | Root about 1% used, 10396763 free; /tmp 1048559 free at inspection |
| Service | provena.service active/running as ssm-user; backend working directory and .venv/bin/python confirmed |
| Production checkout | 9024ccd55c89c84876aeb5d7ea3b352f108fb5c1; no tracked changes reported with optional Git index writes disabled; untracked files not enumerated |
| Python/dependencies | Python 3.13.15; FastAPI 0.116.2, Starlette 0.48.0, multipart 0.0.19, SQLAlchemy 2.0.55, Alembic 1.20.0, psycopg2-binary 2.9.13 |
| Database | provena, PostgreSQL 16.15, 10607639 bytes; schema 9b6e5c4d3a21; API PID/socket-to-catalog correlation confirmed this is the application's DB without reading a connection string |
| Schema/WAL metadata | 19 public base tables, consistent with this revision; current WAL files total 33554432 bytes; neither count proves zero schema drift or peak migration WAL |
| Native utilities | /usr/bin/pg_dump and /usr/bin/pg_restore, both 16.15 |
| Evidence | Local root outside checkout, service-user ownership, mode 700; 147456 allocated bytes; no filenames or original bytes returned |
| Current release disk | Checkout 409886720 allocated bytes, including its 121806848-byte venv; static frontend 1949696 bytes separately; do not count the venv twice |
| Frontend fingerprint | index.html SHA-256 da41fd67070a762878bab4b026ef514e6df41e8f4ad860de4330b3dc8b217474; this does not prove which source generated the static files |
| Host Node tooling | Node 24.21.0, npm 11.19.0; M6 CI/build uses Node 22, so build off-host rather than relying on untested equivalence |
| Network | API/PG listen on loopback 8000/5432; SSH binds all interfaces but attached SG ingress contains only public TCP 80/443 |
| Proxy | Nginx 1.30.5, /api/ retained, upstream loopback 8000, SPA index fallback, TLS 443 and HTTP 80; body limit 100M, read timeout 120 s |
| Forwarding/cache | Host, real IP, forwarded-for and scheme directives observed; no cache-control directive found in the inspected site allowlist; authenticated pass-through/cache behavior still needs smoke testing |
| Nonsecret settings | APP_ENV=production; CORS_ORIGINS=http://localhost:5173; preserved absolute evidence root; no allowlisted process-level override found |
| Existing export root | Legacy default cache directory absent; no explicit new export root observed |
| Renewal | Certbot renewal service installed/static; certbot-renew.timer disabled; crontab unavailable to the inspected sudo command and no /etc/cron.d entries available; no other active renewal mechanism established |
| Scheduling/backup | DuckDNS update timer active; no backup-named active timer identified; EC2 Owned by me snapshot view reports none in this region |
| Off-host metadata | Existing operations-purpose S3 bucket has SSE-S3 default encryption, versioning and Object Lock disabled, no lifecycle or replication rules; its root lists one migration prefix |

The operations bucket was inspected only for inventory/policy metadata. The attempted
prefix navigation was stopped by Computer Use's URL-confidence safety check. No backup
object was opened or downloaded, so last successful backup, coverage, independent digest,
client-side encryption, deletion protection, retention and recoverability remain unknown.
SSE-S3 at-rest policy and a folder name do not establish a current complete backup.
No snapshots in this view does not exclude other-region or other-system backups.

### Actual migration suffix

```text
9b6e5c4d3a21 (source, already includes workspace backfill)
  -> b72a1e84c903  evidence registration lifecycle and input verification links
  -> c83d2f95a014  nullable parser coverage
  -> d94e30a6b125  run/artifact membership, stable correlation and support snapshots
  -> 294d21d0205e  profiles, ingestion runs, normalized events and memberships
  -> 53d6b8a0e88b  explicit event sets, detection runs and support memberships
  -> ee5b99eb5ce4  durable investigation exports (target)
```

Section 6 describes their columns, indexes, uniqueness/FKs and locking risks. None of
these six transforms historical report content or invents event interpretations.
Registration defaults do not validate old bytes; missing historical support remains
null/stale. Preserve custody/verification rows and accepted/rejected decisions. Existing
workspace assignments must be preserved, not recreated. Actual-baseline drift and data
compatibility still require the privately authorized restore rehearsal, not a production
alembic check or migration in this assessment.

### Frozen deployment candidate, separate from this handoff

Use source **36763611139923236e981da6cd66beeae56145cf**, whose application modules,
frontend source and dependency declarations match M6 b9ad5c5. Its changes added the
earlier assessment and synthetic migration checks. [CI #61](https://github.com/shikhar-sahay/provena/actions/runs/42133630009)
passed all eight jobs on this source. Do not substitute whatever main points to later.

The actual GitHub Actions artifact `provena-validated-candidate` from #61 was downloaded
locally through the GitHub connector, without deployment. The outer transport archive
matched GitHub's SHA-256 d463f3611d2dd3e787abc4a691113c1d1f5c00fad6c04a3467733204e45a9ebc.
The enclosed candidate was independently checked with the offline tool:

- Source commit: 36763611139923236e981da6cd66beeae56145cf.
- Inner ZIP SHA-256: b43522ee5a86f6588daf9ba60c3ed906aab254e2f770af9b0e3a30dbfced5e03.
- Size: 5065486 bytes; 336 files, including 309 source files and 27 web assets.
- Every source blob matched that Git commit; all manifest file digests/paths passed.
- Private-path/secret-pattern checks passed; no loopback API URL found in web scripts.
- CI built with Node 22 and VITE_API_URL unset; this is not Playwright's ephemeral build.
- Version 0.1.0-beta.0, unsigned, validation-only, publishable=false; no tag/public release.

Artifact retention expires November 13, 2026 at approximately 05:34 IST. Preserve a
verified private copy before expiry or rebuild the exact source in an approved clean
environment and record its new digest. Do not relabel a different build with this digest.
The previous Windows-built candidate has a different hash; it is not the CI binary.
The new checklist/tooling commit is a preparation revision, not the chosen application
candidate. Verify its own CI in the handoff separately.

```sh
# Local artifact inspection only. Use a trusted private candidate path.
python -B tools/deployment_gate.py --source-revision 9b6e5c4d3a21 --candidate CANDIDATE_ZIP --expect-commit 36763611139923236e981da6cd66beeae56145cf --expect-sha256 b43522ee5a86f6588daf9ba60c3ed906aab254e2f770af9b0e3a30dbfced5e03
```

The tool has no DB/network/shell execution path. It parses migration metadata without
executing it and validates a bounded private snapshot of the archive without extraction.
Unknown source returns exit 2; invalid input returns 1; exit 0 means offline checks passed,
never deployment approval. It always emits deployment_authorized=false. Pins supplied
by a caller are not signatures or independent evidence of their trustworthiness.

### Proposed operating budget and configuration, not applied

Keep one worker, build elsewhere and serialize large investigative/export operations
initially. Preserve current signing and DB secrets privately; operator validation of
M6 secret-strength requirements must not print values. A weak key needs an explicitly
approved rotation/session-invalidation plan, not silent replacement.

| Setting | Proposed after approval |
| --- | --- |
| APP_ENV | production |
| CORS_ORIGINS | https://provena-app.duckdns.org; the current localhost HTTP value fails M6 validation |
| TRUSTED_PROXY_IPS | 127.0.0.1 for the verified local Nginx hop; review actual Uvicorn forwarding flags |
| DATABASE_URL | Retain privately, using installed psycopg2 driver; preserve database identity |
| SECRET_KEY | Preserve privately if it passes M6 checks; no value committed or displayed |
| EVIDENCE_STORAGE_BACKEND/ROOT | local and the existing absolute root from the private worksheet; no relocation |
| EXPORT_STORAGE_ROOT | New private absolute, separate/non-nested disk-backed root; never static web or release directory |
| TMPDIR | New private service-writable disk-backed directory; confirm with Python tempfile diagnostics after authorized startup |
| EVIDENCE_MAX_UPLOAD_BYTES | Proposed 10485760 (10 MiB), matching normalized-log input byte limit |
| EXPORT_MAX_BYTES / EXPORT_METADATA_MAX_BYTES | Proposed 67108864 / 16777216 (64 MiB / 16 MiB) |
| EXPORT_RETENTION_HOURS | 24, with explicitly approved maintenance scheduling and disk monitoring |
| BUILD_ID / LLM_ENABLED | Frozen deployment SHA / false |

The 100M proxy limit can remain for the proposed 10 MiB upload cap. If retaining the
100 MiB application default instead, explicitly raise/review proxy allowance for multipart
overhead, for example 110m, and test the boundary. Do not enlarge synchronous timeouts
blindly: a lost response may leave a completed durable operation. Keep old hashed static
assets through the observation period and require index/API cache smoke tests.

The current disk allocation looks favorable for this small baseline, but no unconditional
capacity GO follows from a rounded df reading. Budget separately for new venv/release,
backup plaintext plus encrypted copy, DB/WAL/index growth, restore clone, retained old
release, cache and temp. The old venv is already included in checkout usage. Peak WAL,
new Linux venv size, restore duration and RSS remain unmeasured. Do not invent a fixed
GB reserve; approve headroom after the rehearsal's measured peaks and rollback needs.

An individual snapshot is bounded by its source size; the proposed upload cap limits new
ones to 10 MiB but does not shrink legacy evidence. Original exports build under the
private cache, not wholly in RAM. Verification can require a copy up to its archive budget;
M5 system restore can copy up to 4 GiB, far beyond /tmp's 457 MiB. Prefer disk-backed
temporary storage for both application and recovery operators. A 64 MiB export cap is
per package, not a total cache quota; retention is not automatic without scheduling.
With roughly 442 MiB available RAM, simultaneous parsers/DB/cache/swap pressure must be
measured on a protected low-volume rehearsal. Local Windows results are not t3 capacity.

### Gates and minimum next authorized work

| Gate | Current decision |
| --- | --- |
| A: live inventory | Largely resolved: host, runtime, checkout, service, roots, DB and proxy verified; private paths retained by owner |
| B: compatibility | Source and six-step suffix confirmed; populated synthetic upgrade/native restore checks run; actual restored-baseline drift check still required |
| C: backup consistency | BLOCKED: correct legacy procedure defined, but no authorized complete current production backup verified |
| D: recoverability | BLOCKED: synthetic restore is not an actual production-baseline restore rehearsal |
| E: capacity | CONDITIONAL: small observed data/disk fit is encouraging; disk-temp, limits, RSS/peak-space and operator reserve acceptance pending |
| F: configuration | BLOCKED: CORS correction, new private cache/temp roots, secret validation and renewal-plan acceptance are prepared, not applied |
| G: authorization | BLOCKED: no maintenance, backup access, migration, service/proxy switch or rollback execution approved |

Next authorize a controlled **backup and rehearsal stage first**: fence all writers,
perform/verify a native PostgreSQL 16 dump plus matching quiesced originals and protected
configuration references, encrypt and verify an off-host copy, restore the old baseline
into fresh isolated targets, compare metadata/digests/report hashes and permissions,
then migrate the clone through the six revisions and measure capacity/smoke tests.
Only after signed acceptance should the same or a later explicitly authorized window
correct configuration and switch the retained API/frontend releases. Keep real backup
and original bytes outside CI and this repository. No owner should approve an
unconditional upgrade merely from the successful synthetic tests or this checklist.

The disabled renewal timer is a concrete operations issue. Authorize review of the
installed renewal unit and an actual approved renewal mechanism separately; do not
infer that cron or external automation compensates for it. No certificate renewal,
timer enablement or TLS change was attempted here.

### Additional disposable recovery proof

The focused synthetic suite previously passed 50 tests, including the exact source
upgrade, native M5 recovery and offline candidate-negative tests. A new native legacy
rehearsal also passed independently: it creates an isolated source at 9b6e5c4d3a21,
seeds synthetic accounts/workspace/case/evidence/custody/verification/review/report data,
quiesces its only writer, runs pg_dump and copies a verified original, then restores
into fresh private targets. All old table fingerprints and the report hash match; a
post-boundary annotation is absent. The restored clone upgrades through all six
migrations and passes alembic check while retaining identities, reviews and custody.
This proves the tested procedure against synthetic data, not Gate D for real production.
The test is explicitly included in the PostgreSQL CI job; default backend runs skip it
unless a guarded localhost provena_ci control DB and native binaries are supplied.

Final reviewed-index export, excluding unrelated local work, passed **51 tests in
65.05 s** using PostgreSQL 16.15. The command from backend/ was
`python -m pytest tests/test_postgres_evidence.py tests/test_m5_recovery.py tests/test_m5_operations.py tests/test_m6_tools.py tests/test_deployment_gate.py tests/test_legacy_recovery.py -q`.
This includes nine PostgreSQL cases, operational/configuration regressions and fifteen
new offline-tool cases. One existing Starlette test-client deprecation warning remains.
The earlier 50-test and independent legacy runs are intermediate results, not extra tests
to add to this count. Documentation checks cover 31 tracked Markdown documents. Final
preparation commit, push and exact CI conclusions accompany the handoff; they do not
change the frozen CI #61 application candidate.

## Gate 1 preparation continuation, 6 November 2026

The [concrete recovery proposal](gate1-recovery-plan.md) and private owner worksheet
now separate Gate 1 backup/rehearsal authorization from Gate 2 live upgrade approval.
Neither execution gate has been approved. No original evidence was read, production
backup created, service stopped, package installed, database migrated or configuration
changed during this preparation.

Read-only refresh at 14:30:43 UTC reconfirmed source
`9024ccd55c89c84876aeb5d7ea3b352f108fb5c1`, active legacy service, Alembic
`9b6e5c4d3a21` and database size 10,607,639 bytes. Existing native PostgreSQL clients
are 16.15, OpenSSL is 3.5.8 and AWS CLI is 2.36.47. The frozen deployment candidate
remains `36763611139923236e981da6cd66beeae56145cf`, despite later preparation commits.

The existing operations bucket's owner console shows Block all public access On and
Bucket owner enforced. The instance role cannot read the public-access-block policy;
this was an AccessDenied result, not a reason to alter IAM. Ciphertext upload rights
remain unverified and must be tested with a synthetic challenge after Gate 1 approval,
before downtime. Previously observed no-versioning/no-Object-Lock settings do not give
immutable retention. No objects were opened or transferred during this inspection.

The local Windows 11 Home PC has approximately 41.4 GiB free and 15.65 GiB RAM,
OpenSSL 3.5.2 and PostgreSQL 16.15 tools. Volume encryption is not yet owner-confirmed;
the owner must confirm Device Encryption and independent recovery-key availability,
or select another already encrypted volume. The dedicated CMS recipient key has not
been generated. The private metadata-only plan has owner/SYSTEM access and no backup
contents; restricted permissions alone are not encryption.

Synthetic streaming AES-256-GCM CMS with RSA-3072 OAEP/SHA-256 successfully encrypted
and restored 1,277,952 bytes; modified and truncated ciphertext failed. Throwaway test
keys are not recovery keys. Owner-only interactive passphrase entry, independent key
escrow and a real synthetic transfer/decryption challenge remain prerequisites.

The strengthened native legacy recovery test compares every original table's old
field projection before backup, after native restore and after all six migrations.
Added columns are allowed; changed credentials, notes, decisions, original report
content or other old fields are not. Six unit cases exercise the projection guard.
These synthetic checks improve Gate B evidence but cannot satisfy real-data Gate D.

Next: owner encryption/key preparation, approval of the exact private plan, then
Gate 1 execution only. Proposed 15-minute downtime is a budget, not a benchmark.
Gate 1 must explicitly allow starting only the unchanged legacy service after the
verified backup boundary; otherwise resumption requires another instruction. Full
production upgrade remains **NO-GO** until Gate 1 succeeds and Gate 2 is approved.

## Repository evidence index

- [Settings and production validation](../backend/app/core/config.py),
  [application startup](../backend/app/main.py), [health routes](../backend/app/api/endpoints/health.py).
- [Read-only preflight](../backend/app/ops/preflight.py),
  [backup and guarded restore](../backend/app/ops/recovery.py),
  [offline archive verifier](../backend/app/ops/archive.py).
- [Evidence storage and exact snapshots](../backend/app/modules/evidence/storage.py),
  [export cache](../backend/app/modules/exports/artifacts.py),
  [all migrations](../backend/alembic/versions).
- [Frontend API origin](../frontend/src/api/client.ts), [Dockerfile](../backend/Dockerfile),
  [local Compose](../docker-compose.yml), [CI](../.github/workflows/ci.yml).
- [Legacy and concurrent PostgreSQL checks](../backend/tests/test_postgres_evidence.py),
  [M5 recovery demonstration](../backend/tests/test_m5_recovery.py),
  [native legacy restore/upgrade rehearsal](../backend/tests/test_legacy_recovery.py).
- [Offline candidate and migration gate tool](../tools/deployment_gate.py),
  [negative tool tests](../backend/tests/test_deployment_gate.py).
