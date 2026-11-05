# Provena 2.0 M3: normalized security events

M3 adds a record-aware event path beside the existing artifact/rule pipeline.
It preserves M0 authorization, M1 exact-input verification and M2 historical
provenance. It does not add detections, a full timeline or native EVTX decoding.

## Schema and immutable source profiles

`app/modules/events/models.py` adds case-scoped source profiles, ingestion runs,
immutable events and run/event memberships. Profiles contain adapter, format,
encoding, optional host, explicit year/timezone and timestamp convention.
Configuration changes create a new semantic profile; names are labels only.
No historical events are backfilled. Profile assumptions remain explicit.

UTF-8, UTF-8 with BOM and explicitly selected Latin-1 are supported. Invalid
UTF-8 is rejected. Explicit source offsets take precedence over configured zones.
Yearless syslog has no current-year default. Ambiguous DST folds and nonexistent
local times withhold UTC. `tzdata` supplies IANA data on Windows.

## Supported records and processing limits

Linux uses anchored sshd accepted/failed password/publickey, invalid user, PAM
failure/session open/close and explicit account-locked denial patterns. It does
not infer session joins or classify arbitrary free-text keywords.

Structured exports support JSON object/array, an `Events` array wrapper, JSONL
and CSV with named fields. Nested `Event.System` and `Event.EventData` are
supported, including XML-converted `@Name`/`#text` and uniquely named Data arrays.
Flat exports use ProviderName, EventID (or Id), Channel (or LogName), Computer
(or MachineName), EventRecordID (or RecordId), TimeCreated and named data fields.
Positional PowerShell Properties arrays are not guessed. Security Event IDs
4624, 4625, 4634, 4648 and 4740 are supported. Conflicting provider/channel is
unsupported; absent values warn that the profile supplies the event family.
Subject/target identities remain distinct. Explicit credentials do not establish
a successful logon. Sysmon 1/3 are contextual process/network events, never
authentication outcomes. IPv4/IPv6 are validated, and placeholders stay missing.

[Microsoft 4648 field definitions](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4648)
and [Sysmon event definitions](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon)
guide the mappings. Original seven-to-nine-digit fractions are preserved while
UTC query projections explicitly disclose microsecond truncation.

Budgets: 10 MiB input, 20,000 records, 32,768 characters per record, depth 16,
200,000 structured nodes and 100 unique CSV columns. Malformed, unsupported and
omitted records have separate accounting. Duplicate JSON keys and non-standard
constants are rejected. Record fingerprints describe decoded lines or canonical
structured records; the original verified byte SHA-256 remains authoritative.

## Frontend dependency remediation

M3 updates the compatible Vite 8 patch range and refreshes transitive lockfile
resolutions (including undici and zod). ESLint/typescript-eslint still requested
vulnerable minimatch 10.x, so a documented minimatch 11.0.1 override supplies the
patched API; Node 22 and the existing lint configuration were tested. No forced
npm audit fix or advisory suppression was used. Both full `npm audit` and
`npm audit --omit=dev` report zero findings and are now enforced in CI. Backend
pip-audit remains enforced. The package manifest preserves the other existing
major ranges rather than adopting npm's suggested unrelated downgrades.

## Verified ingestion and query API

The synchronous `/api/investigations/{id}/events` API enforces active workspace
and case membership on every route. Profile creation, ingestion and recovery
require existing analysis-initiation permissions; archived cases retain the
existing restrictions. Profiles are immutable, deduplicated by configuration,
and limited to 200 per case.

- `GET/POST /profiles`: list/create source interpretations.
- `POST /runs`: `{evidence_id, profile_id}`; durable attempt followed by a locked
  transaction for all events and run memberships.
- `GET /runs?limit=25&offset=0`: bounded coverage/verification history.
- `POST /runs/{id}/recover`: close a stranded running attempt, then retry normally.
  An active ingestion holds the same PostgreSQL case lock, preventing recovery
  from interrupting the analytical transaction.
- `GET /`: exact filters for category, event_type, outcome, username, host,
  source_ip, destination_ip, provider, event_id, evidence_id, profile_id, run_id,
  and offset-aware start/end. Maximum page 200; default 50. Unknown UTC values
  are excluded from time ranges. Stable order: UTC ascending, unknown last,
  then semantic event key. This is pagination, not an incident timeline.
- `GET /{semantic_key}`: bounded event provenance and underlying recorded
  integrity eligibility. No storage keys/paths or unbounded raw records escape.

Event keys hash case/evidence labels, verified input SHA-256, record locator and
fingerprint, profile semantic hash/version, adapter and normalization versions.
Repeated identical lines at different locations remain distinct. Retries reuse
immutable event rows and link them to the new run. Changed interpretation/bytes
or versions create new identities; historical rows remain inspectable. The
normalization version includes packaged tzdata version, and IANA interpretation
uses that package explicitly rather than the host OS database.

Ingestion independently hashes a bounded M1 private snapshot and consumes that
same snapshot. Ready registration and independent verification are mandatory.
Failure/tampering checks append existing verification, custody and audit history.
One transaction persists the entire event set; insertion failure rolls it back.
A running attempt committed before interruption is visible and recoverable.
Lost completion acknowledgements are resolved from persisted status. Database
registration errors return safe 503 messages. Retry never deletes history.

Recognized, unsupported, rejected and omitted counts reconcile to total records.
A complete parse with unsupported records is a partial normalized event set,
not complete semantic coverage. Up to 20 issue locators explain failures without
returning evidence text. Existing events retain their first ingestion provenance;
subsequent run membership and run coverage remain separately queryable.

## Event explorer

The case's Security Events tab provides source-profile configuration/selection,
verified-evidence selection, ingestion and interrupted-run recovery. It displays
all query filters, bounded event/run pagination, empty/error/loading states,
provider/type/outcome context and a provenance drawer with the evidence link,
record locator/fingerprint, exact input digest, source time/UTC projection,
uncertainty, assumptions, attributes and semantic identity. Partial ingestion and
unsupported format feedback remain visible. Recorded integrity eligibility is
not continuous storage monitoring. Historical events remain visible with warnings
when a subsequent check marks their supporting evidence unavailable or mismatched.

UI behavior tests cover immutable profile inputs, unknown-year/zone defaults,
filter and pagination API parameters, event detail provenance, error/empty states,
verified-evidence gating and duplicate-ingestion feedback. Existing design tokens
and shared components are retained.
