# M6 controlled deployment execution checklist

**Preparation only. Nothing here authorizes a production mutation.** Use the detailed
[readiness assessment and runbook](deployment-readiness-m6.md) and [operations guide](operations.md).
Do not execute unresolved placeholders or bypass an unchecked gate. No automatic EC2
deployment workflow exists. Record private paths/resource identities and approvals in
the owner's protected worksheet, not this public file.

The concrete [Gate 1 recovery proposal](gate1-recovery-plan.md) separates backup
authorization from deployment authorization. Preparation is approved; neither
production execution gate is approved at this handoff.

## Frozen decision record

- Production checkout: `9024ccd55c89c84876aeb5d7ea3b352f108fb5c1`.
- Production DB: PostgreSQL 16.15, `provena`, Alembic `9b6e5c4d3a21`.
- Application candidate: `36763611139923236e981da6cd66beeae56145cf`, CI #61 all eight jobs passed.
- Inner candidate ZIP SHA-256: `b43522ee5a86f6588daf9ba60c3ed906aab254e2f770af9b0e3a30dbfced5e03`.
- The later preparation commit must have passing CI but is not a moving deployment target.
- Target schema: `ee5b99eb5ce4`; application version `0.1.0-beta.0` remains unpublished.
- Workspace backfill is already applied. **Do not repeat it, seed users or stamp head.**

## A. Private worksheet and authorization, before maintenance

- [ ] Identify the exact existing host/region and approved SSM route privately; compare
  it to the observed Amazon Linux 2023.12 t3.micro. Never select a host by guessed IP.
- [ ] Record change owner, DB operator, reviewer, incident contact and rollback decision maker.
- [ ] Obtain Gate 1 approval for original-evidence access, writer fencing, native backup,
  encryption, existing-bucket ciphertext transfer and fresh isolated restore/migration.
  Explicitly include permission to resume only the unchanged legacy service after
  the verified boundary; proposed downtime budget is 15 minutes, not a duration promise.
- [ ] Before Gate 1, confirm the PC volume is encrypted, the owner-only recovery key
  has independent escrow, private targets have enough space, and a synthetic ciphertext
  transfer/key-recovery test can run before service interruption. Never share private keys.
- [ ] Obtain separate Gate 2 approval only after Gate 1 acceptance: final backup refresh,
  live migrations, configuration/service/frontend switch, synthetic smoke and rollback.
  Gate 1 approval never includes live schema or release changes.
- [ ] Agree RPO and what happens to writes after opening traffic; production RTO is unmeasured.
- [ ] Record OLD_RELEASE, OLD_PYTHON, NEW_RELEASE, NEW_PYTHON, API_SERVICE, SERVICE_USER,
  ENV_FILE, FRONTEND_ROOT, EVIDENCE_ROOT, EXPORTS_ROOT, TMPDIR and PG_BIN privately.
- [ ] Confirm current source/schema have not changed; inspect tracked checkout modifications
  without optional Git writes. Preserve all local changes and generated persistent material.
- [ ] Record protected secret/role/grant/configuration recovery references; never print values.
- [ ] Validate existing signing key privately. Preserve it unless rotation/session invalidation
  is explicitly approved. Confirm DB driver and role privilege split for migrations.
- [ ] Accept current workspace assignments; no new backfill approval is needed for this suffix.
- [ ] Check certificate expiry and approve a working renewal plan: installed renewal timer is
  disabled; do not assume another mechanism exists.

## B. Capacity and staged artifact, before downtime

- [ ] Verify the CI #61 candidate's trusted outer/inner hashes, manifest, exact commit,
  per-file inventory and publishable=false. Retain a verified private copy before expiry.
- [ ] Confirm this is the same-origin Node 22 CI build, not the E2E ephemeral-origin build.
- [ ] Prepare a separate release directory and Python 3.13 environment; do not overwrite
  the existing checkout/venv or run git pull in production.
- [ ] Resolve backend dependencies together, record the exact inventory, run pip check/audit
  in the approved build/rehearsal environment; do not force incompatible framework versions.
- [ ] Keep old source, dependency environment and static assets available for rollback.
- [ ] Check current DB/WAL/root/inode free space, evidence allocation and private backup
  destination; do not read original evidence until that separate access is approved.
- [ ] Approve measured budget: staged release+venv, DB/WAL/index growth, original copy,
  plaintext+encrypted backup, restore clone, private temp/cache and agreed reserve.
- [ ] Approve private disk-backed temporary storage. The observed /tmp is only about
  457 MiB tmpfs on a host with 913 MiB RAM; do not rely on swap to make it safe.
- [ ] Approve initial one-worker/low-concurrency operation, proposed 10 MiB uploads,
  64 MiB exports, 16 MiB export metadata and 24-hour retention with monitoring.
- [ ] Prepare exact HTTPS CORS origin, loopback proxy trust, preserved original root,
  separate private export root, disk TMPDIR, source BUILD_ID and LLM_ENABLED=false.
- [ ] Review index/API caching, old hashed-asset retention, multipart overhead and 120 s
  synchronous timeout behavior. With a 10 MiB cap the existing 100M proxy limit fits.

## C. Legacy final backup and rehearsal, separate authorized stage

The source is older than the M5 head. **Do not invoke the current M5 backup CLI on it
and do not migrate first just to make backup work.** The native legacy procedure is in
section 7 of the runbook; it requires total writer exclusion.

- [ ] Isolate traffic and stop/fence every API/CLI/external writer, pruning and schema job.
  Nginx maintenance alone does not stop localhost writers.
- [ ] Resolve running/ambiguous operation state and record the final rollback boundary.
- [ ] Create a fresh private output destination outside Git, web and original-storage roots.
- [ ] Use matching PostgreSQL 16.15 native utilities and a privately configured connection;
  create a custom-format dump without placing passwords in arguments or logs.
- [ ] Copy the complete quiesced original storage with preserved keys and required metadata;
  include any discovered legacy persistent generated files. Do not follow escaping links.
- [ ] Reconcile DB-referenced originals/digests and report hashes with the copy; record the
  source/schema, inventory and trusted digests in a private manifest/record.
- [ ] Keep separate approved recovery material for secrets, roles/ACLs, service/proxy and TLS.
- [ ] Encrypt using the approved method, copy to an approved off-host destination, verify
  transfer/decryption and independently retain trusted hashes and key-recovery references.
- [ ] Confirm retention/deletion protection and responsible operator; an S3 prefix, SSE-S3
  policy or EBS encryption is not proof of a current complete backup.
- [ ] Restore the legacy dump and evidence into fresh isolated DB/storage targets, never
  over existing objects. Trusted native restore executes SQL and must remain private.
- [ ] Compare pre/post inventories, original digests, accounts/workspaces/cases, custody,
  decisions and immutable report hashes; check authorization using approved test credentials.
- [ ] Rehearse the six forward migrations on the clone and alembic check; measure disk/RSS,
  locks and duration. Keep real data out of CI and browser synthetic fixtures.
- [ ] Sign off backup consistency and real-baseline recoverability. If either fails, abort.

## D. Conditional upgrade, only after Gate 2 and all readiness gates are signed

- [ ] Confirm owner execution approval and maintenance are still valid; update the final
  consistent backup if writers resumed after rehearsal. Never use an outdated boundary silently.
- [ ] Verify exact new artifact/venv and proposed environment privately, configuration-only
  preflight first. Full M6 readiness is expected to fail against the unmigrated old schema.
- [ ] Ensure no old backend will restart during migration; check writer fencing again.
- [ ] Record current Alembic revision and apply only this suffix with approved lock/time budgets:

```text
b72a1e84c903 -> c83d2f95a014 -> d94e30a6b125
  -> 294d21d0205e -> 53d6b8a0e88b -> ee5b99eb5ce4
```

- [ ] Require sole head ee5b99eb5ce4 and no schema drift; do not downgrade or stamp on failure.
- [ ] Confirm old report hashes/decisions and evidence/custody metadata remain unchanged;
  missing old support remains historical and normalized events are not invented.
- [ ] Apply only approved production configuration corrections, especially HTTP-localhost CORS.
- [ ] Switch the retained systemd release/venv and static frontend together using the reviewed
  mechanism, preserving original storage and old assets. Reload units/proxy only if approved.
- [ ] Run private preflight --database --storage and verify BUILD_ID/source, real temp
  filesystem, permissions, no incomplete-restore marker and liveness/readiness JSON.
- [ ] Validate local API first, then HTTPS/TLS routing, SPA deep links and API error types.
- [ ] Keep public writes fenced until the following smoke checks and reviewer acceptance.

## E. HTTPS post-deployment smoke and observation

- [ ] Login/logout/refresh and workspace selection work; invalid credentials fail safely.
- [ ] Workspace/case roles, suspension, analyst restrictions and nonmember denials hold.
- [ ] Historical reports/digests/custody are preserved; no private data enters screenshots/logs.
- [ ] In a dedicated synthetic case, upload/verify Linux, Windows Security and Sysmon fixtures.
- [ ] Create profiles, ingest, inspect coverage, filter/page and reingest without duplicate activity.
- [ ] Select explicit event sets, execute five detection families, inspect limitations and support.
- [ ] Timeline uncertainty lanes and account/IP/host pivots work without invented session links.
- [ ] Accept/reject with annotations; identical reruns retain identities and review state.
- [ ] Generate accepted-only deterministic reports; historical report hashes remain unchanged.
- [ ] Download metadata and explicitly selected synthetic-original exports; run the offline verifier.
- [ ] Test history/retry/expiry feedback without tampering with real production evidence.
- [ ] Check API/static cache behavior, configured upload limit and bounded long operations.
- [ ] Observe RSS, swap activity, DB/cache/temp/disk growth, readiness, latency and safe error logs
  against the agreed thresholds. A lost response requires history inspection before retry.
- [ ] Reviewer authorizes traffic restoration; retain old assets/rollback material through
  the agreed observation period and explicitly approve synthetic-account cleanup later.

## F. Abort and rollback

- [ ] Abort before migration for backup/hash/decryption/rehearsal failure, insufficient
  space, unidentified schema, drift, unsupported dependencies or invalid configuration.
- [ ] Keep writers fenced for migration/startup/readiness/auth/evidence/history regression.
- [ ] Before schema mutation, code-only rollback requires proof that DB/storage/config are
  unchanged. After mutation, never point old code at the new schema.
- [ ] Restore the verified old DB, matching old application/config and originals into
  fresh targets; no --clean, drop/reset of existing data or blind alembic downgrade.
- [ ] Keep failed targets offline, preserve diagnostic/history material and account for any
  accepted post-boundary writes according to the approved RPO decision.
- [ ] Verify inventory, permissions, original digests, custody, decisions and report hashes
  before selecting the recovered roots/DB and matching old frontend/backend.
- [ ] Revalidate local then HTTPS health/auth/authorization. Obtain traffic-restoration approval.
- [ ] Any new-host/IP/DNS/storage migration requires separate approval; none is implied here.

## Sign-off state at preparation handoff

| Gate | State |
| --- | --- |
| A: inventory | Largely resolved through authorized read-only inspection |
| B: compatibility | Exact suffix established; synthetic migration/native recovery tested; real-baseline rehearsal outstanding |
| C: consistent backup | BLOCKED until an authorized verified production backup exists |
| D: recoverability | BLOCKED until that baseline is restored successfully in isolation |
| E: capacity | CONDITIONAL on disk-backed temp, limits, measured rehearsal and reserve acceptance |
| F: configuration | Corrections prepared, not applied; renewal mechanism acceptance outstanding |
| G: owner approval | BLOCKED; no production execution authorized by this document |

Overall: **NO-GO for immediate deployment.** The minimum next action is an explicitly
authorized legacy backup and isolated restore/upgrade rehearsal, followed by gated
configuration/service switching only after acceptance. Release/tag/license approval
and AWS infrastructure changes remain separate decisions.
