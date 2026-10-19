# Security and evidence controls

This document describes application behavior visible in the repository and the AWS deployment. Provena is not certified forensic software.

## Identity and authorization

Provena hashes passwords with bcrypt and issues signed JWT bearer tokens. Workspace membership establishes the first authorization boundary. Investigation membership and roles further restrict case access and actions. Administrators are scoped to their workspace. Backend checks enforce access to evidence, analysis, findings, reports, and downloads; frontend controls are only user-interface guidance.

The browser stores the token in `localStorage`. Page JavaScript can read it if script injection occurs. Keep dependencies current, review content security policy and Nginx headers, and consider HttpOnly cookies in a future authentication change. Never log tokens or place them in URLs. Production must use a strong unique `SECRET_KEY` and exact allowed origins.

## Evidence and provenance

Evidence registration streams bytes and records an immutable SHA-256 baseline. Later verification hashes stored bytes and records `verified`, `mismatch`, or `unavailable` with expected and observed digests. Unverified or failed evidence cannot enter analysis. Original filenames do not become storage paths; external API responses omit internal storage keys. Custody and audit records are append-only through the application API.

The current EC2 deployment uses local evidence files. Back up the directory with PostgreSQL and test restoration against recorded baselines. A separate S3 backend exists in code but is not selected by the live deployment. See [evidence integrity](evidence-integrity.md).

## AWS boundaries

The deployment uses a public-subnet EC2 instance, security groups, a scoped IAM instance role, private S3 buckets, and Systems Manager Session Manager. Verify that only intended web ports are public, while FastAPI port 8000 and PostgreSQL port 5432 stay local. An S3 gateway endpoint affects EC2-to-S3 routing only when associated with its route table. IAM and bucket policies should permit only the active operational backup or migration prefixes, with no embedded access keys.

PostgreSQL, evidence files, and the frontend share one EC2 failure domain. Confirm EBS encryption, filesystem permissions, backups, restore testing, disk alarms, log retention, and instance patching in the AWS account. The repository cannot attest that these operational checks have been completed.

## Transport security

The deployed domain uses a Let's Encrypt certificate with Nginx TLS termination. Port 80 redirects to HTTPS; DuckDNS IP updates and certificate renewal are configured, and a renewal dry run succeeded on October 19, 2026. The certificate expires January 17, 2027 unless renewed. The DuckDNS token is held in a root-protected file outside the repository. HTTPS protects transport but does not replace secret rotation, patching, backups, access review, or application security testing. Keep `CORS_ORIGINS` restricted to the exact production origin and verify uploads and downloads after web-server changes.

## Reporting and AI trust

The deterministic rule engine proposes findings with cited evidence, locators, factors, and recommendations. Human acceptance is required for reports. Optional Ollama text generation uses structured context and grounding validation; the deployed configuration disables it. Neither a generated narrative nor a confidence score proves an allegation. Reports are immutable content-hashed snapshots, not cryptographic signatures.
