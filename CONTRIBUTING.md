# Contributing to Provena

Read `AGENTS.md`, the architecture guide and evidence-integrity contract before changing
behavior. Preserve the modular monolith, deterministic reasoning, exact verified inputs,
workspace isolation and human review. Propose substantial work through an issue/PR.

Use feature branches for external contributions and focused conventional commits.
Describe the observed problem, final behavior, relevant tests and limitations. Include a
forward-only Alembic migration for schema changes; never rewrite published migrations.
Parser, adapter, rule or identity changes require semantic-version and provenance tests.

Run backend pytest, frontend lint/typecheck/tests/build, dependency audits and
`git diff --check`. PostgreSQL-specific behavior requires the disposable database checks;
SQLite alone does not establish concurrency or migration compatibility. See operations
and milestone docs for synthetic fixtures and safe targets.

Use invented identities and documentation IP ranges. Do not submit real cases, tokens,
private evidence, environment files, dumps, backup archives or model artifacts. Reproduce
security failures using synthetic data and use `SECURITY.md` for sensitive disclosure.
No user evidence is needed for a useful bug report.

Document behavior changes and supported limits. Keep authoritative reports deterministic,
preserve old report hashes, and distinguish observed patterns from malicious intent.
Use existing design tokens and accessible primitives. Project-authored text does not use
Unicode U+2014. Explain what could not be verified instead of claiming a check passed.

Licensing is an open owner decision before public-beta distribution. Contributions must
not introduce third-party material without permission or invent a project license grant.

## Browser, documentation and release checks

Read the [developer guide](docs/development.md) and run the real browser suite through
`python tools/run_e2e.py` with a dedicated localhost control database. Never point it at
an existing application or real evidence. Keep component and E2E tests separate and add
regressions for material UI/integration fixes. Do not mock the principal investigation
journey. Prefer accessible selectors and observable network/DOM waits over sleeps.

Run `python tools/check_docs.py` after explicitly staging new guides so links are checked
against tracked source. Update the [investigator guide](docs/investigator-guide.md) when
UI workflows change. Preserve historical milestone measurements instead of silently
replacing them with new results. Mermaid fence checks are not complete syntax rendering.

Release validation compares frontend builds and scans high-confidence secret patterns,
but human artifact/diff review remains necessary. Synthetic browser traces/downloads are
ignored test artifacts, never source or candidate inputs. See [release policy](docs/releases.md).
