# Architecture

Provena is a **modular monolith**: a React SPA, a FastAPI backend containing all
domain and analysis logic, and PostgreSQL. No microservices, no message brokers,
no separate AI service.

## System overview

```text
Browser (React SPA)
   │  HTTP /api/*
   ▼
FastAPI backend (modular monolith)
   ├── api/        routers per domain
   ├── modules/    domain logic + SQLAlchemy models
   ├── ai/         explainable analysis pipeline (in-process)
   ├── core/       config, errors
   └── db/         engine / sessions
   │                    │
   ▼                    ▼
PostgreSQL      Evidence files on disk
(domain data,   (hashes + metadata in DB;
 hashes,          files content-addressed
 audit logs)      by SHA-256 — planned)
```

## Frontend / backend / database relationship

- The SPA is the only client. It calls `/api/*` on the backend (dev proxy in
  `vite.config.ts`; `VITE_API_URL` in other environments).
- The backend owns all business rules, integrity checks, and authorization.
- PostgreSQL is the system of record for domain data. It never stores raw
  evidence blobs — only metadata, SHA-256 hashes, custody events, and audit logs.

## Planned domain boundaries (`backend/app/modules/`)

| Module    | Responsibility (planned)                              |
| --------- | ----------------------------------------------------- |
| auth      | Authentication, sessions/tokens                       |
| users     | User management, role-based access control            |
| cases     | Investigation lifecycle, team assignment, archival    |
| evidence  | Registration, upload, metadata, SHA-256 verification |
| custody   | Chain-of-custody events                               |
| findings  | Investigator notes, AI-finding validation             |
| audit     | Application audit logs                                |
| reports   | Report generation from validated findings             |

Each domain package exposes a router mounted in `app/api/router.py`. Domains
communicate via direct Python calls (same process), not HTTP or queues.

## File storage concept (planned)

- Uploaded evidence is written to a server-side directory outside the repo
  (git-ignored), stored under its SHA-256 hash.
- The hash is computed at ingest and re-verified on access; the database holds
  the hash, size, MIME type, uploader, timestamps, and custody chain.
- Real evidence must never be committed to the repository.

## Request / data flow (planned)

1. Investigator acts in the SPA → `POST /api/...`.
2. Backend authenticates/authorizes, validates via Pydantic schemas.
3. Domain service mutates Postgres inside a transaction and appends audit entries.
4. Evidence ingest additionally hashes the file, stores it by hash, records
   metadata + custody event.
5. Analysis pipeline (in-process, deterministic) derives artifacts, correlations,
   rule matches, confidence scores, recommendations — all referencing evidence IDs.
6. Investigator validates/rejects AI findings; only validated findings feed
   report generation.

## What exists today vs what is planned

- Exists: app shell, config, DB foundation, `/api/health`, test/lint/build/CI.
- Planned: everything in the tables and flows above. Labels marked "planned"
  are design intent, not implemented behavior.
