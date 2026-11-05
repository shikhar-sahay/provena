# Provena

Provena is an explainable AI-assisted digital forensic investigation platform designed to streamline evidence management, investigative analysis, and case reporting. It provides a centralized workspace where investigators can organize cases, preserve evidence integrity, maintain chain-of-custody records, examine correlated findings, and generate traceable investigation reports.

Built with React, FastAPI, and PostgreSQL, Provena combines structured investigative workflows with transparent, rule-based analysis and deterministic reporting.

The current development target is **0.1.0-beta.0**, an authentication incident investigation workbench. This is a prerelease validation identifier, not a published release or forensic certification. The repository has no approved license grant yet; license selection and maintainer approval remain public-release blockers. The live deployment is managed separately and may lag this source revision.

## Start locally and investigate

With Docker Compose installed, run `docker compose up --build --wait` from the repository root, then open [the local interface](http://localhost:5173). The local stack binds only to loopback, migrates its development database and checks API readiness. It uses separate persistent database, evidence and export-cache volumes. Do not use its demonstration database credentials for an exposed deployment, or remove volumes containing investigations.

Follow the [synthetic authentication demonstration](sample-data/m4-authentication/README.md) to ingest Linux authentication, Windows Security and Sysmon exports, select immutable event sets, run five deterministic detection families and review findings. Unknown timestamps remain uncertain; detections describe observed patterns rather than confirmed compromise.

Open an investigation's **Exports** tab to create a metadata package or explicitly select verified originals. Downloaded packages can be checked offline with `python -m app.ops.archive package.zip` from `backend/`. Hash verification detects internal inconsistency; it does not authenticate the package author. Native PostgreSQL backup/restore, deployment preflight and recovery procedures are in the [operations guide](docs/operations.md).

See [M5 implementation and verification](docs/m5-implementation.md), [release validation](docs/releases.md), [contributing](CONTRIBUTING.md) and [security reporting](SECURITY.md). CI builds private candidate artifacts and a disposable local stack. It does not publish a release or deploy to AWS.

**Live application:** [https://provena-app.duckdns.org/login](https://provena-app.duckdns.org/login). The deployed frontend and API operate over HTTPS; local development remains available below.

## Key capabilities

- Manage workspaces, case teams, priorities, statuses, investigator notes, and scoped search.
- Register evidence through recoverable pending/failed/ready states under opaque storage keys with immutable SHA-256 baselines.
- Record verification outcomes and append-only chain-of-custody events.
- Process only verified evidence using a bounded private copy whose digest is checked before parsing; record exact input provenance and explicit blocked outcomes.
- Extract provenance-bearing artifacts and correlate shared values across evidence.
- Propose findings through versioned rules with visible confidence factors and recommendations.
- Require human acceptance or rejection before findings enter immutable, content-hashed reports.
- Review investigation timelines and an append-only application audit trail.

The interface supports administrator, investigator, forensic analyst, and evidence custodian roles. The backend enforces workspace membership and investigation permissions for every protected operation.

## Architecture overview

Provena is a modular monolith. A React single-page application calls the FastAPI REST API; domain services own authorization, case operations, evidence handling, analysis, and reporting. PostgreSQL stores investigation records and analysis results. Raw evidence bytes are held by a separate storage backend, currently the local filesystem in the AWS deployment.

```mermaid
flowchart LR
    UI[React, TypeScript, Vite, Tailwind] -->|"/api/*"| REST[FastAPI REST API]
    REST --> AUTH[Authentication and workspace RBAC]
    REST --> DOMAIN[Investigation, evidence, custody, audit, reporting services]
    DOMAIN --> PG[(PostgreSQL)]
    DOMAIN --> STORE[Evidence storage interface]
    STORE --> LOCAL[(Local filesystem, deployed)]
    STORE -. "available in code, not selected on EC2" .-> S3[(Private S3 objects)]
    DOMAIN --> AI[In-process explainable analysis]
    AI --> PG
```

Alembic manages database schema changes. Evidence metadata, digests, verification history, custody events, artifacts, correlations, findings, reports, and audit records live in PostgreSQL. Raw evidence is stored separately. Backend checks remain the authorization boundary; hiding actions in the interface is only a usability aid. See [system architecture](docs/architecture.md), [evidence integrity](docs/evidence-integrity.md), and [security](docs/security.md).

### Request flow

```mermaid
flowchart LR
    B[Browser] -->|"/ or frontend route"| N[Nginx on EC2]
    N -->|static files or index.html| SPA[React production build]
    B -->|"/api/* with bearer token"| N
    N -->|"/api/* on localhost"| API[FastAPI :8000]
    API --> SVC[Authorized domain services]
    SVC --> PG[(PostgreSQL 16)]
    SVC --> EVID[(Local evidence directory)]
```

Nginx serves the built frontend and forwards `/api/` requests without stripping their prefix. FastAPI authenticates and authorizes API calls before accessing records or stored evidence. [AWS deployment](docs/aws-deployment.md) explains the host and reverse-proxy setup.

## Investigation workflow and explainable AI

1. Create or join a workspace, then open a numbered investigation and assign its lead and team.
2. Register evidence. Provena streams the upload, computes an immutable SHA-256 baseline, and records its initial custody event.
3. Verify stored bytes against that baseline. Each attempt records the expected and observed digest and a `verified`, `mismatch`, or `unavailable` result. New evidence begins as `not_verified`.
4. Select evidence for analysis. Only `verified` evidence enters parsing; other integrity states receive explicit blocked outcomes.
5. Inspect extracted artifacts and shared-value correlations with their source evidence, locators, context, and extractor version.
6. Review rule-generated findings, matched conditions, weighted confidence factors, and recommended next steps. An investigator accepts or rejects each proposal.
7. Generate an immutable report from accepted findings, evidence and custody summaries, notes, and traceability data. The report includes a SHA-256 content hash. Audit events record meaningful actions throughout the workflow.

```mermaid
flowchart LR
    U[Evidence upload] --> V{Integrity verified?}
    V -->|Yes| P[Bounded parsing and artifact extraction]
    V -->|No| BLOCK[Blocked analysis outcome]
    P --> C[Shared-value correlation]
    C --> R[Versioned rule reasoning]
    R --> S[Weighted confidence factors]
    S --> REC[Rule recommendations]
    REC --> H[Human review]
    H -->|Accepted findings| D[Deterministic report]
    H --> L[Deterministic accepted-finding narrative]
    L -. "if enabled and grounded" .-> D
```

The implemented pipeline uses regular expressions, key-aware structured rules, conservative normalization, and `pypdf` for machine-readable PDFs. It supports text, log, CSV, JSON, and machine-readable PDF evidence, extracts 14 controlled artifact types, and applies three versioned rules: `identity-recurrence`, `removable-media-session`, and `external-transfer-sequence`. Confidence is a deterministic weighted ranking score from 0 to 100, **not a calibrated probability or Bayesian estimate**.

Authoritative reports use deterministic templates and exact accepted findings. M2 excludes free-form model prose because references and literal checks cannot establish semantic fidelity. Legacy Ollama configuration and availability probes remain compatible, but model output cannot introduce report conclusions. Historical reports remain unchanged. See [AI architecture](docs/ai-architecture.md).

## Cloud infrastructure

Provena runs in **AWS Asia Pacific (Mumbai), `ap-south-1`** on one Amazon Linux 2023 `t3.micro` EC2 instance with a 20 GB EBS root volume. The instance sits in a public subnet of a custom VPC behind security groups and an internet gateway. Nginx serves the React build and proxies API requests to a systemd-managed FastAPI process bound to localhost port 8000. PostgreSQL 16 and the active evidence directory reside on the same EC2 instance. Operators use AWS Systems Manager Session Manager; an IAM instance role scopes AWS access.

The AWS environment also has an S3 gateway VPC endpoint and separate S3 buckets for evidence-related resources, frontend-related resources, and operational backups or migration artifacts. The active application uses `EVIDENCE_STORAGE_BACKEND=local` with `EVIDENCE_STORAGE_ROOT`; bucket presence does not mean evidence is stored in S3 or frontend assets are served from S3. The gateway endpoint carries EC2-to-S3 traffic only if associated with the instance subnet's route table.

```mermaid
flowchart TB
    B[User browser] -->|"DNS lookup"| DNS[DuckDNS hostname]
    DNS -->|"current public IP"| IGW
    B -->|"HTTPS 443"| IGW
    subgraph AWS["AWS ap-south-1"]
      subgraph VPC["Custom VPC"]
        IGW[Internet gateway] --> RT[Public route table]
        subgraph SUBNET["Public subnet"]
          SG[Application security group]
          subgraph EC2["EC2 t3.micro, Amazon Linux 2023, 20 GB EBS root"]
            N[Nginx: frontend and /api proxy]
            API[FastAPI systemd service :8000]
            PG[(PostgreSQL 16)]
            FILES[(Local evidence files)]
            N -->|"/api/ on localhost"| API
            API --> PG
            API --> FILES
          end
            SG -->|"HTTPS 443; HTTP 80 redirects"| N
        end
        RT --> SG
        EP[S3 gateway endpoint] -. "associated route table required" .-> S3[(Private S3 buckets)]
        EC2 -. "authorized S3 operations, when used" .-> EP
      end
      ROLE[IAM instance role] -. "scoped permissions" .-> EC2
      SSM[Systems Manager Session Manager] -->|"management session"| EC2
    end
```

DuckDNS updates the hostname when the EC2 public IP changes. Nginx terminates HTTPS with a Let's Encrypt certificate and redirects HTTP to HTTPS; automatic DNS updates and certificate renewal are configured. The current topology does not use CloudFront, RDS, a load balancer, Auto Scaling, or multi-AZ failover. One small EC2 instance is a shared failure domain for the API, database, and local evidence; coordinated backups and restore tests are important. See [AWS deployment](docs/aws-deployment.md), the [team architecture and deployment guide](docs/AWS_ARCHITECTURE_AND_DEPLOYMENT_GUIDE.md), and [security](docs/security.md).

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, React Router, Vitest |
| API and services | Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Uvicorn |
| Data | PostgreSQL 16; local evidence storage in the AWS deployment; optional private S3 backend in code |
| Analysis | Python parsers and rules, `pypdf`, deterministic correlation and confidence; deterministic authoritative narrative |
| AWS operations | EC2, EBS, VPC, security groups, internet gateway, S3 gateway endpoint, IAM instance role, S3 buckets, Systems Manager; Nginx and systemd run on EC2 |
| Security controls | bcrypt password hashes, JWT bearer tokens, workspace and case RBAC, SHA-256 integrity baselines, append-only custody and audit records |

The frontend stores its bearer token in `localStorage`, which page JavaScript can access. This is a security trade-off for a deployed web application; see [security](docs/security.md). Provena is not certified forensic software and makes no legal admissibility claim.

## Getting started

Local prerequisites: Python 3.13+, Node 22+, Docker with Docker Compose, and PowerShell.

```powershell
./scripts/dev.ps1 setup    # local PostgreSQL, dependencies, migrations, development accounts
./scripts/dev.ps1 demo     # optional synthetic five-case demo, idempotent
./scripts/dev.ps1 api      # FastAPI on localhost:8000, separate terminal
./scripts/dev.ps1 web      # Vite on localhost:5173, separate terminal
```

The Vite development proxy forwards `/api` to FastAPI. Development uses local evidence storage by default. Do not run the synthetic seed against production. The [development guide](docs/development.md) covers manual setup, configuration, migrations, tests, and report narration safety.

To use the deployed application instead, open the [live HTTPS login](https://provena-app.duckdns.org/login). Do not use local demo credentials as production credentials.

```powershell
# In backend/
python -m pytest

# In frontend/
npm run lint
npm run typecheck
npm test
npm run build
```

## Documentation and roadmap

- [System architecture](docs/architecture.md): modules, authorization, data flow, and service boundaries.
- [AI architecture](docs/ai-architecture.md): extraction, provenance, rules, confidence, review, and Ollama safeguards.
- [Evidence integrity](docs/evidence-integrity.md): registration, SHA-256 verification, custody, and analysis eligibility.
- [AWS deployment](docs/aws-deployment.md): Mumbai infrastructure, Nginx/systemd deployment, verification, and limitations.
- [AWS architecture and deployment review guide](docs/AWS_ARCHITECTURE_AND_DEPLOYMENT_GUIDE.md): deployed topology, operations, trade-offs, and technical review questions.
- [Security](docs/security.md): authentication, IAM, network controls, storage, TLS status, and risks.
- [Local development](docs/development.md): setup, configuration, migrations, demo, and testing.
- [Future enhancements](docs/future-enhancements.md): proposed analysis and availability improvements.

Potential future work includes stronger backup and monitoring practices, S3 evidence migration, managed PostgreSQL, higher availability, and carefully evaluated analysis additions. Bayesian scoring, knowledge graphs, cross-case inference, OCR, and spaCy-based NLP are not implemented.


## Normalized security events (M3)

The case-scoped Security Events explorer ingests verified Linux SSH/PAM logs and
structured Windows Security/Sysmon exports through immutable source profiles.
It preserves exact-input digests, record locators, timestamp uncertainty and
processing coverage. Reingestion is idempotent; Sysmon is contextual telemetry,
not authentication success/failure. Native EVTX decoding remains unsupported.

See [M3 implementation](docs/m3-implementation.md) and the
[synthetic authentication demonstration](sample-data/m3-authentication/README.md).

## Authentication investigation workbench (M4)

Select explicit normalized event sets, run five versioned authentication pattern
detectors, inspect source-backed findings and review them through the existing
analyst decision workflow. The Authentication tab includes uncertainty-aware
timeline lanes, account/IP/host pivots, source provenance and selected-set reports.
Copies and alternative profile interpretations are not independent attempts.
Severity describes review priority, never a probability of compromise.

See [M4 implementation](docs/m4-implementation.md) for rule thresholds, limits,
identity and time semantics, and the [synthetic end-to-end demonstration](sample-data/m4-authentication/README.md).
