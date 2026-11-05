# M5 operational and release readiness

## M4 closeout

M4 final `2faf335c5dd9355d99e6deb3bab77414aebfdef2` matches its final pushed state and
[CI #53](https://github.com/shikhar-sahay/provena/actions/runs/41997745754) passed backend,
frontend, dependencies and PostgreSQL migrations. Earlier increments #51/#52 also passed.
The immutable selection, five rules, stable shared review, three timeline lanes, pivots,
workbench, deterministic reports and historical/concurrency guarantees are implemented.
M4 was not reimplemented or expensively retested merely for closeout.

## Implemented operational foundation

Case exports have durable operations and explicit metadata/original modes. The package
schema is `provena-investigation-export/1`; its canonical manifest inventories every file
with SHA-256/size, actor/case identity, exact selections, evidence baselines, versions,
coverage, omissions and original report hashes. JSONL metadata is streamed in bounded
chunks. ZIP construction uses disk-backed temporary files, not an in-memory archive.

Defaults: 512 MiB package, 32 MiB metadata, 20000 rows per metadata file, 1000 inventory
items, 20 selected event sets, 100 reports/originals, 20 retained running/completed
operations per case and 24-hour artifact retention. Limits reject rather than silently
truncate. Original sizes and selected report sizes are checked before large reads.

`POST /api/investigations/{id}/exports` accepts an explicit selection and optional
`Idempotency-Key`. GET lists bounded history; `/{id}/download` checks current case access,
mode permissions, expiry and a copied package digest before streaming; `/{id}/recover`
closes interrupted work or expired generated artifacts under a case lock. Metadata needs
active case access; originals additionally require case-management permission and fresh
exact-byte integrity verification. Internal storage keys never enter case export DTOs.

Exports use a PostgreSQL repeatable-read metadata boundary after durable registration.
Source originals are M1 verified immutable copies, not reopened paths. A failed selection,
byte check, budget or transaction leaves no downloadable partial package. Verification
failures survive rollback through the evidence journal. Ambiguous successful commits
are reread. Failed cleanup is explicit and recoverable. Report bytes use their existing
canonical convention; old content hashes are never rewritten.

The standalone `python -m app.ops.archive` verifier uses only the standard library.
It never extracts/executes archive content and rejects altered/missing/unexpected files,
unsafe paths, duplicate entries/JSON keys, symlinks, encrypted/unsupported compression,
decompression-budget violations, unsupported schemas and report/evidence hash mismatches.
Unsigned consistency is not authenticity, a signature or certification.

The final verifier also requires typed actor/case references, a UTC creation time,
explicit bounded selections, matching report/original inventories, event-set coverage
and processing-version metadata. Backup manifests require schema/application versions,
consistency metadata and well-formed bounded table fingerprints. Missing provenance
cannot pass merely because file hashes match. Metadata-only packages can inventory
large originals without including their bytes. Existing generated M5 manifests already
contain these fields; the format stays at version 1 and old report hashes are unchanged.

## Snapshot-bound disaster recovery

`python -m app.ops.recovery` provides private system backup and trusted fresh-target
restore, separate from portable case exports. A PostgreSQL exported REPEATABLE READ
snapshot binds the native custom-format dump, complete canonical table fingerprints,
evidence inventory and export-cache records. Each copied original must match its immutable
baseline; missing/corrupt bytes fail backup. A concurrent-write test proves that a note
committed after the boundary is excluded from both dump and restored fingerprints.

Restore requires explicit connection-environment selection, database-name confirmation,
sensitive-backup acknowledgement, explicit trust and an independently supplied archive
SHA-256. It refuses existing user objects, existing paths and nested roots. Native restore
runs in a single transaction. Files restore through generated-key validation and atomic
no-clobber publication. Complete table fingerprints and immutable report hashes must match
before the incomplete-restoration marker is removed. Readiness rejects that marker.
Only trusted backups may restore SQL; investigation-package verification never executes SQL.

Backups include account hashes and private evidence. They do not include environment/TLS/
AWS credentials, PostgreSQL roles or infrastructure. Output must be outside the source
repository and is never overwritten. Limits are 4 GiB, 10000 files and 2 million validation
rows. S3 sources use the storage abstraction; restoration targets portable local storage.
Direct live S3 restore is documented as a separately authorized procedure, not claimed
as implemented or tested against AWS. See [operations](operations.md) for actual commands,
failure recovery, secret handling and post-restore validation.

## Diagnostics, release preparation and UI

Read-only preflight validates configuration and, only when requested, database/schema and
storage readiness. Production rejects weak/default signing secrets, unsafe CORS origins,
all-address proxy trust and non-PostgreSQL URLs. Validation errors hide input values.
`/api/live` is dependency-free; `/api/ready` checks required operational dependencies with
a safe public response. Legacy `/api/health` remains compatible. Optional Ollama is not
a readiness dependency. Structured request logs and audit metadata share bounded request
IDs without logging credentials, raw records, query strings or private paths. Unexpected
exceptions receive safe responses. Export cleanup is an explicit bounded maintainer CLI.

The case Exports tab provides selection, metadata/original separation, permissions,
safe operation status, bounded history, downloads, recovery and offline instructions.
Ambiguous network retries preserve the request key; changed selections create a new key.

Cancellation is not an implicit rollback guarantee. A synchronous worker may finish
after a client disconnects; consult durable history and retry with the same request key.
Hard interruptions before completion leave a `running` operation that cannot download
and can be explicitly recovered. An interruption after the completion commit retains its
completed state and package. Regression tests interrupt building and both sides of the
completion commit, check audit retention/idempotent retry, and prove that recovery never
deletes an unrelated completed export. Request cancellation also preserves its original
exception and resets correlation context instead of masking it with a logging error.

Release validation is gated on existing CI jobs, builds a clean frontend and a verified
candidate from committed allowlisted source, then tests disposable Compose startup. It
does not create releases/tags or deploy. Internal version is `0.1.0-beta.0`; approval and
licensing remain publication requirements. Read [release policy](releases.md).

## Historical compatibility and known limits

Migration `ee5b99eb5ce4` adds only export operations; old evidence, reports, events,
analyst decisions and detection identities are retained. No historical migration is edited.
Existing local configuration/health/proxy changes were reviewed and integrated where
directly related to M5. Private environment and unrelated deployment/audit files remain
outside intended commits; `migration-backup/` is never opened or changed.

Operational limits are deliberate; large cases can require narrower export selections
or the private system-backup path. No independent cryptographic signatures, managed key
service, certified chain of custody, background queue, automated production deployment,
native EVTX decoding or public release is implied. Operators must protect/encrypt backup
copies, manage off-host retention and perform their own controlled deployment/restore drills.

Docker Desktop's local engine was unavailable during implementation; real PostgreSQL
tests used a disposable local PostgreSQL 16.15 cluster. The CI release workflow validates
fresh container startup, which passed in CI #55. The final pushed revision and subsequent
workflow conclusion are also supplied in the implementation handoff.

## Reproducible demonstration and measurements

The [M5 demonstration](../sample-data/m5-operations/README.md) runs the actual API,
concurrent export retries, archive tampering, native PostgreSQL backup, fresh restore,
restored login/authorization, stable events/findings and immutable report checks. It
preserves isolated resources for inspection instead of deleting databases automatically.

Representative local capacity test: Windows, Intel Core i5-13420H, approximately 16 GB
RAM, Python 3.13.5 and isolated SQLite. With 2000 normalized events and 16973316 bytes
of originals, the archive was 22874516 bytes. Observed durations were ingestion 0.62 s,
detection 2.15 s, a 100-item timeline page 0.14 s and report generation 0.49 s. Export
with Python allocation tracing enabled took 14.54 s and peaked at 9986636 traced bytes.
Native allocations/RSS are not measured. These are diagnostic local observations under
concurrent test load, not EC2 or PostgreSQL production guarantees. Batching JSONL writes
reduced observed instrumented export overhead from an earlier 22.27 s run; that comparison
was not a controlled benchmark. The test imposes no fragile machine-speed threshold.

The real PostgreSQL 16.15 demonstration produced a 294184-byte synthetic backup in
1.77 s and restored it in 1.90 s. Those figures include native tool work and fingerprint
validation but not full environment provisioning. All table fingerprints, report hashes,
review states, selected events and case isolation matched; the intentionally post-boundary
annotation was absent. Larger databases and evidence inventories require independent
capacity planning and restore drills.

## Verification record

Backend foundation commit: `8a75b0b4fe4fe9176864807ab7d6ca50e98f8484`.
Workbench/release commit: `fc655b1cbe22696e9023e084095bb450bef23f0d`.
[CI #55](https://github.com/shikhar-sahay/provena/actions/runs/42035809689) succeeded
on the latter with all six jobs: dependencies, backend, frontend, PostgreSQL migrations,
candidate verification/upload and disposable Compose startup/readiness.

Cancellation/handoff commit `bebcc83a97121fa28f4bdab74fee0dcb814b9c07` was also
verified on [CI #56](https://github.com/shikhar-sahay/provena/actions/runs/42036829400):
all six jobs passed, with 378 backend tests plus six PostgreSQL checks in the dedicated
job, and 66 frontend tests. The continuation found the cancellation fix already committed
and retained it. Remaining changes enforce the existing manifest contract and add
interruption/commit-boundary tests; they do not reimplement M4 or change schema history.

| Command/check | Actual result |
| --- | --- |
| Fresh Python 3.13 environment, `python -m pip install -r backend/requirements.txt "pip-audit>=2.9,<3"` | Successful resolution/install |
| `python -m pip check` | No broken requirements |
| `python -m pip_audit -r backend/requirements.txt` | No known vulnerabilities |
| `python -m pytest -q`, clean archive of backend foundation with isolated PostgreSQL enabled | 382 passed, 381.34 s |
| CI #55 `python -m pytest` | 377 passed, 6 PostgreSQL checks explicitly skipped in this job |
| CI #55 `python -m pytest tests/test_postgres_evidence.py tests/test_m5_recovery.py -q` | All 6 PostgreSQL checks passed, 7.22 s |
| Final export tests after operation-owned interrupted-temporary cleanup | 19 passed |
| Final operational tests including cancellation/context cleanup | 13 passed |
| `python -m alembic upgrade head` and `python -m alembic check`, disposable PostgreSQL | Current at `ee5b99eb5ce4`, no new upgrade operations |
| `python -m app.ops.preflight --database --storage`, explicit synthetic targets | Ready, database/schema and both local roots healthy |
| `npm ci`, `npm audit`, `npm audit --omit=dev` | Installed successfully, both audits zero vulnerabilities |
| `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` | Passed; 66 frontend tests in 23 files |
| `docker compose config --quiet` locally | Passed; actual Docker daemon unavailable locally |
| CI #55 disposable Compose build/start plus `/api/live` and `/api/ready` | Passed on Ubuntu Docker |
| `python tools/build_release.py --frontend frontend/dist --output NEW_PATH.zip` | Verified unsigned candidate, committed allowlist only, not publishable |
| `git diff --check` and reviewed explicit staging | Passed; private environment/backup/evidence paths excluded |

The 382-test clean-source run predates the additional interrupted-builder and request
cancellation regressions; those passed separately. CI #55 already includes the builder
regression. This distinction prevents treating an older local test count as a later
single-run result. The two expected warnings are Starlette's test-client deprecation
and the deliberate duplicate-name malicious ZIP fixture. Frontend build also reports
the existing approximately 504 kB bundle warning; no gate was suppressed.

Fresh and populated M3/M4 PostgreSQL upgrades preserve accepted/rejected decisions,
evidence digests, normalized-event keys, ingestion membership and original report hashes.
Native restore verifies every table fingerprint, not just selected demo counts. Tests
include concurrent retries and a post-snapshot write; SQLite is not used to claim those
PostgreSQL guarantees. Cancellation preserves its original exception while resetting
request diagnostics. Interrupted builder cleanup is scoped to its operation's generated
file and refuses unexpected contents instead of deleting recursively.

No live AWS, production database or real investigative evidence was contacted. Private
backup encryption/off-host retention, confirmed private disclosure, approved licensing
and a separately authorized operational restore/deployment drill remain release work.
Direct S3 restoration, signed exports and browser UI automation are not claimed. Source
S3 behavior is tested through an in-memory fake. Restore requires exclusive operator
control of a fresh target; backups require schema changes and pruning to remain paused.

## Final continuation verification

The final reviewed application source was exported from the Git index into a new
temporary directory, excluding unrelated local work. With `APP_ENV=test`,
`M1_POSTGRES_TEST_URL` set to the dedicated localhost `provena_ci` database and
`M5_PG_BIN` selecting PostgreSQL 16.15 utilities, `python -m pytest -q` passed
**400 tests, no skips, in 382.72 s**. This supersedes the older 382-test snapshot;
it includes all six real PostgreSQL checks, archive/provenance validation, three hard
interruption/commit-boundary cases and M0-M4 regressions. The targeted command
`python -m pytest tests/test_m5_archive_attacks.py tests/test_m5_exports.py tests/test_m5_operations.py -q`
also passed all 65 tests.

The continuation reran `npm ci`, lint, typecheck, all **66 frontend tests**, production
build, `npm audit` and `npm audit --omit=dev`; every command succeeded, both audits found
zero vulnerabilities. `python -m pip check` and `python -m pip_audit -r backend/requirements.txt`
again succeeded with no broken requirements or known vulnerabilities. Dependency files
are unchanged from the clean Python environment installed earlier in M5. Read-only
preflight and `alembic check` again passed against the explicit disposable targets.

Final commit and exact workflow URL/conclusions are supplied in the implementation
handoff after the push. The [main CI history](https://github.com/shikhar-sahay/provena/actions/workflows/ci.yml?query=branch%3Amain)
contains the final revision's six required jobs. Candidate packaging must retain
`publishable=false`; neither a release/tag nor a production deployment is authorized.
Manual browser testing and independently authorized operational deployment/restore
drills remain prerequisites for public beta. Browser downloads buffer a bounded archive;
very large packages need client-memory planning as well as server disk capacity.
