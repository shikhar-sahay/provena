# Development Guide

## Prerequisites

Python 3.13+, Node 22+, Docker + Docker Compose.

## First-time setup

```bash
cp .env.example .env        # .env is git-ignored; adjust values if needed
docker compose up --build   # db :5432, api :8000, web :5173
```

Open `http://localhost:5173` (frontend) and
`http://localhost:8000/api/health` (backend health).

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

| Variable       | Used by | Default (dev)                                              |
| -------------- | ------- | ---------------------------------------------------------- |
| `APP_ENV`      | Backend | `development`                                              |
| `DATABASE_URL` | Backend | `postgresql+psycopg2://provena:provena@localhost:5432/provena` |
| `CORS_ORIGINS` | Backend | `http://localhost:5173`                                    |
| `VITE_API_URL` | Frontend| `http://localhost:8000` (dev proxy covers `/api` anyway)   |

See `.env.example`. Never commit `.env` or any secrets.

## Tests, lint, formatting

```bash
python -m pytest                     # from backend/
npm run lint && npm run typecheck    # from frontend/
npm run build                         # from frontend/ (production build)
```

CI (`.github/workflows/ci.yml`) runs backend tests plus frontend
lint and build on every push/PR.

## Database migrations (Alembic)

Alembic is configured (`backend/alembic.ini`, `backend/alembic/env.py`) but no
application tables exist yet. Once the first domain models are added:

```bash
alembic revision --autogenerate -m "describe change"   # from backend/
alembic upgrade head
```

`DATABASE_URL` must be set for migrations to run.

## Docker workflow

- `docker compose up --build` — full local stack.
- `docker compose up db` — only Postgres (run API/web from source).
- `docker compose down -v` — stop everything and delete the dev database volume.

## Troubleshooting

- **Backend can't reach Postgres:** check `DATABASE_URL` host (`localhost` for
  local runs, `db` inside Compose) and that the `db` container is healthy.
- **Frontend shows "Backend offline":** the API isn't running or the dev proxy
  target is wrong; verify `http://localhost:8000/api/health` directly.
- **Port conflicts:** another Postgres on 5432 or Vite on 5173 — stop the other
  service or remap ports in `docker-compose.yml`.
- **Stale frontend deps in Docker:** the `web` service mounts `./frontend`, but
  `node_modules` lives in an anonymous volume; run `docker compose build web`
  after dependency changes.
