# AGENTS.md — Instructions for AI coding agents working in Provena

Read this file before making any change. The repository itself is the persistent
project context; keep it accurate.

## 1. Project purpose

Provena is an AI-assisted digital investigation management platform (university
project: Software Engineering + AI). It centralizes the investigation lifecycle —
cases, evidence, chain of custody, explainable analysis, human validation,
reporting — while preserving evidence integrity, traceability, and human oversight.

## 2. Project constraints (non-negotiable)

- Two-person team, limited timeline, zero infrastructure/API budget.
- Must run on ordinary student hardware and demo locally with no paid services.
- Optimize for maintainability, simplicity, reliability, explainability.
- Backend is a **modular monolith**. Do not introduce microservices.
- Do not introduce Kubernetes, Kafka/RabbitMQ, Redis, Celery, Neo4j,
  Elasticsearch, vector DBs, RAG/MCP infrastructure, or cloud-specific services
  unless explicitly requested with justification.
- Do not add an LLM dependency except as a documented future integration point.

## 3. Core AI principle

**"The LLM is a language-generation component, not the source of investigative truth."**

Evidence processing, correlation, reasoning, confidence calculation, and
recommendations must remain explainable and traceable to underlying evidence.
The investigative pipeline is deterministic parsers, regex, spaCy (only where NLP
genuinely adds value), custom correlation logic, custom rule-based reasoning,
transparent weighted confidence scoring, and deterministic recommendations — with
human investigator validation before anything reaches a report. A local LLM
(Ollama) may eventually render validated structured findings into report prose,
and the system must degrade gracefully when it is unavailable.

- Never call ordinary conditional logic "machine learning".
- Never claim probabilistic/Bayesian confidence scoring is implemented.
  Initial scoring is deterministic/weighted; Bayesian scoring is a possible
  future enhancement.
- Never implement fake AI functionality.

## 4. Repository organization

```text
frontend/            # React + TS + Vite + Tailwind
backend/app/
  api/               # routers (mounted in api/router.py with /api prefix)
  core/              # config, errors, shared utilities
  db/                # engine, session, Base
  modules/           # future domain modules: auth, users, cases, evidence,
                     # custody, findings, audit, reports
  ai/                # future analysis: extraction, correlation, reasoning,
                     # scoring, recommendations, reporting
  main.py            # create_app() + app
docs/                # architecture.md, ai-architecture.md, development.md
sample-data/         # synthetic demo data only (see its README)
```

## 5. Conventions

- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 style. One domain = one
  package under `app/modules/<domain>/` with `router.py`, `schemas.py`,
  `service.py`, `models.py` only as needed — do not create empty abstraction
  files to look "enterprise". Environment-based config in `app/core/config.py`;
  never hardcode credentials or URLs.
- **Frontend:** Functional React components, TypeScript strict, Tailwind for
  styling. API base URL from `VITE_API_URL` (dev proxy for `/api` in
  `vite.config.ts`). No unnecessary dependencies.
- **Database:** PostgreSQL; schema changes via Alembic (`backend/alembic/`).
  Planned default hash for evidence integrity is SHA-256. Do not invent
  cryptographic/security mechanisms.
- **Security/forensics:** Never commit `.env`, uploads, evidence, DB dumps,
  models, venvs, build artifacts. Real investigative evidence must never enter
  the repo. Never describe the project as certified forensic software.

## 6. Testing and docs requirements

- Backend changes need pytest coverage (`backend/tests/`); frontend changes must
  keep `lint`, `typecheck`, and `build` green.
- Update `README.md` / `docs/*` whenever you make an architectural or
  behavior-changing modification. Never present planned features as implemented.

## 7. Dependencies and Git

- Prefer established, boring, maintainable solutions. No "just in case" packages.
- Small, professional commits with conventional messages
  (e.g. `feat:`, `fix:`, `chore:`, `test:`, `docs:`). Never force-push,
  rewrite published history, or commit secrets.

## 8. How to work here

- Inspect existing code and docs before changing architecture; understand the
  current branch/remote and preserve legitimate existing work.
- Prefer focused changes over broad rewrites. Do not silently change core
  architectural decisions (monolith, deterministic AI pipeline, Postgres) —
  raise them with the user first.
- Do not expand scope beyond what is requested.
