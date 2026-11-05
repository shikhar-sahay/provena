# Development and browser testing

Use Python 3.13, Node.js 22 and PostgreSQL 16. Docker Compose is optional for native
setup and required for the container smoke test. No model or paid API is needed.
Read [architecture](architecture.md), [security](security.md) and [contribution rules](../CONTRIBUTING.md).

## Local application

`docker compose up --build --wait` starts the development DB/API/Vite stack, migrates its
own DB and checks readiness. Open http://localhost:5173, register and create a workspace.
Database, evidence and exports use distinct named volumes and loopback ports. Do not
remove volumes holding investigations. Do not use these demo credentials in a shared or
production deployment. Compose intentionally does not use a private production env file.

For native development, create a dedicated local database owned by your development
role. Activate a new virtual environment, install `backend/requirements.txt` and supply
`DATABASE_URL` through your private process environment. The application reads an optional
backend/.env only when launched from backend/, and process variables take precedence.
Never commit environment files. See [operations](operations.md) for configuration limits.

From the root, `python -m venv backend/.venv` creates the environment. Activate with
`backend/.venv/Scripts/Activate.ps1` on PowerShell or `source backend/.venv/bin/activate`
on POSIX, then run `python -m pip install -r backend/requirements.txt`. PostgreSQL role
and database creation require your local database administrator, not application seed
credentials. Keep application and test databases separate.

```sh
# From backend/, in the activated environment and with the local DATABASE_URL:
python -m alembic upgrade head
python -m alembic check
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# A second terminal, frontend/:
npm ci
npm run dev
```

The development Vite proxy forwards /api to localhost:8000 unless explicitly configured.
A production build uses VITE_API_URL at build time; blank selects same-origin /api. Do
not point local tests at a remote API. `scripts/dev.ps1` remains a Windows convenience
for local setup/seeding. Its explicit reset command destroys its development data and
is never required by browser tests or routine startup.

## Backend and frontend checks

```sh
# backend/
python -m pytest -q
python -m pip check
python -m pip install "pip-audit>=2.9,<3"
python -m pip_audit -r requirements.txt
# frontend/
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm audit
npm audit --omit=dev
# repository root
python tools/check_docs.py
git diff --check
```

Component tests live under frontend/src and use Vitest/jsdom. Playwright tests live
under frontend/e2e and are separately type checked; npm test never collects them.
PostgreSQL-specific pytest checks require M1_POSTGRES_TEST_URL targeting a dedicated
localhost provena_ci database and M5_PG_BIN pointing to matching native tools. Without
that explicit environment those checks skip, which is not PostgreSQL verification.
M5 recovery creates fresh randomly named databases and retains them for inspection.

## Real browser suite

Install frontend dependencies, then `npx playwright install chromium` from frontend/.
On Ubuntu use `npx playwright install --with-deps chromium`. The pinned Playwright release
is 1.64.1, including matching browser binaries. The latest test-package metadata briefly
referenced an unavailable core release during implementation, so this complete release
was selected rather than forcing an incompatible installation.

Create a dedicated localhost PostgreSQL **provena_ci** control database with a role
allowed to create/drop its own test databases. This must not contain application or
production evidence. Set the connection through M6_POSTGRES_TEST_URL, for example a
private `postgresql+psycopg2://...@127.0.0.1:5432/provena_ci` value.

One optional dedicated local control container (entirely synthetic, not the app DB):

```sh
docker run --name provena-browser-db -e POSTGRES_USER=provena_ci -e POSTGRES_PASSWORD=synthetic_local_only -e POSTGRES_DB=provena_ci -p 127.0.0.1:55482:5432 -d postgres:16-alpine
docker exec provena-browser-db pg_isready -U provena_ci -d provena_ci
```

After it is ready, use
`postgresql+psycopg2://provena_ci:synthetic_local_only@127.0.0.1:55482/provena_ci`
only for this loopback test container. These invented credentials are never production
defaults. Stop only this container when finished. Native PostgreSQL is also supported,
as demonstrated by the passwordless local test-cluster example below.

```powershell
# Windows example, local disposable cluster only, activated backend environment:
$env:M6_POSTGRES_TEST_URL = 'postgresql+psycopg2://provena_ci@127.0.0.1:55481/provena_ci'
python tools/run_e2e.py
# Focused rerun, still a fresh isolated application:
python tools/run_e2e.py --grep 'workspace isolation'
```

The Python runner refuses remote hosts, other control-database names and URL options.
It creates only a randomly named provena_e2e_UUID database, migrates it, builds the actual
frontend, starts loopback API/preview servers on temporary ports and uses private temporary
evidence/cache roots and a random signing secret. No existing server, database or env
file is reused. Teardown stops only owned processes and drops only that created database.
Browser contexts and fresh synthetic workspaces isolate tests; tests do not require order.
No privileged test endpoint is added to the application.

The main journey uses real APIs, adapters, detections, reports and browser downloads;
no responses are mocked. Only the named network-failure test aborts one download. Browser
requests to origins other than the owned web/API servers are rejected by the suite.
Traces/screenshots are retained on failure; HTML reports and synthetic metrics are under
ignored frontend/playwright-report and frontend/test-results. Artifacts can contain
**synthetic** tokens and records, never run this suite on real cases. CI retains them
seven days. Open a trace with `npx playwright show-trace PATH` from frontend/.

The runner rebuilds dist using its ephemeral API URL. Run `npm run build` again with
VITE_API_URL unset before manually packaging a same-origin release candidate. CI's
release job builds from its own clean checkout and never uses the browser job's dist.

## Failure diagnosis and migrations

A setup failure exits nonzero and retains setup.log/API logs in the ignored artifact
folder. Check PostgreSQL availability/role privileges, browser installation and Node/Python
versions. Ports are allocated locally; a binding race fails safely instead of reusing
another app. Missing control configuration refuses execution before application startup.
There are no arbitrary test sleeps; network/DOM assertions wait for observable outcomes.

Change models and add a new Alembic revision; never rewrite a published migration. Verify
fresh upgrades, populated prior-schema upgrades and alembic check on disposable PostgreSQL.
Update rule/parser/adapter identities when semantics change and preserve old reports and
reviews. See [release checklist](releases.md) and [M6 evidence](m6-implementation.md).
