# Development Guide

## Prerequisites

Python 3.13+, Node 22+, Docker + Docker Compose.

## Canonical local workflow (Windows PowerShell)

`scripts/dev.ps1` is the single entry point for native development
(Docker Postgres on host :5433, backend and frontend from source):

```powershell
./scripts/dev.ps1 setup    # db, venv, dependencies, migrations, user seed
./scripts/dev.ps1 demo     # optional synthetic demo investigation
./scripts/dev.ps1 api      # backend on :8000 with reload (new terminal)
./scripts/dev.ps1 web      # frontend on :5173 (new terminal)
./scripts/dev.ps1 health   # check API health and db container
./scripts/dev.ps1 reset -Force   # wipe the dev database and reseed
```

`setup` creates `backend/.venv`, installs dependencies, starts Postgres,
applies migrations, runs the user seed, and writes `backend/.env` with local
defaults (created once, never overwritten). The backend resolves
`DATABASE_URL` from the process environment first, so either export it or
rely on `backend/.env`.

Full-container alternative: `docker compose up --build` (db :5433,
api :8000, web :5173). The two paths use different databases; do not mix them.

## Manual setup (without the script)

```powershell
docker compose up -d db
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
$env:DATABASE_URL = "postgresql+psycopg2://provena:provena@localhost:5433/provena"
# from backend/:
python -m alembic upgrade head
python -m app.seed
```

Open `http://localhost:5173` (frontend) and
`http://localhost:8000/api/health` (backend health).

## Development users

The user seed (`python -m app.seed`) creates one login per role. It is
idempotent: safe to rerun.

| Username       | Role               |
| -------------- | ------------------ |
| admin          | Admin              |
| investigator   | Investigator       |
| analyst        | Forensic Analyst   |
| custodian      | Evidence Custodian |

The password defaults to `provena-dev` and can be overridden with the
`SEED_DEV_PASSWORD` environment variable. **Local development only.**
Never use these credentials anywhere shared or production-like.

## Demo investigation (optional)

`python -m app.seed_demo` (from `backend/`, after the user seed) builds the
fictional "Suspected Internal Data Exfiltration" investigation from
`sample-data/*.log` using only real application services: registration with
genuine SHA-256 baselines, verification runs, a custody transfer, team
membership, and an in-progress status. Every record, digest, and audit entry
is real; no AI output is fabricated. Idempotent: reruns detect the existing
demo investigation by title and stop. Refuses to run with
`APP_ENV=production`.

## Running services without Docker

Prefer `./scripts/dev.ps1 api` and `./scripts/dev.ps1 web`. The manual
equivalent:

```powershell
# Backend (from backend/, venv active or via .venv/Scripts/python.exe)
pip install -r requirements.txt
python -m uvicorn app.main:app --reload   # serves :8000

# Frontend (from frontend/)
npm install
npm run dev                               # serves :5173, proxies /api to the backend
```

Use `python -m` entry points (not global `alembic`/`uvicorn` installs) so the
project virtualenv is always the interpreter. The backend needs no database
to start: `/api/health` reports `"db": "not_configured"` until `DATABASE_URL`
is set.

## Environment variables

| Variable              | Used by | Default (dev)                                  |
| --------------------- | ------- | ---------------------------------------------- |
| `APP_ENV`             | Backend | `development` (`production` blocks the seed)   |
| `DATABASE_URL`        | Backend | `postgresql+psycopg2://provena:provena@localhost:5433/provena` |
| `CORS_ORIGINS`        | Backend | `http://localhost:5173`                        |
| `SECRET_KEY`          | Backend | dev-only default; set a real value if shared   |
| `SEED_DEV_PASSWORD`   | Seed    | `provena-dev` (local development only)         |
| `EVIDENCE_STORAGE_ROOT` | Backend | `./evidence-storage` (`/evidence` in Compose) |
| `EVIDENCE_MAX_UPLOAD_BYTES` | Backend | `104857600` (100 MiB)                    |
| `VITE_API_URL`        | Frontend| `http://localhost:8000` (dev proxy covers `/api` anyway) |

See `.env.example`. Never commit `.env` or any secrets.

## Tests, lint, formatting

```powershell
python -m pytest                     # from backend/ (SQLite-backed, no Postgres needed)
npm run lint                         # from frontend/
npm run typecheck                    # from frontend/
npm test                             # from frontend/ (vitest behavior tests)
npm run build                         # from frontend/ (production build)
```

Backend evidence tests override `EVIDENCE_STORAGE_ROOT` with a temporary
directory, so test uploads never touch real storage.

CI (`.github/workflows/ci.yml`, pinned to `ubuntu-24.04`) runs backend
tests plus frontend lint, tests, and build on every push/PR. Recent runs #4-6
failed with GitHub-hosted runner acquisition errors and an internal server
error; those are GitHub infrastructure failures, not Provena failures.

## Database migrations (Alembic)

Migrations live in `backend/alembic/versions/` and read `DATABASE_URL`
from the app settings (process environment first, then `backend/.env`).

```powershell
python -m alembic upgrade head       # from backend/
python -m alembic downgrade base     # roll everything back (dev databases only)
python -m alembic revision --autogenerate -m "describe change"
```

Use `python -m alembic` (not a global install) so migrations run against the
project virtualenv. Backend tests use throwaway SQLite databases; Alembic
remains the only schema-management strategy for PostgreSQL.

## Evidence storage

- Local filesystem storage under `EVIDENCE_STORAGE_ROOT`. Files are addressed
  by generated internal keys; the database holds digests and metadata.
- Uploads are capped by `EVIDENCE_MAX_UPLOAD_BYTES` (default 100 MiB) and
  empty files are rejected.
- In Docker Compose, the API service mounts the `provena_evidence` volume at
  `/evidence`. Runtime uploads are git-ignored; synthetic demo logs live in
  `sample-data/` and can be registered as evidence for walkthroughs.

## PostgreSQL ports

Provena's Docker database publishes **host port 5433** (container port 5432),
because many machines already run Postgres on 5432. The internal Compose
service still uses `db:5432`; only the host mapping differs. Local (non-Docker)
runs use `localhost:5433` via `DATABASE_URL`.

## Docker workflow

- `docker compose up --build` — full local stack.
- `docker compose up db` — only Postgres (run API/web from source).
- `docker compose down -v` — stop everything and delete the dev database volume.
- `docker compose config` — validate the Compose file without starting anything.

## Local URLs

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/api/health`
- Backend API: `http://localhost:8000/api/...`
- Postgres: `localhost:5433` (user/password/db: `provena`)

## Troubleshooting

- **Backend can't reach Postgres:** check `DATABASE_URL` host (`localhost` for
  local runs, `db` inside Compose), the port (5433 on the host), and that the
  `db` container is healthy.
- **"Port is already allocated" for 5433:** another service uses it; remap the
  host port in `docker-compose.yml` and update `DATABASE_URL` to match.
- **Frontend shows a sign-in error:** the UI distinguishes causes. "Invalid
  username or password" means credentials; "Cannot reach the Provena backend"
  means the API is not running (start it, then verify
  `http://localhost:8000/api/health` directly).
- **401 after seed:** you may be logging in with the wrong password; rerun the
  seed or check `SEED_DEV_PASSWORD`.
- **Stale frontend deps in Docker:** the `web` service mounts `./frontend`, but
  `node_modules` lives in an anonymous volume; run `docker compose build web`
  after dependency changes.
