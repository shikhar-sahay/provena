# Pre-release and release-validation policy

The internal version is `0.1.0-beta.0`. Backend `app/version.py` is the release-version
source of truth; frontend package metadata must match. This is a development pre-release,
not a published final release, certification or assurance of operational admissibility.

Every main/PR CI run preserves dependency, backend, frontend and PostgreSQL gates. After
all four pass, the reusable `release-validation` workflow builds a production frontend,
creates a bounded candidate from committed allowlisted source and compiled public assets,
verifies every artifact digest, and tests a fresh disposable Docker Compose database/API.
The candidate and JSON metadata are uploaded as a seven-day Actions artifact. No AWS
deployment, GitHub release creation or tag publication occurs.

Candidate construction uses `git archive HEAD`, not uncommitted working-tree source.
Private environment files, runtime evidence, backups, model files, generated caches and
untracked deployment documents cannot enter the allowlisted source artifact. Only the
explicit synthetic M3/M4 authentication datasets and M5 demonstration instructions are included. The candidate manifest
records application version, exact commit, file SHA-256 digests and publication blockers.
It is unsigned and marked `publishable=false` until explicit maintainer approval.

Reproduce after committing the intended source and building the frontend:

```sh
python tools/build_release.py --frontend frontend/dist --output /private/provena-candidate.zip
```

Do not reuse an existing output path. A new version requires a meaningful changelog,
passing CI on the exact release commit, tested schema upgrade and fresh restore, and
maintainer review of sensitive-file exclusions. Substantial schema/behavior compatibility
changes require explicit upgrade notes. Pre-release patch increments must still record
parser/rule/normalization versions independently; application version alone is not
investigative identity.

## Publication blockers

- No project license file existed at M5 start. The owner must choose and approve a
  license before describing a distributed beta as licensed open-source software.
  M5 does not make a legal licensing choice or add an invented grant.
- A private security-disclosure channel must be confirmed before a public beta. See
  `SECURITY.md`; no invented email address or response guarantee is supplied.
- A maintainer must explicitly approve any release/tag and independently authorize any
  production deployment. Passing tests or generating an artifact is not that approval.
- Real deployment ownership, backups, restore drill, storage capacity, secrets, TLS and
  monitoring must be validated through a controlled operations process. M5 never accessed
  or changed the live EC2/DuckDNS deployment.
