# Provena — Digital Investigation Management Platform

Provena is an AI-assisted digital investigation management platform. It centralizes
the lifecycle of a digital investigation — cases, evidence, chain of custody, and
explainable analysis — while preserving evidence integrity, traceability, and
human oversight.

This is a two-person university project (Software Engineering + AI). It is **not**
certified forensic software and must never be described as such.

## Current status: development foundation

This repository currently contains a **runnable scaffold only**:

- React + TypeScript + Vite + Tailwind application shell (`frontend/`)
- FastAPI application with a health endpoint (`backend/`)
- PostgreSQL configuration via Docker Compose
- pytest + ESLint/typecheck/build tooling, CI workflow
- Architecture and agent documentation (`docs/`, `AGENTS.md`)

Nothing in the investigation workflow below is implemented yet beyond the health
check. Do not mistake planned capabilities for working features.

## Planned investigation workflow

Create Investigation → Assign Team → Collect/Register Evidence → Verify Integrity
→ Maintain Chain of Custody → Process Evidence → Correlate Evidence → Generate
Insights → Investigator Reviews Findings → Generate Report → Archive Investigation

## Planned capabilities

- Authentication, role-based access control, user management
- Case/investigation management
- Evidence registration, upload, metadata, SHA-256 integrity verification
- Chain of custody, findings/notes, timeline, audit logs
- Explainable AI-assisted analysis: artifact/entity extraction, correlation,
  rule-based reasoning, confidence scoring, recommendations
- Investigator validation/rejection of AI findings
- AI-assisted report generation, case archival

## AI philosophy (summary)

**The LLM is not the investigative reasoning engine.** Evidence processing,
correlation, reasoning, confidence calculation, and recommendations must remain
deterministic, explainable, and traceable to underlying evidence (parsers, regex,
spaCy where NLP genuinely helps, custom correlation/reasoning logic, weighted
scoring). A local LLM (Ollama) may later be used **only** for natural-language
generation — turning already-validated structured findings into professional
report prose. The system must stay useful when the LLM is unavailable.
See `docs/ai-architecture.md` and `AGENTS.md`.

## Technology stack

| Layer    | Choice                                              |
| -------- | --------------------------------------------------- |
| Frontend | React, TypeScript, Vite, Tailwind CSS               |
| Backend  | Python, FastAPI, Pydantic, SQLAlchemy               |
| Database | PostgreSQL (Docker Compose for local dev)           |
| Analysis | Planned: deterministic parsers, regex, spaCy, custom correlation/reasoning |
| Dev      | Docker/Docker Compose, pytest, ESLint, Alembic      |

The backend is a **modular monolith**. See `docs/architecture.md`.

## Repository structure

```text
provena/
├── frontend/        # React + TS + Vite + Tailwind shell
├── backend/         # FastAPI app (app/api, app/core, app/db, app/modules, app/ai)
├── docs/            # architecture.md, ai-architecture.md, development.md
├── sample-data/     # synthetic demo data policy (no real evidence, ever)
├── .github/         # CI workflow
├── .env.example     # safe example config (never commit .env)
├── AGENTS.md        # instructions for AI coding agents
└── docker-compose.yml
```

## Prerequisites

- Python 3.13+, Node 22+, Docker + Docker Compose
- Zero budget required: everything runs locally.

## Local development

```bash
cp .env.example .env        # adjust if needed; .env is git-ignored
docker compose up --build   # db :5432, api :8000, web :5173
```

Or run services individually (see `docs/development.md`):

```bash
# Backend
pip install -r backend/requirements.txt
uvicorn app.main:app --reload          # from backend/

# Frontend
npm install && npm run dev             # from frontend/
```

Health check: `GET http://localhost:8000/api/health`

## Tests, lint, build

```bash
python -m pytest                       # from backend/
npm run lint && npm run typecheck       # from frontend/
npm run build                           # from frontend/
```

## Architecture

High level: the React SPA talks to the FastAPI modular monolith over `/api/*`;
PostgreSQL persists domain data; uploaded evidence will live on the filesystem
with hashes in the database; the analysis layer lives **inside** the backend
(`backend/app/ai/`), not as a separate service. Details in `docs/architecture.md`.
