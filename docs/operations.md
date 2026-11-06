# Maintainer operations

For the existing EC2 deployment, use the [M6 deployment assessment and gated runbook](deployment-readiness-m6.md).
It separates public observations from historical host claims and defines the unknowns,
legacy backup branch, maintenance gates and fresh-target rollback. No production action
is approved by these instructions or by passing CI.

The [execution checklist](deployment-execution-checklist.md) records the confirmed
legacy source 9b6e5c4d3a21, frozen application candidate and six-step migration suffix.
The source already includes workspace backfill. Use native legacy backup/recovery
before upgrading it; current M5 backup is not compatible with that old schema.
Production inspection found HTTP-localhost CORS and a disabled renewal timer. Their
corrections, private disk-backed TMPDIR/cache roots and operating limits are prepared
in the assessment, not applied. Original storage paths belong only in the private
operator worksheet. Synthetic restore success is not a real-baseline restore drill.

These commands describe implemented local/disposable workflows. M5 did not access,
back up, change or deploy the live AWS system. Never substitute production targets
into tests. The application is not certified forensic software.

## Configuration and preflight

Use Python 3.13 and Node.js 22. Install `backend/requirements.txt`; use PostgreSQL 16
and matching PostgreSQL client utilities for dump/restore. Set configuration through
your private process environment. Never commit environment files or dump archives.

Production requires `APP_ENV=production`, a non-placeholder PostgreSQL `DATABASE_URL`,
a signing `SECRET_KEY` of at least 32 characters with varied characters, and exact HTTPS
`CORS_ORIGINS` when cross-origin access is required. Use a cryptographically random key,
not a memorable sentence. Token lifetime is bounded to 1-1440 minutes. `TRUSTED_PROXY_IPS`
accepts explicit IPs/CIDRs; all-address trust is rejected in production. The reverse proxy
must actually terminate TLS and strip untrusted forwarding headers. Preflight cannot
prove external TLS configuration, DNS correctness or certificate renewal.

Storage settings: `EVIDENCE_STORAGE_BACKEND=local` with `EVIDENCE_STORAGE_ROOT`, or `s3`
with `S3_EVIDENCE_BUCKET` and `AWS_REGION`. Generated archives use `EXPORT_STORAGE_ROOT`,
separate from original evidence. Defaults are 512 MiB per export, 32 MiB metadata and
24-hour retention. `EXPORT_MAX_BYTES`, `EXPORT_METADATA_MAX_BYTES` and
`EXPORT_RETENTION_HOURS` are validated. Both roots need protected permissions and
adequate free space; temporary verified copies also consume disk space.

From `backend/`:

```sh
python -m app.ops.preflight
python -m app.ops.preflight --database --storage
python -m alembic upgrade head
python -m alembic check
```

The first command performs configuration-only checks without network calls. Connectivity
and storage probes require explicit flags. They are read-only: no migrations, probe files,
directory creation or evidence mutation. S3 bucket probing is a real read-only network
operation when explicitly selected; do not run it against live AWS as part of local tests.
The second command fails for unreachable/unmigrated databases or unavailable storage.
Filesystem permission inspection does not prove future successful writes or capacity.
Migrations are an explicit separate operation. Never migrate production without its
approved deployment procedure, a validated backup and a tested recovery path.

## Local Compose

```sh
docker compose up --build --wait
```

The development stack binds database/API/frontend ports to loopback. PostgreSQL health
precedes explicit development migrations and preflight, then API startup. Named volumes
separate database, original evidence and generated archives. The API runs as a non-root
user. Newly created storage directories are private. Existing volumes may require an
operator-reviewed ownership adjustment; never recursively change real evidence permissions
without understanding the old installation and preserving its backup.

Use `/api/live` for process liveness and `/api/ready` for database/schema/storage readiness.
`/api/health` remains the legacy backward-compatible health summary. Public readiness
does not expose connection URLs, storage paths or diagnostics. Optional Ollama never
determines readiness. `BUILD_ID` can identify a build in private CLI diagnostics.

## Investigation packages

Use the case Exports tab. Metadata-only is the default; it still contains confidential
case records, source excerpts, accounts and annotations. Only case managers can export
or download selected original evidence. All users require current workspace and case
authorization. Only explicitly selected sets supply normalized events; only selected
reports are embedded. Original evidence bytes are never included implicitly.

```sh
python -m app.ops.archive downloaded-export.zip
```

This standalone verifier needs only Python's standard library and never extracts or
executes package content. Pass means internal structure/digests/report hashes are
consistent, not authenticity or independent proof of provenance. Keep package SHA-256
references separately through a trusted channel. Store original-containing packages
as confidential evidence and apply appropriate access controls/encryption outside the tool.

## Private system backups

**Schema compatibility:** the current backup CLI requires its exact Alembic head,
`ee5b99eb5ce4`. It cannot back up an older production schema before upgrade. Do not
migrate merely to enable backup. Follow the [legacy backup decision](deployment-readiness-m6.md)
and rehearse a native PostgreSQL plus quiesced-storage backup/restore first when the
source predates M5. The current restore CLI likewise refuses a different manifest
revision; a native legacy dump is not a Provena-format backup archive.

These contain application account hashes and all persistent evidence, not merely a case
export. Protect and encrypt them outside this tool, keep independent copies and record
the returned whole-package SHA-256 separately. The tool never includes `.env`, signing
secrets, PostgreSQL roles, proxy/TLS keys or AWS credentials; recover those separately
through the operator's secret-management procedure.

Verify a private backup offline without connecting to a database or executing SQL:

```sh
python -m app.ops.archive --kind backup /private/backup.provena-backup.zip
```

This checks the package's internal manifest, content hashes and reference inventory;
compare the whole-package digest with an independently trusted reference before restore.

The backup uses a PostgreSQL exported REPEATABLE READ snapshot for both `pg_dump` and
table fingerprints/inventory. Each evidence file is copied from an M1 bounded snapshot
and must match its immutable database baseline. Completed export cache archives are also
copied and verified. This is not an independently timed dump plus a changing directory
copy. New database writes after the snapshot are excluded. Concurrent pruning or external
tampering can make the backup fail safely; avoid pruning during backup. Pending evidence
registrations and known integrity failures must be recovered before a complete backup.
Pause migrations and other schema changes for the entire backup. MVCC row snapshots do
not make arbitrary concurrent schema maintenance safe.
Running analytical/export operations remain running in the snapshot and require recovery
after restoration. PostgreSQL sequence counters may advance independently of MVCC rows;
semantic event/finding identities do not depend on sequence allocation.

Set a private `SOURCE_DATABASE_URL` environment variable explicitly, then confirm its
database name. Use an existing private output directory outside the repository:

```sh
python -m app.ops.recovery backup --database-url-env SOURCE_DATABASE_URL --confirm-database synthetic_source --acknowledge-sensitive-backup --output /private/backup.provena-backup.zip
```

`--pg-bin` selects a directory containing matching `pg_dump`/`pg_restore` binaries.
The database URL is supplied through an environment variable, never a command argument
or log entry. Native utilities receive connection details through their private process
environment. Backups are bounded to 4 GiB, 10000 files and 2 million validation rows.
They fail rather than silently truncate. No existing backup file is overwritten.

## Restore into a fresh isolated environment

1. Verify the whole-package SHA-256 using an independently trusted reference. Do not
   restore investigation exports or unknown third-party SQL as system backups.
2. Create a new empty PostgreSQL database and new evidence/cache target paths. The
   application and all other writers must remain stopped or disconnected from this
   restore target. Empty-target checks do not fence arbitrary external database writers.
3. Use the application release matching the backup's Alembic revision. Configure a
   private `RESTORE_DATABASE_URL` for the empty target, not the source database.
4. Run the explicit trusted restore:

```sh
python -m app.ops.recovery restore --database-url-env RESTORE_DATABASE_URL --confirm-database synthetic_restore --acknowledge-sensitive-backup --trust-backup --expect-sha256 TRUSTED_PACKAGE_DIGEST --package /private/backup.provena-backup.zip --evidence-root /private/new-evidence --exports-root /private/new-exports
```

5. The utility refuses existing user objects (including tables, views, functions, types,
   non-default schemas and large objects), existing roots and nested evidence/cache
   roots. It snapshots and verifies the archive before using native `pg_restore` in a
   single transaction, restores exact generated evidence keys, verifies every table's
   canonical row fingerprint and every immutable report hash, then removes the incomplete
   restoration marker. Only trusted backups are eligible because SQL restore inherently
   executes trusted database definitions; the investigation verifier never executes SQL.
6. Configure the restored application for the new database and local evidence/cache roots.
   Original S3-backed backups restore portable bytes to local storage. Direct S3 restoration
   is not implemented; any later upload of preserved keys requires a separately authorized,
   private-bucket migration and baseline verification. Synthetic S3 tests do not establish
   live AWS integration.
7. Run preflight, migration/schema checks, verify reports and selected evidence, test a
   synthetic account's case permissions, then recover interrupted operations explicitly.
   Rotate the signing secret if existing bearer sessions must be invalidated.

On failure, target paths can remain with `RESTORE_INCOMPLETE` and the database can contain
restored metadata. Readiness rejects an incomplete local restore. Keep the target offline,
inspect it, and retry into different fresh resources. The utility never drops, resets,
cleans or overwrites existing databases/directories automatically.

## Recovery, retention and observability

Existing evidence/ingestion/detection recovery APIs remain explicit and case scoped.
Export attempts progress `running` to `completed` or `failed`; only completed, unexpired,
hash-verified packages download. Lost completion acknowledgement is resolved by rereading
the durable state. Request-key retries reuse an export; a different selection with the
same key is rejected. Partial packages are removed, or a cleanup-pending failure remains
visible if filesystem cleanup fails.

Case managers can recover interrupted exports or prune expired packages from the Exports
tab. A private maintainer command scans at most 5000 generated operations:

```sh
python -m app.ops.maintenance --database-url-env MAINTENANCE_DATABASE_URL --confirm-database synthetic_source
```

Add `--recover-interrupted` only when intentionally closing stranded running exports.
Case locks prevent interrupting an active transaction. Schedule this command through an
existing operator-controlled timer if needed; M5 does not install a timer or queue.
It never removes original evidence or historical database provenance.

Structured request logs record bounded correlation ID, method, route template, outcome
and preparation duration. They omit tokens, query strings, bodies, raw records and paths.
Correlation IDs are also attached to audit metadata. They are correlation aids, not
authentication. Streaming transfer duration is not the same as response-preparation time.
Unhandled errors receive safe 503 responses rather than raw SQL/storage exceptions.

## M6 validation, upgrades and troubleshooting

The [developer guide](development.md) owns the disposable Chromium runner and the
[investigator guide](investigator-guide.md) owns UI terminology. Do not use real evidence
in browser tests or point their control connection at an application database. Browser
artifacts are synthetic and separate from release candidates. M6 did not validate any
live EC2, DNS, TLS, S3 or monitoring configuration.

Before an independently approved upgrade, record the current source/schema revision,
pause schema-changing work and cache pruning, create/verify a private backup, and restore
it into a fresh disposable environment. Test migrations and readiness there first. A
rollback restores a validated compatible backup into fresh targets; published migrations
are not rewritten or automatically downgraded. Do not upgrade production merely because
CI is green. A localhost development Compose upgrade is not a production procedure.

| Symptom | Safe next action |
| --- | --- |
| Liveness works, readiness fails | Run private CLI preflight; inspect DB/schema/storage without exposing credentials |
| Ingestion is partial/rejected | Check supported adapter/export schema, explicit profile and coverage; preserve the source |
| A request response was lost | Inspect durable history; reuse its idempotency key where supported; do not infer rollback |
| Download is unavailable/expired | Reauthorize, inspect export history and recorded size/hash; regenerate explicitly if needed |
| Restore marker remains | Keep every writer offline, investigate validation failure and retry into different fresh targets |
| New Docker volumes work but old ones fail permissions | Review ownership with a validated backup; do not recursively change real evidence blindly |
| Browser tests refuse startup | Use a dedicated localhost provena_ci control DB, matching browser binaries and current Node/Python |

Schedule generated-cache maintenance through an operator-owned timer only after explicit
authorization. M6 does not install retention, encryption, off-host backups, alarms or
production services. Protect API/operator logs and use correlation IDs instead of raw
source records when diagnosing failures. Existing parser/selection/export budgets remain
explicit limits; narrower selections or private backup may be required for larger cases.
