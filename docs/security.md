# Security architecture and limits

This describes repository controls and synthetic verification, not a live deployment
attestation or forensic certification. See [disclosure policy](../SECURITY.md) and
[release blockers](releases.md).

## Threat model and boundaries

The important boundaries are browser to authenticated API, active workspace to case
membership, database metadata to evidence storage, untrusted evidence to bounded parsers,
analytical support to human review, and private backups to an explicitly trusted restore.
Protect confidential records against unauthorized users, accidental cross-case references,
malformed input, mutable storage, interrupted operations and operational mistakes.
A privileged database/filesystem administrator remains outside application-level
append-only guarantees. SHA-256 manifests are not independent authentication.

| Boundary | Backend behavior |
| --- | --- |
| Global account / workspace | Workspace administrators can suspend membership, not globally disable a shared account |
| Workspace / case | Active selected workspace membership plus case team membership or workspace administration |
| Case mutation | Case creator/lead or workspace administrator; assigned analysts/custodians have narrow capabilities |
| Verification | Case manager or assigned evidence custodian, with archived-case restrictions |
| Findings and reports | Managers review findings and generate reports; explicit event sets for authentication conclusions |
| Case exports | Readers may export metadata; original bundles require management permission and explicit verified files |
| Restore | Maintainer CLI only, trusted package hash, fresh isolated DB/storage and full validation |

Last-active-administrator protections lock the workspace on PostgreSQL. Surviving case
membership cannot bypass workspace suspension. Same-name accounts in different domains
or hosts are not merged. Case-scoped IDs from another case fail even when a caller can
access both cases. Role changes may require a browser refresh to update controls; API checks remain immediate.
UI controls do not replace backend authorization; nonexistent and
inaccessible investigations normally share a 404 response.

## Authentication and browser behavior

Passwords use bcrypt; bearer JWT signing secrets and lifetime are configured through the
environment. Production rejects default/weak secrets, unsafe HTTPS CORS origins, broad
proxy trust and non-PostgreSQL URLs. Public health responses omit private connection data.
Proxy/TLS/DNS correctness requires operator validation outside application preflight.

Tokens remain in localStorage and are readable by page JavaScript if XSS occurs. They
are not HttpOnly cookie sessions. Bearer authorization is explicit, so cross-site requests
do not automatically gain cookie credentials; CORS is not authorization. No claim of
complete brute-force protection, perfect revocation or protection against a compromised
browser is made. Logout/session refresh, invalid login and workspace boundaries are
browser-tested. A future cookie/session redesign requires explicit compatibility/security
work, not a silent change in M6.

## Evidence, custody and analysis

Registration creates immutable SHA-256 baselines under generated storage keys. Ready,
verified evidence is independently copied and hashed for analysis/ingestion and original
exports; the same private snapshot is consumed. Historical flags alone do not satisfy
integrity. Missing/mismatched bytes block relevant operations and retain verification
history. Storage paths are absent from ordinary API/case-export metadata.

Parsing, record counts, input sizes, output rows and execution results are bounded.
Coverage, omitted results and unsupported temporal comparisons remain explicit. Timestamp
assumptions do not become source facts. Deterministic rules describe observed patterns,
not guilt or compromise probability. Authoritative reports use templates and exact
accepted current findings; legacy Ollama availability does not enable model allegations.

Custody/audit rows have no ordinary modification endpoints. They are application-level
append-only records, not cryptographic signatures or certified legal chain of custody.
Immutable report hashes detect inconsistency, not who authored the database state.
[Evidence integrity](evidence-integrity.md) details the exact-byte contract.

## Export and backup security

ZIPs use generated paths and bounded disk-backed construction. The standard-library
verifier does not extract or execute package data. It validates versioned provenance,
explicit selections, file inventory, digests, report hashes and original references;
unsafe paths, duplicate entries/keys, links and decompression-budget violations fail.
An attacker who can replace both data and unsigned hashes can forge consistency, which
is why independent trusted hash references and access controls remain necessary.

Exports can contain confidential excerpts even without originals. Downloads reauthorize
and copy/check the archive before streaming. Only complete, unexpired packages download.
Recovery preserves nonexpired completed artifacts. Client disconnects can leave a completed
or recoverable operation; inspect history before generating another export.

System backups contain all application accounts/hashes and evidence. Protect/encrypt them
outside the tool; keep independent trusted whole-package digests. An exported PostgreSQL
snapshot binds the native dump, metadata fingerprints and baseline-verified originals.
Pause DDL/pruning and keep restore targets exclusively offline. Trusted restore executes
native database definitions intentionally; never restore unknown third-party SQL or case
exports as backups. Existing user objects/roots are refused, and an incomplete marker
blocks readiness until restored fingerprints and report hashes match.

## CI and residual risks

CI audits Python requirements and both npm dependency sets without blanket ignores.
Release packaging uses a committed-source allowlist, rejects private runtime paths and
scans high-confidence private-key/AWS/GitHub-token patterns, including chunk boundaries.
This is a limited leak check, not proof that arbitrary secrets cannot be present. Review
staged diffs and artifacts. Ignore rules do not protect already tracked files or force-adds.

Browser tests use only randomly owned localhost databases and private synthetic storage.
Failure traces may contain short-lived synthetic tokens; artifacts expire after seven days.
No real case may be used with this harness. Docker startup, migrations and browser jobs
run on disposable CI infrastructure; passing them does not validate the AWS host.

Operators still own OS patching, reverse-proxy headers, TLS renewal, encryption, backups,
retention, monitoring, disk capacity, access review and independent security assessment.
No live AWS/S3, production database or personal evidence was tested in M6.
