# Gate 1: legacy recovery execution proposal

**NOT APPROVED OR EXECUTED.** This is the concrete proposal for backing up the
legacy installation and rehearsing recovery. It does not authorize M6 deployment.
Use the owner's private worksheet for the exact existing instance, bucket, service,
paths, run identifier and trusted digests. Do not copy those private identifiers,
keys, backups or investigation records into this repository or CI.

## Scope and two separate approvals

Source: application `9024ccd55c89c84876aeb5d7ea3b352f108fb5c1`, PostgreSQL 16.15,
Alembic `9b6e5c4d3a21`. Gate 1 may access original evidence only after explicit
approval. It may stop the existing API service, copy its consistent database and
evidence state, encrypt and transfer that copy, and restore/migrate isolated targets.
It must not migrate production, install a new application, change application
configuration, modify Nginx/IAM, create resources or touch the original evidence.

The proposed maximum service interruption budget is **15 minutes**, an operator
limit, not a measured duration prediction. Explicit Gate 1 permission is also needed
to start **only the unchanged legacy service** after closing and verifying the
backup boundary. This narrow exception avoids keeping the website offline through
the local restore rehearsal. If that exception is not granted, service resumption
requires another instruction. M6 startup remains Gate 2 only.

Gate 2 is separately requested after backup, key recovery, off-host verification,
real-baseline restore, six-migration rehearsal and historical comparison succeed.
If legacy writers resume, Gate 2 must include a fresh final consistent backup and
validation of changes since rehearsal. A Gate 1 snapshot is not indefinitely current.

## Observations and remaining prerequisites

On 6 November 2026, bounded read-only inspection reconfirmed the old source/schema
and active legacy service. Existing host tools include PostgreSQL 16.15 native
clients, OpenSSL 3.5.8, AWS CLI 2.36.47 and curl. No installation is needed for the
proposed encryption and transfer. This inspection did not read original evidence.

The existing private operations bucket has Block all public access On and Bucket
owner enforced, verified in the owner's console. Its previously inspected defaults
are SSE-S3, no versioning/Object Lock, no lifecycle or replication. The instance role
cannot read the bucket public-access policy; no IAM change was attempted. Object
upload permission is **unverified**. No current backup or recovery proof follows
from the bucket's existence or its `migration/` prefix.

The Windows 11 Home recovery PC has about 15.65 GiB RAM and 41.4 GiB free on C: at
inspection, OpenSSL 3.5.2 and PostgreSQL 16.15 utilities. Existing synthetic fixtures
are not an approved real-data restore environment. Free space must be refreshed
before use. Volume encryption and independent recovery-key storage require owner
confirmation. NTFS permissions alone do not encrypt a folder.

Before requesting execution, the owner must:

1. Confirm Windows Device Encryption is On and its recovery key is saved independently,
   or identify an already encrypted owner-controlled volume. Do not send its recovery
   key. If unavailable, stop: do not place real backup/plaintext data there. Enabling
   encryption is a separate manual owner action, not something this plan automates.
2. Choose a recovery directory outside Git, browser sync and OneDrive on that encrypted
   volume. Restrict it to the owner and SYSTEM; inspect effective permissions. Keep
   plaintext, PostgreSQL data/WAL, evidence copies and temporary files under it.
3. Generate the dedicated passphrase-protected recovery key manually as below. Retain
   an independent protected key copy and a separate passphrase recovery method.
4. Approve the exact private worksheet, including the current host, unique staging
   paths, existing bucket/prefix, local targets and retention responsibility.

Windows Home can support Device Encryption; do not assume EFS or enterprise BitLocker
management is available. See [Microsoft Device Encryption](https://support.microsoft.com/en-us/windows/security/encryption/device-encryption-in-windows).

## Owner-only encryption key ceremony

The owner performs these commands in a private local terminal, outside screen sharing
or agent control. Use the verified installed OpenSSL executable, a new private key
directory on the confirmed encrypted volume, and fresh output names. Never put a
passphrase in arguments, environment variables, shell history, chat or a transcript.
Use a password-manager-generated strong passphrase, preferably at least 128 bits of
generated entropy. These commands prompt interactively:

```text
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -aes-256-cbc -out owner-recovery-key.pem
openssl req -new -x509 -key owner-recovery-key.pem -sha256 -days 3650 -subj "/CN=Provena Recovery Recipient" -addext "basicConstraints=critical,CA:FALSE" -addext "keyUsage=critical,keyEncipherment" -out recipient.pem
openssl x509 -in recipient.pem -noout -fingerprint -sha256
```

Only `recipient.pem` and its confirmed SHA-256 certificate fingerprint are supplied
to the backup operator. It is a self-signed encryption recipient certificate, not a
TLS certificate to install in a trust store. The operator does not read the private
key or passphrase. Certificate expiry does not replace a key-retention policy.

Store another encrypted copy of the private key on independently controlled encrypted
offline storage. Keep the passphrase in a separate recoverable password manager or
other owner-approved escrow. Record who can recover both and test that recovery using
a synthetic encrypted challenge before any production backup. Losing either key or
passphrase makes the backup unrecoverable. Device Encryption recovery and CMS key
recovery are separate requirements. Do not delete either recovery copy after a test.

## Ciphertext-only transfer proof, before downtime

After Gate 1 approval, first encrypt a synthetic challenge on the existing EC2 host
using only the public recipient certificate. Upload it under the unique approved
prefix in the existing bucket, download it to the protected PC directory and have
the owner decrypt it manually. This checks real transfer permission and recipient
key recovery without accessing original evidence or stopping the service.

Use authenticated CMS AES-256-GCM, RSA-3072 OAEP with SHA-256 and streaming output.
The following template was tested with throwaway synthetic keys; operator paths
must come from the approved private worksheet:

```sh
openssl cms -encrypt -stream -binary -aes-256-gcm -recip "$RECIPIENT_CERT" \
  -keyopt rsa_padding_mode:oaep -keyopt rsa_oaep_md:sha256 \
  -in "$CLOSED_PACKAGE" -outform DER -out "$CIPHERTEXT"
```

With `-stream`, OpenSSL emits streaming BER, even though the output option is named
DER. OpenSSL CMS decrypt accepts it with `-inform DER`. On the owner PC, manually:

```text
openssl cms -decrypt -binary -inform DER -in backup.cms -recip recipient.pem -inkey owner-recovery-key.pem -out quarantine-package.tar
```

Decrypt only to a new quarantine file on the encrypted volume. OpenSSL can emit
plaintext before authenticating the final tag. Require successful exit, the expected
plaintext digest and manifest verification **before** extracting or restoring. Never
pipe decryption directly to `pg_restore`. Reject and remove only the failed owned
quarantine output on authentication failure, retaining ciphertext and diagnostics.
See [OpenSSL CMS behavior](https://docs.openssl.org/3.5/man1/openssl-cms/).

Transfer only ciphertext over HTTPS. Use the existing role and unique object name,
conditional `PutObject` with `--if-none-match '*'`, SSE-S3 and SHA-256 checksum headers.
No public ACL or public download URL, credentials in arguments, bucket changes,
overwrite or IAM changes. Use the existing owner console for download if local AWS
authentication is unavailable. A permission failure aborts this route before downtime.
See [AWS PutObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-object.html).

Compare the complete ciphertext SHA-256 on EC2, S3's full-object SHA-256 checksum and
the downloaded PC file. Do not use multipart/composite checksums or ETags as a full
SHA-256 substitute. Retain trusted digests independently in the owner's private record.
The public certificate fingerprint must be confirmed independently before encryption;
a changed recipient or ciphertext must not be accepted by simply updating the record.

S3 is an additional encrypted off-host copy, not the only recovery copy. Versioning
and Object Lock are absent, so the object is not WORM-protected. Retain the PC copy
and independent key recovery material under an explicit owner retention policy. This
plan creates no bucket, paid service or infrastructure; existing S3 request/storage
charges remain possible and require acceptance for the approved transfer.

## Consistent legacy backup, only after Gate 1

1. Recheck exact host, source/schema, service, free space and no tracked source changes.
   Record a private operation identifier. Stop if baseline differs. Reserve measured
   space for a complete plaintext package, ciphertext, temporary copies and rollback.
2. Create only the new approved private EBS-backed staging directory, outside checkout,
   original storage and web roots, with mode 700 and files 600. Use a process-local
   disk-backed temporary directory. Do not change the running application's environment.
3. Stop the approved API service; verify it is inactive and exclude other CLI, schema,
   maintenance and external writers. Nginx isolation alone is insufficient. Do not stop
   PostgreSQL or modify proxy configuration. Record the consistent boundary in UTC.
4. Use matching native `pg_dump --format=custom --no-owner --no-acl`. Use existing
   private connection mechanisms without passwords in logs/arguments. Verify the dump
   with `pg_restore --list`; structural listing alone is not a restore proof.
5. Under the same writer fence, retain a complete source evidence copy with generated
   keys and permission metadata. Reject symlinks, escaping paths and special files.
   Reconcile every DB reference and baseline digest, including missing/mismatched or
   unreferenced files explicitly. Do not silently omit an anomaly or edit source data.
6. Capture all legacy table counts and ordered original-field hashes, plus report-hash
   validation. The optional [projection helper](../tools/legacy_projection.py) receives
   an already authorized consistent SQLAlchemy connection and has no CLI or credential
   discovery. Use UTC sessions on both sides, keep its inventory private, and stop at
   its row budget. It is not a substitute for evidence-byte/report verification.
7. Include the old source revision, private installed dependency inventory, old static
   assets and confirmed persistent generated files. Retain the old checkout/venv.
   Record separately protected recovery references for secrets, DB roles/grants and
   service/proxy/TLS configuration. Do not casually dump environment files into logs.
8. Close a manifest with source/schema, file inventory, sizes, SHA-256, evidence/report
   references and omissions. Package only reviewed regular files, relative paths and
   no links. Record its trusted plaintext digest privately, then encrypt with the
   already challenged recipient and transfer/verify ciphertext as above.
9. Resume only the unchanged old service if that narrow action was expressly approved,
   the source is intact and no integrity discrepancy exists. Keep the website fenced
   and ask the owner if data discrepancies or ambiguous state appear. At the downtime
   budget, abort safely rather than bypassing a failed verification.

Private ACLs, EBS/PC encryption and CMS protect different boundaries. Plaintext staging
exists temporarily on the encrypted EC2 volume; **no plaintext is transferred off-host**.
Do not claim cryptographic signatures or independent authenticity from ordinary hashes.
Only clean up the unique owned staging after independently verified copies and key
recovery exist; do not delete originals, the only backup, private manifests or history.

## Real-baseline restore and migration rehearsal

Create a fresh PostgreSQL 16.15 cluster under the protected PC recovery directory,
bound only to loopback on the privately approved unused port. Use SCRAM authentication
and private credentials, not the existing synthetic trust-authenticated CI cluster.
Keep database/WAL, copied originals, exports and all temporary outputs on the encrypted
volume. The target must be empty; refuse an existing database or nonempty evidence
root. Native restore executes trusted SQL, so do not restore untrusted packages.

After owner decryption succeeds, validate archive paths, file counts, size budgets,
manifest and every digest before extraction. Restore the native dump and originals
into fresh isolated targets, never production. Keep network access private and avoid
external services or uploads. Compare all old field projections, credentials/account
hashes, workspace/case identities, evidence digests, custody/verification history,
notes, accepted/rejected decisions and immutable report content/hashes.

Then migrate a retained clone through:

```text
9b6e5c4d3a21 -> b72a1e84c903 -> c83d2f95a014 -> d94e30a6b125
 -> 294d21d0205e -> 53d6b8a0e88b -> ee5b99eb5ce4
```

Require `alembic check`, configuration preflight, private readiness and the same old
field/report/evidence checks after migration. Do not repeat workspace backfill or stamp
head. Test authorization using owner-approved isolated credentials; any clone-only test
account change comes after baseline comparison and never modifies production accounts.
Measure duration, memory, disk/WAL/temp growth and preserve the unmigrated restore.
Windows PC measurements do not prove the 913 MiB EC2 host's peak capacity.

## Evidence record and stop conditions

Record approvals privately with timestamps and exact scope. Gate 1 succeeds only after
all of the following: complete consistent backup, confirmed recipient, independent
ciphertext digests, encrypted PC and S3 copies, manual decryption, fresh restore,
historical comparison, six migrations, drift/preflight and recovery-key availability.
There is no claim any of these real-data operations has happened during preparation.

Stop for missing encryption/key escrow, denied transfer, changed baseline, other
writers, unsafe paths, missing/corrupt evidence, ambiguous dump/transfer, insufficient
capacity, failed restore, changed historical fields/report hashes, migration errors or
missing approval. Preserve originals and failed-target diagnostics. No blind downgrade,
production reset, configuration change or deployment is a Gate 1 recovery action.

## Preparation validation, not production proof

Synthetic CMS AES-256-GCM streaming encryption with RSA-3072 OAEP/SHA-256 round-tripped
1,277,952 bytes using throwaway keys. Modified and truncated ciphertext failed to
decrypt successfully. The owner key has not yet been generated or tested.

The synthetic native PostgreSQL test restores the confirmed old schema, compares every
old field before/after the six-migration upgrade and checks drift/report/evidence
integrity. Unit tests reject changed/deleted historical rows, missing tables, wrong
revisions, row-budget exhaustion and an empty inventory. These do not satisfy the
actual-baseline restore gate. The final commit/CI result belongs in the handoff, not
in an assertion that preparation is deployment authorization.

The reviewed-index source export passed **57 tests in 50.05 seconds** with disposable
PostgreSQL 16.15, including the native legacy restore/upgrade and nine PostgreSQL
cases. One existing Starlette test-client deprecation warning remains. Command from
`backend/` with the guarded localhost control DB and native utility directory set:

```sh
python -m pytest tests/test_postgres_evidence.py tests/test_m5_recovery.py tests/test_m5_operations.py tests/test_m6_tools.py tests/test_deployment_gate.py tests/test_legacy_recovery.py tests/test_legacy_projection.py -q
```

`python tools/check_docs.py` checked 32 tracked Markdown documents without errors.
The offline deployment gate reverified the frozen candidate's 336 files and SHA-256
`b43522ee5a86f6588daf9ba60c3ed906aab254e2f770af9b0e3a30dbfced5e03`;
its output remains `deployment_authorized=false`. Staged-file checks found no private
instance/bucket identifiers, original root paths, private-key patterns or U+2014.
