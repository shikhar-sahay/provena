# Development Guide

## Prerequisites

Python 3.13+, Node 22+, Docker + Docker Compose.

## First-time setup

```bash
cp .env.example .env        # .env is git-ignored; adjust values if needed
docker compose up --build   # db :5433, api :8000, web :5173
```

Then, with the database running, apply migrations and create logins:

```bash
# from backend/ (DATABASE_URL must point at the database, see below)
alembic upgrade head
python -m app.seed
```

Open `http://localhost:5173` (frontend) and
`http://localhost:8000/api/health` (backend health).

## Development users

The seed creates one login per role. It is idempotent: safe to rerun.

| Username       | Role               |
| -------------- | ------------------ |
| admin          | Admin              |
| investigator   | Investigator       |
| analyst        | Forensic Analyst   |
| custodian      | Evidence Custodian |

The password defaults to `provena-dev` and can be overridden with the
`SEED_DEV_PASSWORD` environment variable. **Local development only.**
Never use these credentials anywhere shared or production-like.

## Running services without Docker

```bash
# Backend (from backend/)
pip install -r requirements.txt
uvicorn app.main:app --reload        # serves :8000

# Frontend (from frontend/)
npm install
npm run dev                          # serves :5173, proxies /api to the backend
```

The backend needs no database to start: `/api/health` reports
`"db": "not_configured"` until `DATABASE_URL` is set.

## Environment variables

| Variable              | Used by | Default (dev)                                  |
| --------------------- | ------- | ---------------------------------------------- |
| `APP_ENV`             | Backend | `development` (`production` blocks the seed)   |
| `DATABASE_URL`        | Backend | `postgresql+psycopg2://provena:provena@localhost:5433/provena` |
| `CORS_ORIGINS`        | Backend | `http://localhost:5173`                        |
| `SECRET_KEY`          | Backend | dev-only default; set a real value if shared   |
| `SEED_DEV_PASSWORD`   | Seed    | `provena-dev` (local development only)         |
| `VITE_API_URL`        | Frontend| `http://localhost:8000` (dev proxy covers `/api` anyway) |

See `.env.example`. Never commit `.env` or any secrets.

## Tests, lint, formatting

```bash
python -m pytest                     # from backend/ (SQLite-backed, no Postgres needed)
npm run lint && npm run typecheck    # from frontend/
npm run build                         # from frontend/ (production build)
```

CI (`.github/workflows/ci.yml`) runs backend tests plus frontend
lint and build on every push/PR.

## Database migrations (Alembic)

Migrations live in `backend/alembic/versions/` and read `DATABASE_URL`
from the app settings.

```bash
alembic upgrade head                 # from backend/
alembic downgrade base               # roll everything back (dev databases only)
alembic revision --autogenerate -m "describe change"
```

Backend tests use throwaway SQLite databases; Alembic remains the only
schema-management strategy for PostgreSQL.

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
- **Frontend shows a login error:** the API isn't running or the dev proxy
  target is wrong; verify `http://localhost:8000/api/health` directly.
- **401 after seed:** you may be logging in with the wrong password; rerun the
  seed or check `SEED_DEV_PASSWORD`.
- **Stale frontend deps in Docker:** the `web` service mounts `./frontend`, but
  `node_modules` lives in an anonymous volume; run `docker compose build web`
  after dependency changes.
