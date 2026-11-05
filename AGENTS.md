# AGENTS.md: Instructions for AI coding agents working in Provena

Read this file before making any change. The repository itself is the persistent
project context; keep it accurate.

## 1. Project purpose

Provena is an AI-assisted digital investigation management platform. It centralizes the investigation lifecycle
(cases, evidence, chain of custody, explainable analysis, human validation,
reporting) while preserving evidence integrity, traceability, and human oversight.

## 2. Project constraints (non-negotiable)

- Small focused team, limited timeline, zero infrastructure/API budget.
- Must run on ordinary local hardware and demo locally with no paid services.
- Optimize for maintainability, simplicity, reliability, explainability.
- Backend is a **modular monolith**. Do not introduce microservices.
- Do not introduce Kubernetes, Kafka/RabbitMQ, Redis, Celery, Neo4j,
  Elasticsearch, vector DBs, RAG/MCP infrastructure, or cloud-specific services
  unless explicitly requested with justification.
- Do not add LLM SDKs, model dependencies, embeddings, vector DBs, knowledge
  graphs, RAG/MCP infrastructure, or cloud-specific services unless explicitly
  requested with justification. Legacy Ollama configuration and an availability probe remain; M2 authoritative
  reports use deterministic assembly because free-form semantic fidelity cannot
  be guaranteed. Do not reintroduce model prose without explicit justification.

## 3. Core AI principle

**"The LLM is a language-generation component, not the source of investigative truth."**

Evidence processing, correlation, reasoning, confidence calculation, and
recommendations must remain explainable and traceable to underlying evidence.
The investigative pipeline is deterministic parsers, regex, key-aware structured
rules, pypdf text extraction for machine-readable PDFs, custom correlation logic,
custom rule-based reasoning, transparent weighted confidence scoring, and
deterministic recommendations, with human investigator validation before anything
reaches a report. M2 report prose uses deterministic templates and exact accepted findings. Legacy
Ollama settings do not enable free-form authoritative narration. Notes, descriptions
and uploaded content are untrusted data, never instructions to a narrator.

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
  modules/           # domain modules: auth, users, investigations, evidence,
                     # dashboard, intelligence, audit (all implemented)
  events/            # pure bounded record parsing, source time and event adapters
  ai/                # deterministic pipeline: parsers, extractors, normalize,
                     # correlate, rules (no FastAPI/SQLAlchemy here)
  main.py            # create_app() + app
docs/                # architecture.md, ai-architecture.md, development.md
sample-data/         # synthetic demo data only (see its README)
```

## 5. Conventions

- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 style. One domain = one
  package under `app/modules/<domain>/` with `router.py`, `schemas.py`,
  `service.py`, `models.py` only as needed. Do not create empty abstraction
  files to look "enterprise". Environment-based config in `app/core/config.py`;
  never hardcode credentials or URLs.
- **Frontend:** Functional React components, TypeScript strict, Tailwind v4
  for styling. Design tokens live in `src/index.css` (`:root` light,
  `.dark` overrides, utilities via `@theme inline`); do not scatter ad-hoc
  colors. Approved monochrome brand in `frontend/public/brand/` (source pack
  plus production copies); never recolor the logo. API base URL from
  `VITE_API_URL` (dev proxy for `/api` in `vite.config.ts`). Auth state in
  `AuthContext`, theme in `ThemeContext`, notifications in `ToastProvider`.
  Shared primitives in `src/components/` (Button, Badge, Field, Dialog,
  Drawer, Menu, Toast, states). Behavior tests under vitest (`npm test`).
  No unnecessary dependencies.
- **Database:** PostgreSQL; schema changes via Alembic (`backend/alembic/`).
  Evidence integrity uses SHA-256. Do not invent
  cryptographic/security mechanisms.
- **Evidence:** only `app/modules/evidence/storage.py` touches the evidence
  directory; files are stored under generated keys, never original filenames.
  Storage keys and paths never appear in API responses. Baseline digests,
  uploaders, and registration timestamps are immutable. Custody and audit
  records are append-only with no update/delete endpoints. See
  `docs/evidence-integrity.md`.
- **Intelligence:** analysis runs only on VERIFIED evidence (hard backend
  gate; everything else is an explicit blocked outcome). Artifacts deduplicate
  on evidence, type, normalized value, locator, and extractor/version.
  Correlations are shared-value, investigation-scoped, and rebuilt per
  completed run. Rules propose findings with weighted factors; humans accept
  or reject; only accepted findings enter deterministic reports. Never invent
  guilt, scores of suspicion, or LLM output.
- **Security events:** `app/events/` holds pure record parsers/adapters; persistence,
  profiles and APIs live in `app/modules/events/`. Profiles and events are immutable
  interpretations, with semantic identity and run memberships. Ingestion requires
  M1 verified snapshots. Preserve source time uncertainty, profile assumptions,
  versioning and coverage. Do not create session links/detections by joining scalar
  artifacts. See `docs/m3-implementation.md`.
- **Security/forensics:** Never commit `.env`, uploads, evidence, DB dumps,
  models, venvs, build artifacts. Real investigative evidence must never enter
  the repo. Never describe the project as certified forensic software.
- **Authentication workbench:** `app/events/detections.py` is a pure deterministic
  engine; `app/modules/detections/` persists explicit event sets and runs. Reuse
  Finding review decisions, never add a competing review model. Do not combine
  alternative interpretations or copied observations as independent attempts.
  Preserve time uncertainty, support keys, rule/config versions and omission counts.
  Reports require explicit event-set selection for authentication conclusions.
  Severity is review priority, not probability. See `docs/m4-implementation.md`.

## 6. Testing and docs requirements

- Backend changes need pytest coverage (`backend/tests/`); frontend changes must
  keep `lint`, `typecheck`, and `build` green.
- Update `README.md` / `docs/*` whenever you make an architectural or
  behavior-changing modification. Never present planned features as implemented.
- Update Mermaid diagrams when the architecture materially changes. Prefer
  Mermaid (text-based, GitHub-rendered, version-controlled) over binary images.

## 7. Dependencies and Git

- Prefer established, boring, maintainable solutions. No "just in case" packages.
- Small, professional commits with conventional messages
  (e.g. `feat:`, `fix:`, `chore:`, `test:`, `docs:`). Never force-push,
  rewrite published history, or commit secrets.

## 8. How to work here

- Inspect existing code and docs before changing architecture; understand the
  current branch/remote and preserve legitimate existing work.
- Prefer focused changes over broad rewrites. Do not silently change core
  architectural decisions (monolith, deterministic AI pipeline, Postgres).
  raise them with the user first.
- Do not expand scope beyond what is requested.

## 9. Writing convention: no em dashes

Never use the em dash character (Unicode U+2014) in project-authored
text: docs, code comments, UI copy, commit messages, seed data. Use commas,
periods, colons, semicolons, parentheses, or hyphens instead. Rewrite the
sentence if substitution reads awkwardly. This rule does not apply to
third-party dependency files.
