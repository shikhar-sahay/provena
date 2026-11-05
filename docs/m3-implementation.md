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
