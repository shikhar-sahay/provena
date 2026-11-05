# Investigator guide

Use only synthetic or explicitly authorized evidence. Provena is an experimental
workbench, not certified forensic software. A detection is an observed pattern to review,
not proof of malicious intent. This guide describes the current UI.

## Account, workspace and case

1. Choose **Create account** from sign-in, register and create a workspace or join with
   an administrator's invite code. A new workspace makes its creator administrator.
2. Use **Account menu > Switch workspace** to select another authorized workspace.
   Case lists and permissions follow the selected workspace. Suspension does not remove
   access to other authorized workspaces.
3. Choose **New investigation**, supply a title, scope, priority and lead. Open cases
   from **Investigations**; use search/status filtering. Case managers assign workspace
   members to the case. Archived investigations are read-only for ordinary mutations.

## Register and verify evidence

Open the case **Evidence** tab, choose **Register evidence**, select a synthetic file,
set its title/type/source and submit. Registration must be `ready` before verification.
A SHA-256 baseline represents the original uploaded bytes; it is not a legal custody
certificate. Managers/custodians choose **Verify integrity** on the evidence page.

`not_verified`, `verified`, `mismatch` and `unavailable` are distinct. Pending/failed
registrations are not analysis eligible. Do not replace bytes under an existing evidence
record; register changed source material separately. Recovery controls close incomplete
operations; they do not invent missing files or repair altered evidence. Custody and
verification histories retain actors, times and outcomes. Only storage abstractions
handle evidence paths; API-visible evidence IDs are safe navigation references.

## Source interpretation and ingestion

In **Security Events**, choose verified evidence and **Configure source profile**.

| Evidence | Adapter | Format | Time assumptions |
| --- | --- | --- | --- |
| OpenSSH/PAM auth.log/secure text | Linux authentication | Syslog | Leave unknown year/timezone blank |
| Named Windows Security exports | Windows Security | JSON, JSONL or CSV | Preserve source offsets; supply explicit fallback only when justified |
| Structured Sysmon IDs 1/3 | Sysmon context | JSON, JSONL or CSV | Context, never authentication verdicts |

Give the immutable profile a name. Encoding options are UTF-8, BOM-aware UTF-8 and explicit
Latin-1. A new interpretation creates a new profile, not a rewrite of history. Never guess
the current year or UTC for yearless local logs. Click **Save source profile**, select
**Evidence to ingest** and **Source interpretation profile**, then **Ingest verified evidence**.

Inspect **Ingestion status and record coverage**. Recognized, unsupported, rejected and
omitted records are separate; partial coverage is not complete coverage. Limits include
10 MiB, 20000 records and 32768 characters per record. Native EVTX, arbitrary XML,
positional Properties arrays and OCR are unsupported. Windows IDs 4624/4625/4634/4648/4740
and Sysmon 1/3 have conservative mappings. **Inspect event** shows evidence digest,
profile/version, locator, fingerprint, time semantics and warnings. Evidence links return
to the original source record's evidence page.

Filters operate on the server; pages show at most 50 events in the UI. Clear or change
filters when results are empty. Unknown-time events are not treated as UTC range matches.
Repeated ingestion reuses logical event identities and retains separate run history.

## Authentication workbench

For the separate artifact workflow, open **AI Analysis > Run analysis** and select
eligible verified TXT/LOG, CSV, JSON or machine-readable PDF evidence. Inspect parser
coverage, **Artifacts** and **Correlations** before opening **Findings > Evaluate rules**.
This legacy path uses explicit weighted heuristic factors, not compromise probabilities.
It does not create normalized security events or replace source-profile ingestion.
Managers/assigned analysts may produce results where authorized; human acceptance is
still required before general reports include current supported findings.

1. Open **Authentication**, expand **Create a selection from ingestion runs**, choose
   the intended runs and save a named event set. Select one interpretation per source.
   Identical reingestions and copied observations cannot inflate independent attempts.
   The selection limit is 10000 events; oversized inputs are rejected, not silently dropped.
2. Review source coverage, duplicate accounting and time assumptions. Adjust validated
   thresholds only when justified. **Run detections** evaluates repeated failures,
   password spraying, success after failures, explicit lockouts and mixed-outcome bursts.
3. Open a result to inspect exact thresholds, entities, supporting event identities,
   severity rationale, source locators and limitations. Shared/NAT IPs do not identify
   actors. Missing domains/hosts are not silently merged into one account.
4. Case managers can **Accept finding** or **Reject finding** with an **Analyst review
   note**. **Save annotation** adds a separate investigation note. Analysts can inspect
   and annotate where authorized; review authority remains with managers.
5. **Explore supporting events in timeline** restricts to exact support. Click an account,
   IP or host to inspect related activity; use the return control to preserve context.
   **Time interpretation** separates source UTC, profile-assumed and unknown/ambiguous
   lanes. Do not read list position or equal timestamps as causal order.
6. Reingest unchanged evidence, select equivalent inputs and rerun. Findings and prior
   decisions remain stable. Changed inputs/profiles/rule semantics require fresh review.
   Historical or unavailable support cannot enter current accepted conclusions.

## Reports and exports

**Generate reviewed report** in Authentication freezes that selected event set, executed
rules, coverage, current accepted findings and a separate decision inventory. General
**Reports > Generate report** excludes unselected authentication conclusions. Open past
reports without regenerating them; old content hashes remain unchanged. Unreviewed and
rejected proposals are not accepted conclusions.

In **Exports**, metadata-only is the default. Select explicit event sets and reports;
originals require case-management permission, a separate mode and explicit verified
files. Metadata still contains confidential case information and source excerpts.
Preparation is synchronous and operation history is durable. After a lost response,
reload history before retrying; unchanged retries reuse the request key. A browser
refresh can lose its in-memory retry key, so inspect history first.

**Download export #...** obtains a hash-checked package. A failed download can retry the
same completed operation. Managers can **Recover interrupted or prune expired** packages;
nonexpired completed packages are retained. Default retention is 24 hours; physical cache
cleanup requires the operator's maintenance procedure. Size/record limits fail explicitly.

```sh
# From backend/, standard-library verifier, no extraction or execution:
python -m app.ops.archive downloaded-export.zip
```

Verify package structure, provenance, file digests and embedded report/original hashes.
Unsigned consistency is not authenticity. Protect originals and hash references through
independent controlled channels. See [operations](operations.md) for private system backup;
a portable case export is not a database restore package.

## Reproducible evaluation

Use the [M4 synthetic fixture guide](../sample-data/m4-authentication/README.md) for the
51-event, five-family scenario. [Browser instructions](development.md) automate that real
journey, including both browser downloads and offline verification, on disposable systems.
Known limits and release decisions are in [M6 readiness](m6-implementation.md).
