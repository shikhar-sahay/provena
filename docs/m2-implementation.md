# Provena 2.0 M2 implementation handoff

Baseline: M1 `e9c701dacb104432851785756c97507a2f8cf874`.
M2 preserves the modular monolith and M1 exact-input integrity contract. It does
not add authentication-event schemas, detection families, OCR, a full incident
timeline, model dependencies or background infrastructure. No production
service, evidence or database was accessed or deployed during implementation.

## Implemented behavior

| Finding | Implementation | Main regression coverage |
| --- | --- | --- |
| AI-001 | Full bounded scan text separated from excerpts; distinct occurrence spans and structured coordinates | `test_m2_parsers.py`, `test_ai_pipeline.py` |
| AI-003 | Persisted complete/partial/rejected coverage; PDF page failures, processing budgets and decoder limits | `test_m2_parsers.py` |
| AI-004 | Immutable semantic correlation snapshots, run/artifact membership and versioned finding identities | `test_m2_provenance.py`, `test_postgres_evidence.py` |
| AI-005 | Record-level removable-media observations; ambiguity never becomes an established session | `test_m2_rules.py` |
| AI-006 | Scores equal declared factor totals; actual supporting verification; duplicate/partition safeguards | `test_m2_rules.py` |
| AI-007 | Deterministic authoritative narration; model prose never requested or accepted | `test_narrative.py` |
| AI-008 | Deterministic output selection, explicit counts/limits, persisted evaluation accounting and UI expansion | `test_m2_rules.py` |
| AI-009 | Original times, explicit offsets, precision and unknown timezone preserved; conservative temporal comparison | `test_m2_timestamps.py` |

Backend test paths in this document are relative to `backend/tests/`.
Frontend behavior tests cover parser coverage, source/time semantics, score
reconciliation, result accounting and report compatibility.

## Data and identity contract

Pipeline version is `2`, parser `2.2`, extractor `2.3` and rules `2`. Artifact
extractor versions combine extractor/parser versions, currently `2.3.p2.2`.
A behavior-changing parser/extractor/normalizer change requires a new processing
version; materially changed rules require a new rule version.

`analysis_run_artifacts` records the artifacts actually emitted in a run.
Current reasoning selects the latest completed attempt for each evidence item
under the current processing version. A later blocked or rejected attempt does
not substitute an earlier successful parse. Historical artifacts remain readable.

Correlation semantic hashes include algorithm version, entity type/value and
sorted supporting artifact identities. Artifact identities include evidence ID,
input SHA-256, source occurrence, extractor name and processing version. They
exclude artifact, correlation and run sequence IDs. Changed support creates a
new immutable correlation membership snapshot; `is_current` selects the current
view. Old IDs and memberships remain resolvable.

Finding identities include rule/version, semantic support, claim, score/factors
and parser coverage. Equivalent proposals reuse pending, accepted or rejected
records. Changed support or versions start pending. Old analyst decisions are
not transferred to new claims. Reports snapshot supporting locators, digests,
versions and coverage, and exclude unavailable/stale support. Historical report
content and hashes are never rewritten.

PostgreSQL investigation row locks serialize analysis and proposal persistence.
Tests exercise concurrent registration retries, analysis and finding generation
on a real disposable PostgreSQL instance. SQLite tests alone are not evidence of
PostgreSQL concurrency behavior.

## Coverage and source coordinates

Source text scanned by extractors is distinct from the at-most-280-character
preview. Repeated values at different spans remain distinct occurrences. Spans
are zero-based, half-open Unicode codepoints within the decoded line, CSV cell,
JSON scalar or PDF extracted line. They are not original byte offsets or preview
positions. CSV column ordinals and JSON Pointers disambiguate source fields;
duplicate JSON object keys are rejected instead of silently dropping values.

Limits are declared in `app/ai/parsers.py`: 10 MiB text/CSV/JSON, 25 MiB PDF,
10,000 characters per source value, 50,000 source units, 2,000,000 scanned
characters, JSON depth 20/path length 1,000, 10,000 artifacts per evidence and
500 codepoints per extracted value. PDF processing examines at most 50 pages,
with 2 MiB decoded stream and 10 MiB total page-content budgets. CSV reader field
limits also apply. Rejected byte/format limits are distinct from partial prefix,
record, page and artifact coverage. PDF decoder limits use context-local pypdf
configuration, requiring `pypdf>=6.21.4,<7`.

Run outcomes preserve coverage warnings and PDF total/processed/skipped pages,
reasons and unprocessed-page counts where available. A completed run means its
selected items were attempted, not that all source content was covered. The UI
marks omissions and unknown historical coverage, and findings from partial
sources carry an explicit qualification.

## Scores and result accounting

Scores are deterministic support rankings, never calibrated probabilities:

- Identity recurrence: 30 plus up to 65 from distinct supporting record patterns.
  Copies and partitions do not create additional patterns or prove independence.
- Removable media: 20 for a recorded device, 35 only for a unique user/host/device
  in one structural record, and 10 for verified supporting inputs. Missing or
  ambiguous fields remain qualified observations, not established sessions.
- Upload sequence: 25 for the shared link, 15 for a file reference, 20 for temporal
  order and 10 for supporting verification. Link artifacts are included in support.

Temporal sequences require explicit upload/file-access cues, comparable
second-or-finer offset-aware timestamps and strictly positive separation within
24 hours. An offset does not prove clock accuracy or destination ownership.
Naive times, DST ambiguity and negative-zero offsets remain unknown. Unsupported
fractional precision is not silently shortened. Original timestamp text remains
available in locators and report support.

`POST .../analysis/findings/generate?per_rule_limit=25` accepts 1 through 200
proposals per rule. Counts of enumerated/emitted/omitted proposals and the input
set hash persist in the generation audit event. `GET .../analysis/findings/coverage`
retrieves that last evaluation; it is not continuous monitoring after new evidence.
Reports preserve its accounting. Selection uses semantic tie-breaking before
limits, so artifact sequence allocation cannot change which proposals are selected.
Upload pairing stops at 100,000 candidate comparisons and explicitly marks total
possible results unknown if that budget is exhausted. Raising the output limit
does not override processing limits.

## Narrative safety and historical compatibility

Authoritative reports use deterministic templates and exact accepted finding
text. Legacy `LLM_ENABLED`/Ollama configuration and availability probing remain,
but no model generation request is made for a report. Notes, case descriptions
and uploaded content cannot instruct a narrator. Literal/ID validation was
removed as an insufficient semantic assurance mechanism. Old model-generated
reports remain unchanged, with a visible warning that their prose was not
revalidated under M2.

## Migration and recovery considerations

Forward-only migrations:

1. `c83d2f95a014_parser_coverage.py`: nullable historical run coverage.
2. `d94e30a6b125_stable_support.py`: run/artifact membership, immutable correlation
   keys/current flags and finding support snapshots.

Legacy coverage, memberships and semantic support are not invented or backfilled.
Historical decisions remain recorded but do not become new M2 approvals. Reanalyze
verified evidence and review new proposals to obtain current M2 support. Applying
these migrations to production requires separately authorized deployment work.

A populated M1 PostgreSQL upgrade was checked with synthetic evidence, an accepted
finding, correlation memberships and an immutable report. Upgrade and schema drift
checks passed; the original review, membership references and report hash remained
unchanged. Legacy support stayed explicitly historical.

Repeated local PostgreSQL testing exposed an intermittent Windows extended-path
namespace comparison failure in staging. Local storage now normalizes only the
comparison representation of resolved paths; traversal/symlink containment and
original I/O paths remain enforced. Namespace and concurrent staging tests cover it.

## Verification and reproducibility

Run from `backend/` in an isolated environment with `APP_ENV=test`, an empty
`DATABASE_URL`, local evidence storage and synthetic fixtures:

```text
python -m pip install -r requirements.txt
python -m pip check
python -m pip_audit -r requirements.txt
python -m pytest -q
python tests/benchmark_analysis.py
```

For PostgreSQL, use only a disposable loopback database named `provena_ci`, set
`M1_POSTGRES_TEST_URL` to it, apply `alembic upgrade head`, run `alembic check`,
and execute `python -m pytest tests/test_postgres_evidence.py -q`. CI provisions
PostgreSQL 16 for this job. Local checks used standalone PostgreSQL 16.15 because
Docker was unavailable; the temporary server is stopped after verification.

From `frontend/`: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`,
`npm run build`. Review `git diff --check` and the explicitly staged diff before
committing. Final exact counts and CI conclusions belong to the milestone report;
local untracked configuration tests intentionally remain outside the committed suite.

The committed benchmark creates only synthetic evidence, in-memory SQLite and
new temporary storage. Its measured M1/M2 comparison and limitations are recorded
in [analysis architecture](ai-architecture.md). It is not a production capacity test.

## Remaining limitations and focused follow-up

- S3 behavior is tested with a synthetic provider, not live AWS infrastructure.
- Parser limits do not constitute an operating-system sandbox for hostile PDFs.
- Rule scores and co-occurrences do not establish compromise, intent or guilt.
- Existing sample logs have unknown source timezones and do not establish UTC
  cross-source temporal sequences. Future source profiles require explicit design.
- Frontend dependency auditing reported 13 existing development advisories
  (10 moderate, 3 high), including Vite, undici and zod. The production dependency
  graph reported zero with `npm audit --omit=dev`. The frontend manifest/lockfile
  were not changed or blanket-upgraded as unrelated M2 work. Remediate the build
  tooling in a focused follow-up; a clean backend pip audit does not cover it.
- Custody remains application-level append-only, not cryptographically tamper-proof.
- Synchronous processing and per-case locks remain intentional; benchmark before
  raising budgets or adding event normalization in the next milestone.
- Existing deployment/configuration work, environment templates, audit documents
  and protected migration backups remain separate from M2 commits.
