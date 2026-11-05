# Synthetic M5 recovery and export demonstration

This scenario generates invented authentication records at runtime through the actual
application APIs. It does not use personal data, real credentials or production services.
The M4 scenario remains available in `../m4-authentication/`.

Use an isolated PostgreSQL 16 instance on localhost, with a dedicated `provena_ci`
database and a disposable database owner allowed to create new databases. Install the
backend requirements and matching PostgreSQL native client utilities. Never point the
demonstration at a live application database or existing evidence directory.

From `backend/`, configure `M1_POSTGRES_TEST_URL` to the dedicated localhost
`postgresql+psycopg2://.../provena_ci` URL. Set `M5_PG_BIN` to the matching native
utility directory when it is not on PATH. Run:

```sh
python -m pytest tests/test_m5_recovery.py -q -s
```

The executable demonstration creates randomly named `provena_backup_*` and
`provena_restore_*` databases and private temporary evidence/cache directories. It:

1. Creates a workspace, investigator, unrelated account and case.
2. Uploads synthetic SSH failures/success, verifies original SHA-256, creates a profile,
   ingests events, selects an immutable event set and executes real detection logic.
3. Accepts a finding and generates an immutable report.
4. Creates an originals export, downloads it, verifies the archive, alters a copy and
   confirms rejection.
5. Makes two concurrent idempotent export requests and checks that they share one row.
6. Creates a native custom-format PostgreSQL backup from one exported snapshot while
   committing an annotation after that boundary.
7. Restores into fresh empty targets, validates every table fingerprint and report hash,
   and confirms that the post-boundary annotation is absent.
8. Logs in through the restored application, checks event/timeline/findings/report/export
   access and confirms that the unrelated account still cannot access the case.
9. Rejects a populated restore target and an incorrect independently supplied digest.

`M5_POSTGRES_RECOVERY` output records the measured backup/restore durations. Databases
are intentionally retained for inspection; the test never drops an existing database.
Stop/remove only the disposable PostgreSQL instance you created when finished. Repeated
demonstrations create fresh names and do not overwrite old resources.

For archive attacks, failure injection, local/fake-S3 snapshots and configuration checks:

```sh
python -m pytest tests/test_m5_exports.py tests/test_m5_archive_attacks.py tests/test_m5_operations.py tests/test_m5_maintenance.py -q
python -m pytest tests/test_m5_capacity.py -q -s
```

The capacity example uses SQLite and 2000 events plus a 16 MiB opaque synthetic original;
its local timings and Python allocation measurements are not PostgreSQL or EC2 capacity
claims. The fake-S3 tests do not contact AWS. See `docs/operations.md` for private real
backup handling, schema compatibility, retention and recovery commands.
