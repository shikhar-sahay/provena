# M6 prerelease hardening and real-browser verification

## Scope and implemented architecture

M6 preserves the modular monolith, PostgreSQL, exact verified evidence snapshots,
immutable source interpretations, stable reviewed findings and deterministic reports.
No production access, deployment, public release, tag or license choice is performed.
M5 baseline is 31825e0decf71364fa18420698a68127da1f07bc, verified by CI #57.

Playwright 1.64.1 is pinned with matching browser binaries. tools/run_e2e.py creates a
randomly owned localhost PostgreSQL database, applies real migrations, builds the real
frontend, launches loopback API/preview processes and private temporary evidence/cache
roots, and runs Chromium. It refuses remote/ambiguous control targets and does not reuse
an application server. Teardown stops only owned processes before removing private
storage and dropping only the database created by that invocation.

The suite is independent of Vitest, separately type checked, uses observable response/DOM
waits and accessible selectors, and retains synthetic failure screenshots/traces. Browser
requests are restricted to owned local origins. Every test creates its own account/case
state; no execution order is required. No privileged test endpoint or mocked main workflow
is introduced. One explicit download-failure scenario aborts a network request.

## Browser coverage

- Registration, workspace creation, invalid login, session refresh/persistence, logout,
  narrow screens and nonexistent-case feedback.
- Real upload, registration, SHA-256 verification, source configuration and all three
  Linux/Windows Security/Sysmon adapters using existing M4 synthetic fixtures.
- Explicit 51-event selection, all five detection families, support provenance, uncertainty
  lanes, IP pivot, annotations, acceptance/rejection and immutable selected-set reporting.
- Duplicate ingestion and reruns preserving event identities and reviewed finding states.
- Metadata and explicitly selected originals exports, browser downloads and real offline
  verifier execution. Completed recovery does not delete the package; a failed browser
  download retries the same operation without duplicate registration.
- Case nonmembership, analyst review/report/original-export rejection, archived mutation
  restriction, suspension, workspace switching and unrelated workspace access.
- Keyboard dialog entry/focus/escape and a 1000-event filtering/pagination workload with
  at most 50 rendered table rows. Synthetic metrics attach to the browser report.

Expired caches, storage/DB failure injection, tampered evidence, commit interruption,
restore safety and broader cross-workspace conditions remain covered by backend tests.
They are not falsely described as browser-induced storage failures.

## Demonstrated fixes

- Evidence detail previously enabled verification for analysts despite a backend 403.
  It now disables the action and explains role/archive restrictions; backend enforcement
  remains the security boundary. Component and browser regression tests cover this.
- Legacy artifact-analysis initiation and rule-evaluation controls now follow the same
  case-management/assigned-analyst and archived-state predicates as the backend. A
  workspace investigator assigned only as a case reader no longer sees usable write
  actions. Four additional component cases and the role-switch browser scenario verify it.
- Account menu now exposes Switch workspace, reusing the existing onboarding selector.
  Previously there was no ordinary app navigation to that implemented workflow.
- The narrow-screen creation action now has the full accessible New investigation name.
- A review completing after the user closed/pivoted away could reopen a finding drawer,
  block clicks and inject stale history errors. Review/history generation checks now
  preserve dismissal; a deferred-response component regression and real review flow cover it.
- Clean Linux CI exposed a missing direct Node type dependency that an ancestor local
  install masked. Node 22 type definitions are now explicitly pinned, so browser/config
  type checking does not depend on packages outside the checkout.

Separate shared predicates preserve the backend distinction between analysis/ingestion
and finding/detection production. A case owner with a custodian workspace role cannot
initiate parsing, but retains finding-production authority where the existing case-manager
policy permits it. Nine capability cases protect this distinction without changing APIs.

No backend authorization vulnerability was confirmed in the exercised paths. New tests
prove that IDs from a second authorized case still cannot cross export/event/history
boundaries. Existing M0-M5 integrity and concurrency checks remain required.

## Performance and reliability

The new browser workload generates 1000 explicit-UTC SSH records without real identities.
It measures ingestion/first render and pagination, asserts exact filtering and a 50-row
DOM bound, and does not impose a fragile hardware timing threshold. A backend query-count
regression uses 300 events: local SQLite observed 11 statements for a 50-item page and
10 for a 200-item page, so response size does not cause per-event query growth. This is
not PostgreSQL production capacity evidence. M5's 2000-event/16 MiB export benchmark and
native recovery measurements remain historical observations, not EC2 guarantees.

On the local Windows/i5-13420H/16 GB system with PostgreSQL 16.15 and Chromium, the
1000-event browser scenario completed in 7.6-11.1 s in representative runs. That
includes account/case creation, upload, verification, profile configuration, ingestion,
pagination and filtering, not just parser CPU time. The full browser suite took about
1.3-1.7 minutes under concurrent verification load. No RSS or EC2 capacity measurement is
claimed. Repeated default frontend builds matched all 27 file hashes. Vitest workers
are capped at four to avoid oversubscribing ordinary local hardware; test isolation and
assertions remain enabled.

Synchronous operation histories, idempotent retries and bounded parser/export limits are
preserved. Request cancellation does not imply rollback of a synchronous worker; inspect
history before creating another operation. No distributed queue is added.

## Documentation and release validation

README, architecture, developer, investigator, operator, security, contributor, disclosure,
release and changelog documents now form a current-guide hierarchy. Milestone and AWS
records are explicitly historical, not live deployment claims. tools/check_docs.py checks
tracked relative-file links and Mermaid fences/declarations offline; it does not claim
full Mermaid rendering, external-link validity or semantic documentation proof.

CI adds real browser and documentation jobs before candidate/container validation.
Candidate packaging excludes private runtime paths, tests same-environment frontend build
reproducibility and scans high-confidence private-key/AWS/GitHub-token patterns, including
chunk boundaries. Leak detection is limited; explicit human staging/artifact review remains
mandatory. Candidates remain unsigned validation artifacts and publishable=false.

## Readiness and remaining decisions

**Controlled local beta evaluation:** appropriate with synthetic/authorized data and
stated processing limits, subject to successful final gates recorded below.

**Staging:** engineering tooling supports preparation, but an operator must separately
approve/provision the environment, secrets, TLS/proxy, backup retention and restore drill.
No actual staging deployment is claimed.

**Public release:** blocked on owner-approved licensing, confirmed private security
reporting, explicit release approval and operational/security validation. Passing CI does
not resolve legal or live-environment prerequisites.

Technical limits remain: Chromium-only automation, no browser/OS coverage matrix or full
WCAG audit; unsigned hash manifests; local restore targets with synthetic S3 testing;
bounded synchronous operations; localStorage bearer-token exposure if XSS occurs; explicit
operator scheduling/encryption/off-host backup responsibilities. Large browser downloads
buffer a bounded archive. Native EVTX, OCR, a trained anomaly engine, automated remediation
and an enterprise SIEM are outside this release.

## Verification record

Implementation commit: `a0093946f95109cf395294af7a0ae36de1ca780e`. Its code and tests
were exported from the reviewed Git index into a clean temporary directory, excluding
unrelated local changes. The final source/CI SHA is supplied in the implementation handoff.

| Command/check | Actual local outcome |
| --- | --- |
| `python -m pytest -q`, clean exported backend with dedicated PostgreSQL enabled | 416 passed, zero skips, 408.16 s |
| `python -m pytest tests/test_m6_tools.py tests/test_m6_boundaries.py -q` | 16 passed |
| `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` | Passed; 84 component tests in 26 files; browser/config TypeScript also checked |
| `python tools/run_e2e.py` | Six Chromium scenarios passed, real PostgreSQL/API and production-built frontend |
| `python -m pip check`, `python -m pip_audit -r backend/requirements.txt` | No broken requirements or known vulnerabilities |
| `npm audit`, `npm audit --omit=dev` | Zero vulnerabilities |
| `python tools/check_build.py` | All 27 frontend file hashes match an independent same-environment build |
| `python tools/check_docs.py` | 29 tracked Markdown documents, zero missing-file/fence/declaration errors |
| Release packaging on the implementation commit | 329 files, 5044090 bytes, verified unsigned manifest and private-path/secret checks; not publishable |
| `git diff --check` and explicit staging review | Passed; unrelated environment/private documents excluded |

The full backend result includes six real PostgreSQL checks: fresh/populated upgrades,
schema drift, concurrent registration/ingestion/export/detection behavior and native
backup/restore with preserved report hashes/decisions. No new migration is required;
the current head remains `ee5b99eb5ce4`. CI runs PostgreSQL checks in a separate job,
so its ordinary backend job reports those six as skipped rather than claiming SQLite
verified them. Two expected backend warnings remain: Starlette's test-client deprecation
and the deliberate duplicate-entry hostile ZIP fixture. The frontend still warns about
the approximately 505 kB main bundle; no security/check gate is suppressed.

See [development](development.md) for reproducible commands and [release checklist](releases.md)
for owner/operator prerequisites. CI must pass on the final pushed commit, including all
eight jobs, before this milestone is handed off. The exact run URL/conclusions accompany
the final report; [main CI history](https://github.com/shikhar-sahay/provena/actions/workflows/ci.yml?query=branch%3Amain)
provides the persistent revision-indexed record. Live AWS/EC2/S3, real evidence and manual
target-device/WCAG evaluation remain unverified and were not accessed.

An intermediate CI #58 successfully ran browser, documentation, dependency and PostgreSQL
checks but exposed the missing direct Node type dependency. It was not reported as green.
The fix pins @types/node 22.20.5 and is validated with a fresh npm ci and full frontend
gates before the final push. Final CI must verify the corrected revision; an earlier
successful browser job is not substituted for that result.

CI #59 passed dependency, backend, frontend, documentation and PostgreSQL jobs,
but its browser dependency installation stalled for over ten minutes before test
execution. It was superseded by a revision bounding browser setup to ten minutes
and the entire browser job to twenty-five minutes. Timeouts fail the gate; no test
or dependency validation is skipped to conceal infrastructure failure.
