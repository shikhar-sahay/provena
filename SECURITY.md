# Security reporting and supported status

Provena is an experimental pre-release DFIR workbench, not certified forensic software.
Only the current maintained `main` is validated in CI; no long-term supported release or
response-time guarantee is established. Use synthetic or explicitly authorized evidence.

For a suspected vulnerability, use GitHub's private vulnerability reporting on this
repository's Security tab if it is enabled. The maintainer must confirm that channel
before public beta. If no private channel is available, open a minimal issue requesting
a private contact method without exploit details, credentials, real evidence or personal
data. No security email address has been designated in this repository.

A useful private report identifies the affected commit, synthetic reproduction,
preconditions, observed impact and suggested fix. Do not test the live deployment,
access other workspaces or upload real personal data to demonstrate a defect.

Hashes and unsigned manifests demonstrate internal integrity consistency. They are not
digital signatures or independent proof of provenance. Backup packages contain sensitive
database/account and evidence data; protect/encrypt them and never attach them to issues.
Do not post bearer tokens, database URLs or storage keys in logs/screenshots/issues.

The [current security architecture](docs/security.md) describes workspace/case boundaries,
export/restore threats and residual localStorage/unsigned-manifest limitations. M6 browser
tests use disposable synthetic systems and do not establish live-host or full WCAG/security
certification. Candidate secret-pattern scans are limited checks, not proof of no secrets.
