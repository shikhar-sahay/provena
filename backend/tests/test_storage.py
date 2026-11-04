"""Storage backend contract tests. All S3 behavior uses an in-memory fake."""

import hashlib
import io

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.evidence.models import CustodyEvent
from app.modules.evidence import storage
from tests.conftest import auth_headers, login
from tests.test_evidence import make_investigation, upload


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.uploads = {}
        self.fail_operation = None
        self.aborted = []

    def _fail(self, operation):
        if self.fail_operation == operation:
            raise RuntimeError(f"{operation} failed")

    def create_multipart_upload(self, Bucket, Key):
        self._fail("create")
        upload_id = f"upload-{len(self.uploads) + 1}"
        self.uploads[upload_id] = {"key": Key, "parts": {}}
        return {"UploadId": upload_id}

    def upload_part(self, Bucket, Key, UploadId, PartNumber, Body):
        self._fail("upload")
        self.uploads[UploadId]["parts"][PartNumber] = bytes(Body)
        return {"ETag": f"etag-{PartNumber}"}

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
        self._fail("complete")
        parts = self.uploads.pop(UploadId)["parts"]
        self.objects[Key] = b"".join(parts[index] for index in sorted(parts))

    def abort_multipart_upload(self, Bucket, Key, UploadId):
        self.aborted.append(UploadId)
        self.uploads.pop(UploadId, None)

    def copy_object(self, Bucket, Key, CopySource):
        self._fail("copy")
        self.objects[Key] = self.objects[CopySource["Key"]]

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def get_object(self, Bucket, Key):
        self._fail("get")
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):
        self._fail("head")
        if Key not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[Key])}


def make_s3():
    fake = FakeS3()
    return storage.S3EvidenceStorage("private-bucket", "us-east-1", client=fake), fake


def test_local_storage_round_trip_and_hash(tmp_path):
    backend = storage.LocalEvidenceStorage(tmp_path)
    payload = b"synthetic evidence bytes"
    staged = backend.stage(io.BytesIO(payload), 7, 1024)
    backend.finalize(staged)
    with backend.open(staged.storage_key) as handle:
        assert handle.read() == payload
    assert backend.sha256(staged.storage_key) == hashlib.sha256(payload).hexdigest()


def test_s3_storage_round_trip_and_byte_integrity():
    backend, fake = make_s3()
    payload = b"x" * (storage.S3_PART_SIZE + 17)
    staged = backend.stage(io.BytesIO(payload), 3, len(payload))
    assert staged.sha256 == hashlib.sha256(payload).hexdigest()
    backend.finalize(staged)
    assert staged.storage_key in fake.objects
    assert staged.staging_ref not in fake.objects
    with backend.open(staged.storage_key) as handle:
        assert handle.read() == payload
    assert backend.sha256(staged.storage_key) == staged.sha256


@pytest.mark.parametrize("payload,max_bytes,error", [
    (b"", 10, ValueError),
    (b"too large", 3, OverflowError),
])
def test_s3_rejects_empty_and_oversized_uploads(payload, max_bytes, error):
    backend, fake = make_s3()
    with pytest.raises(error):
        backend.stage(io.BytesIO(payload), 1, max_bytes)
    assert not fake.uploads
    assert not fake.objects


def test_s3_interrupted_upload_is_aborted():
    backend, fake = make_s3()

    class BrokenStream:
        calls = 0
        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b"partial"
            raise OSError("connection interrupted")

    with pytest.raises(OSError):
        backend.stage(BrokenStream(), 1, 100)
    assert fake.aborted
    assert not fake.uploads


@pytest.mark.parametrize("operation", ["create", "upload", "complete", "copy", "head", "get"])
def test_s3_api_failures_are_propagated(operation):
    backend, fake = make_s3()
    fake.fail_operation = operation
    if operation in {"copy", "head"}:
        fake.fail_operation = None
        staged = backend.stage(io.BytesIO(b"data"), 1, 100)
        fake.fail_operation = operation
        with pytest.raises(RuntimeError):
            backend.finalize(staged)
        assert staged.staging_ref in fake.objects
    elif operation == "get":
        with pytest.raises(FileNotFoundError):
            with backend.open("1/" + "a" * 32):
                pass
    else:
        with pytest.raises(RuntimeError):
            backend.stage(io.BytesIO(b"data"), 1, 100)


def test_s3_missing_and_tampered_objects():
    backend, fake = make_s3()
    staged = backend.stage(io.BytesIO(b"original"), 1, 100)
    backend.finalize(staged)
    fake.objects[staged.storage_key] = b"tampered"
    assert backend.sha256(staged.storage_key) != staged.sha256
    del fake.objects[staged.storage_key]
    with pytest.raises(FileNotFoundError):
        backend.sha256(staged.storage_key)


def test_s3_failed_promotion_retains_reconcilable_staging_object():
    backend, fake = make_s3()
    staged = backend.stage(io.BytesIO(b"recoverable"), 9, 100)
    assert staged.staging_ref == storage.staging_key_for(staged.storage_key)
    assert storage.storage_key_from_staging(staged.staging_ref) == staged.storage_key
    fake.fail_operation = "copy"
    with pytest.raises(RuntimeError):
        backend.finalize(staged)
    assert fake.objects[staged.staging_ref] == b"recoverable"


def test_s3_read_timeout_is_sanitized_and_body_closed(monkeypatch):
    backend, fake = make_s3()
    class TimeoutBody:
        closed = False
        def read(self, size=-1):
            raise RuntimeError("private-provider-url")
        def close(self):
            self.closed = True
    body = TimeoutBody()
    monkeypatch.setattr(fake, "get_object", lambda **_: {"Body": body})
    with pytest.raises(OSError, match="Stored evidence stream is unavailable"):
        with backend.open("1/" + "a" * 32) as handle:
            handle.read(1)
    assert body.closed


@pytest.mark.parametrize("key", ["../secret", "1/not-hex", "/absolute", "0/" + "a" * 32])
def test_invalid_storage_keys_are_rejected(key):
    backend, _ = make_s3()
    with pytest.raises(ValueError):
        with backend.open(key):
            pass


def test_s3_backed_analysis_and_authorized_download(
    client, investigator, storage_dir, db_session, monkeypatch
):
    backend, _ = make_s3()
    monkeypatch.setattr(storage, "get_storage", lambda: backend)
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(
        client, token, inv["id"],
        content=b"user=j.smith host=WS-17 from 192.0.2.10\n",
        filename="auth.log",
    ).json()
    verified = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    assert verified.json()["result"] == "verified"
    run = client.post(
        f"/api/investigations/{inv['id']}/analysis/runs",
        headers=auth_headers(token),
        json={"evidence_ids": [item["id"]]},
    )
    assert run.status_code == 201
    assert run.json()["artifact_count"] > 0
    download = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/download",
        headers=auth_headers(token),
    )
    assert download.content.startswith(b"user=j.smith")
    assert client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/download"
    ).status_code == 401
    assert db_session.execute(select(CustodyEvent)).scalars().all()
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "EVIDENCE_REGISTERED" in actions
    assert "EVIDENCE_VERIFIED" in actions
    assert "EVIDENCE_DOWNLOADED" in actions
