# AWS deployment: current single-instance architecture

Provena runs on a single EC2 instance in Asia Pacific (Mumbai), `ap-south-1`. This guide describes that deployment and its operational boundaries. The repository contains application configuration and earlier, unimplemented container/CloudFront plans, but no infrastructure-as-code or live account inventory. Verify commands, service names, mount points, and network rules against the EC2 instance before using them. Do not copy development credentials to production.

## Deployment inventory

| Concern | Reported configuration | Verification still needed |
| --- | --- | --- |
| Host | Amazon Linux 2023 on one `t3.micro` EC2 instance | Instance health, AMI revision, memory headroom |
| Disk | 20 GB EBS root volume | Encryption, utilization, backup retention |
| Network | Custom VPC, public subnet, internet gateway, route table, security groups | Exact inbound rules and public IP lifecycle |
| Management | AWS Systems Manager Session Manager | Agent connectivity and instance profile permissions |
| AWS storage | Three distinct S3 buckets for evidence-related resources, frontend-related resources, and operational backups/migration artifacts | Bucket encryption, public-access blocks, versioning, actual object usage |
| S3 route | Gateway VPC endpoint | Endpoint association with the EC2 subnet route table |
| Web | Nginx serves the Vite production build and proxies `/api/` | Live Nginx configuration, caching and security headers |
| API | FastAPI under systemd, bound to localhost port 8000 | Unit name, working directory, service user, restart policy |
| Database | PostgreSQL 16 on the EC2 instance | Data directory, backups, local-only listener |
| Evidence | Local filesystem through `EVIDENCE_STORAGE_ROOT`; `EVIDENCE_STORAGE_BACKEND=local` | Path, permissions, backups, disk growth |
| LLM | `LLM_ENABLED=false` | Runtime configuration |

The code supports private S3 evidence storage when explicitly selected, but the deployed application currently uses local files. S3 buckets do not imply S3-backed evidence or frontend hosting. PostgreSQL is on EC2, not RDS. CloudFront, ALB, Auto Scaling, ECS, EKS, Lambda, Elastic Beanstalk, and multi-AZ failover are not part of this deployment.

## Request and deployment flow

```mermaid
flowchart LR
    B[Browser] -->|"web request; HTTPS in progress"| N[Nginx on EC2]
    N -->|"/ and static assets"| SPA[React production build]
    N -->|"/api/ proxy"| API[FastAPI on 127.0.0.1:8000]
    API --> PG[(PostgreSQL 16 on EC2)]
    API --> FILES[(Local evidence directory)]
    API -. "instance role, only for configured operations" .-> S3[(Private S3 buckets)]
```

Keep `VITE_API_URL` unset for a same-origin frontend build. The browser requests `/api/*`; Nginx forwards those requests without removing the `/api` prefix. The backend router is mounted under `/api`. Multipart upload and streaming download should be tested through Nginx, not only through localhost.

## Prerequisites and AWS controls

1. Choose `ap-south-1` and confirm account budget, Free Plan eligibility, quotas, and approved retention. Resource cost and credits are account-specific.
2. Place the instance in the public subnet with an internet-gateway route. Limit inbound web ports to the intended audience. Keep PostgreSQL 5432 and FastAPI 8000 closed externally; permit administration through Systems Manager. Avoid open SSH if Session Manager suffices.
3. Attach an IAM instance role with only the S3 actions and object prefixes actually used for backup or migration. The local evidence backend needs no S3 object permission for ordinary evidence operations. Do not store long-lived AWS keys in the environment file.
4. Check that the S3 gateway endpoint is associated with the public subnet's route table. An endpoint resource by itself does not guarantee that this instance uses it.
5. Confirm S3 Block Public Access, encryption, versioning and lifecycle/retention on each bucket. Keep the frontend bucket private if it is not actively serving assets.

The repository has no EC2 bootstrap script, Nginx site file, or systemd unit for this live topology. The examples below are a reproducible template to compare with the deployed configuration, not a claim that those exact files already exist.

## PostgreSQL 16 and backend

Install PostgreSQL 16 from a trusted, supported source for the selected Amazon Linux 2023 release. Keep the database listener on `127.0.0.1` or a local Unix socket, create a dedicated database and least-privilege application role, and record the data directory. Back up before upgrades. Use a supported Python version that satisfies the backend requirements, create a virtual environment, and install `backend/requirements.txt` from a reviewed release.

Populate a protected production environment file outside the Git checkout:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg2://APP_USER:REPLACE_AT_DEPLOYMENT@127.0.0.1:5432/APP_DB
SECRET_KEY=REPLACE_WITH_RANDOM_VALUE_AT_LEAST_32_CHARACTERS
CORS_ORIGINS=https://VERIFIED_DUCKDNS_HOSTNAME
EVIDENCE_STORAGE_BACKEND=local
EVIDENCE_STORAGE_ROOT=/srv/provena/evidence
LLM_ENABLED=false
TRUSTED_PROXY_IPS=127.0.0.1
```

These are placeholders, not usable credentials. Until HTTPS is operational, set `CORS_ORIGINS` to the exact current origin instead of the future hostname. Because production validation rejects placeholder values, replace them before startup. Protect the file with owner-only read permission. Do not place it under the web root or commit it. Ensure the service account can read and write the evidence directory but cannot read other application secrets unnecessarily.

From the release's `backend/` directory, with the production environment loaded, run `python -m alembic upgrade head` explicitly. Do not run development seeds or silently migrate during service startup. Confirm `GET /api/health` and `GET /api/ready` after starting; readiness checks PostgreSQL connectivity.

A systemd unit should use a dedicated non-root user, a fixed working directory, the protected environment file, and a restart policy. Its command should run a single Uvicorn process bound to `127.0.0.1:8000`. Review the live service with `systemctl status SERVICE_NAME` and `journalctl -u SERVICE_NAME`; avoid logging bearer tokens, passwords, or evidence contents. The exact unit name and path must be confirmed on the instance.

Example unit structure to adapt after inspecting the live host:

```ini
[Unit]
Description=Provena API
After=network.target postgresql.service

[Service]
User=APP_SERVICE_USER
WorkingDirectory=/opt/provena/backend
EnvironmentFile=/etc/provena/api.env
ExecStart=/opt/provena/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

After placing the unit, use `sudo systemctl daemon-reload`, `sudo systemctl enable --now SERVICE_NAME`, and `sudo systemctl status SERVICE_NAME`. Confirm the PostgreSQL unit name on Amazon Linux before keeping the example `After=` dependency.

## Frontend and Nginx

Install dependencies from the lockfile, run `npm run build` in `frontend/` with `VITE_API_URL` unset, and deploy only `dist/` into an Nginx-readable directory. Nginx should serve static assets, fall back to `index.html` for frontend routes, and proxy `/api/` to `http://127.0.0.1:8000` with request path and Authorization header preserved. Do not rewrite API errors to SPA HTML.

Review Nginx request-body limits against `EVIDENCE_MAX_UPLOAD_BYTES` (100 MiB default), proxy timeouts for synchronous analysis, binary download buffering, and cache policy. Never cache authenticated API responses. Keep port 8000 bound to loopback and do not expose PostgreSQL.

Example HTTP site structure, with `SERVER_NAME` and `FRONTEND_DIST` replaced after checking the host:

```nginx
server {
    listen 80;
    server_name SERVER_NAME;
    root FRONTEND_DIST;
    index index.html;
    client_max_body_size 110m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_read_timeout 120s;
        add_header Cache-Control "no-store" always;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Keep `proxy_pass` without a trailing slash so the `/api/` prefix reaches FastAPI. Validate with `sudo nginx -t` before a reload. The final HTTPS configuration should add a certificate-backed 443 server and make port 80 redirect to HTTPS.

## DuckDNS and HTTPS: configuration in progress

The intended completed path is DuckDNS DNS to the instance's public IP, Let's Encrypt certificate, Nginx HTTPS termination, port 80 redirect to 443, certificate renewal, and a DNS updater when the IP changes. The current web scheme was not independently verified during this documentation pass; describe HTTPS as in progress until the hostname, certificate, redirect, and renewal are tested.

Before marking HTTPS operational, verify:

- The DuckDNS name resolves to the current EC2 public IP and updates after an IP change.
- The certificate covers the exact hostname and is trusted by a browser.
- HTTP redirects to HTTPS, including deep links, without breaking `/api/`.
- Renewal is scheduled and a dry run succeeds.
- Login, evidence upload/download, reports, and all API methods work over HTTPS without mixed content.
- `CORS_ORIGINS` matches the final origin and Nginx forwards the right scheme and host.

The README production URL remains a placeholder until these checks pass.

## S3 and backup use

The S3 buckets are resources for evidence-related future work, frontend-related assets, and operational backups/migration artifacts. The live evidence API reads the EC2 filesystem. A database backup alone cannot restore evidence bytes; back up both PostgreSQL and the evidence directory, preserve checksums and access controls, and test an isolated restore. Verify whether operations-bucket backups are actually scheduled and retained before claiming automation. S3 access through the gateway endpoint depends on route-table association and the instance role policy.

## Deployment verification

After each release, check:

1. Nginx serves the SPA and a direct deep link.
2. `/api/health` returns liveness and `/api/ready` confirms PostgreSQL.
3. Login, workspace selection, and role restrictions work.
4. Synthetic evidence upload, SHA-256 verification, authorized download, and custody events work through Nginx.
5. Verified-only analysis produces artifacts, correlations, explainable findings, and a deterministic report; audit history records the actions.
6. A restart preserves PostgreSQL records and local evidence files.
7. Backup and isolated restore reproduce records, evidence digests, and report hashes.
8. Disk space, memory, systemd, Nginx, PostgreSQL, and logs remain healthy.

If the API fails, inspect `journalctl`, production configuration validation, database connectivity, and Alembic revision. If the SPA loads but API calls fail, check Nginx `/api/` proxying, browser network responses, Authorization forwarding, and CORS. If verification reports `unavailable`, check the configured evidence root, file permissions, and backup restoration; do not rewrite the immutable baseline to conceal missing files.

## Trade-offs and older design documents

A single `t3.micro` is economical and simple, but CPU, memory, disk, and service availability share one failure domain. Local PostgreSQL and evidence require coordinated backup and recovery. Private networking, CloudFront, Docker, and S3 evidence are alternative architectures, not part of the live topology. See [future enhancements](future-enhancements.md) for possible migration paths.
