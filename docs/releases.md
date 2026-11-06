# Prerelease validation and release checklist

The version is **0.1.0-beta.0**, an unpublished development prerelease. Backend
app/version.py is the version source; frontend metadata must match. Parser, adapter,
normalization and rule versions remain separate investigative identities. Never describe
passing CI as certification or public-release approval.

## Automated validation

Main/PR CI has eight jobs: Python dependencies, backend pytest, frontend component/lint/
type/build/npm audits, PostgreSQL migrations/concurrency/recovery, real Chromium workflows,
offline documentation checks, candidate validation and disposable Compose startup.
Candidate/container jobs are gated on the first six. No gate is weakened to pass a build.

The candidate job builds the frontend, compares an independent second build under the
same source/runtime/environment, packages committed allowlisted source and public web
assets, verifies inventory/digests, and uploads seven-day validation artifacts. The source
includes browser configuration/tests, synthetic fixtures and current guides. Runtime
evidence, environment files, backups, caches and local untracked documents are excluded.
High-confidence secret patterns fail packaging; this does not replace human review.

Candidate manifests record schema, source SHA, version, per-file SHA-256/size and known
publication blockers. They are unsigned and always `publishable=false`. No release/tag,
package publication, AWS deployment or infrastructure change is performed.

After committing and rebuilding frontend/dist with the intended environment:

```sh
python tools/check_docs.py
python tools/check_build.py
python tools/build_release.py --frontend frontend/dist --output /private/new-candidate.zip
```

Use a fresh output path. The E2E runner builds with ephemeral API ports; rebuild normally
before local packaging. CI candidates use a separate clean checkout. Reproducibility
checks cover identical environment builds, not arbitrary OS/compiler combinations.

## Engineering checklist

- Full backend/component/browser suites and audits pass on the exact intended revision.
- Fresh and populated prior-schema upgrades, alembic check and native restore pass on
  disposable PostgreSQL; SQLite is not concurrency evidence.
- Browser demonstration covers review, historical stability and offline verification of
  real downloads. Failure traces are synthetic, bounded by job limits and excluded from Git.
- README, investigator/operator/developer/security guides and changelog describe actual
  behavior. Relative links and Mermaid fence/declaration checks pass. Full diagram rendering
  and external URLs are not claimed to be checked by the lightweight documentation tool.
- Inspect explicit staged changes, release inventory and secret-pattern results. No real
  evidence, private backups, credentials or unrelated local work enter a candidate.
- Record source SHA, all job conclusions, limitations, migration compatibility and rollback
  procedure. Changes requiring rollback use a validated backup into fresh targets.

## Owner decisions, still blocked

- Choose and approve a license. No license existed at M5/M6 start; repository visibility
  does not create a license grant. The implementation does not invent one.
- Confirm a private vulnerability-reporting channel/contact. SECURITY.md explains safe
  reporting without inventing an email or response guarantee.
- Explicitly approve the public beta, release notes, tag and publication. CI is not approval.

## Operational prerequisites, separately authorized

The [M6 EC2 deployment assessment](deployment-readiness-m6.md) is the current gated
upgrade/rollback preparation document. The deployed revision and paths must be verified;
historical AWS examples are not a production inventory. In particular, choose a compatible
pre-upgrade backup strategy before running any migration. Deployment approval remains
separate from public-release, license and infrastructure approval.

Require sign-off of the [execution checklist](deployment-execution-checklist.md) before
any production action. The frozen deployment candidate is source 36763611139923236e981da6cd66beeae56145cf,
verified by CI #61; subsequent preparation commits are not an implicit replacement.
The CI candidate's actual bytes and manifest were checked locally. Rebuilding the
same source can change the archive hash; record the new digest instead of reusing an
old one. No production-consistent backup or real-baseline restore has been completed
by this assessment, so production execution remains gated.

The [Gate 1 proposal](gate1-recovery-plan.md) now specifies owner-controlled encrypted
PC recovery storage, owner-only key generation, existing-bucket ciphertext transfer
and fresh PostgreSQL restoration. Key/volume confirmation and execution approval are
still pending. Its tests and new documentation do not replace the frozen application
artifact. Gate 1 backup approval and Gate 2 deployment approval are distinct; resumed
legacy writes require a fresh final backup boundary before an approved upgrade.

- Select a staging environment, configure strong secrets/TLS/proxy/storage permissions
  and validate health with the actual deployment owner.
- Install encrypted off-host backup/retention procedures and complete a controlled restore
  drill. M5 tools exist; M6 does not provision a scheduler, encryption service or cloud.
- Approve and validate live migrations/deployment, rollback, monitoring, disk alerts,
  certificate renewal and EC2 capacity. No live load test or AWS access is authorized here.
- Perform manual browser/accessibility validation on target devices, and independent
  security/operational review appropriate to the sensitivity of intended evidence.

The current recommendation is in [M6 readiness](m6-implementation.md). Controlled local
synthetic evaluation is distinct from staging authorization and public-release readiness.
