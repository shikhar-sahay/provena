"""Private evidence storage with local and S3 implementations."""
from __future__ import annotations

import hashlib
import os
import re
import uuid
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, ContextManager, Iterator, Protocol

from app.core.config import settings

CHUNK_SIZE = 1024 * 1024
S3_PART_SIZE = 5 * 1024 * 1024
_KEY_PATTERN = re.compile(r"^[1-9][0-9]*/[0-9a-f]{32}$")


@dataclass(frozen=True)
class StagedUpload:
    storage_key: str
    staging_ref: str
    sha256: str
    size: int


class EvidenceStorage(Protocol):
    def stage(self, stream: BinaryIO, investigation_id: int, max_bytes: int) -> StagedUpload: ...
    def finalize(self, upload: StagedUpload) -> None: ...
    def discard(self, upload: StagedUpload) -> None: ...
    def open(self, storage_key: str) -> ContextManager[BinaryIO]: ...
    def sha256(self, storage_key: str) -> str: ...


def validate_storage_key(storage_key: str) -> str:
    if not _KEY_PATTERN.fullmatch(storage_key):
        raise ValueError("Invalid evidence storage key.")
    return storage_key


def staging_key_for(storage_key: str) -> str:
    return f".staging/{validate_storage_key(storage_key)}"


def storage_key_from_staging(staging_key: str) -> str:
    prefix = ".staging/"
    if not staging_key.startswith(prefix):
        raise ValueError("Invalid evidence staging key.")
    return validate_storage_key(staging_key.removeprefix(prefix))


class LocalEvidenceStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root.resolve()

    def resolve(self, storage_key: str) -> Path:
        validate_storage_key(storage_key)
        root = self._root()
        candidate = (root / Path(*storage_key.split("/"))).resolve()
        if root not in candidate.parents:
            raise ValueError("Storage key escapes the storage root.")
        return candidate

    def stage(self, stream: BinaryIO, investigation_id: int, max_bytes: int) -> StagedUpload:
        storage_key = f"{investigation_id}/{uuid.uuid4().hex}"
        final_path = self.resolve(storage_key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path = final_path.with_name(final_path.name + ".part")
        digest, size = hashlib.sha256(), 0
        try:
            with staging_path.open("wb") as out:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise OverflowError("File exceeds the maximum upload size.")
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            staging_path.unlink(missing_ok=True)
            raise
        if size == 0:
            staging_path.unlink(missing_ok=True)
            raise ValueError("Uploaded file is empty.")
        return StagedUpload(storage_key, str(staging_path), digest.hexdigest(), size)

    def finalize(self, upload: StagedUpload) -> None:
        os.replace(Path(upload.staging_ref), self.resolve(upload.storage_key))

    def discard(self, upload: StagedUpload) -> None:
        Path(upload.staging_ref).unlink(missing_ok=True)

    @contextmanager
    def open(self, storage_key: str) -> Iterator[BinaryIO]:
        with self.resolve(storage_key).open("rb") as handle:
            yield handle

    def sha256(self, storage_key: str) -> str:
        return _hash_stream(self.open(storage_key))


class _StoredReader:
    """Normalize provider read errors without catching exceptions from consumers."""
    def __init__(self, body):
        self.body = body

    def read(self, size=-1):
        try:
            return self.body.read(size)
        except Exception as exc:
            raise OSError("Stored evidence stream is unavailable.") from exc


class S3EvidenceStorage:
    """Private S3 storage using the AWS default credential provider chain."""

    def __init__(self, bucket: str, region: str, client=None):
        if not bucket or not region:
            raise ValueError("S3 evidence storage requires a bucket and AWS region.")
        self.bucket = bucket
        if client is None:
            import boto3
            client = boto3.client("s3", region_name=region)
        self.client = client

    def stage(self, stream: BinaryIO, investigation_id: int, max_bytes: int) -> StagedUpload:
        storage_key = validate_storage_key(f"{investigation_id}/{uuid.uuid4().hex}")
        # The deterministic staging key makes interrupted promotion
        # reconcilable without storing provider-specific state in PostgreSQL.
        staging_key = staging_key_for(storage_key)
        digest, size, upload_id = hashlib.sha256(), 0, None
        parts: list[dict[str, object]] = []
        try:
            upload_id = self.client.create_multipart_upload(
                Bucket=self.bucket, Key=staging_key
            )["UploadId"]
            while chunk := stream.read(S3_PART_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise OverflowError("File exceeds the maximum upload size.")
                digest.update(chunk)
                number = len(parts) + 1
                response = self.client.upload_part(
                    Bucket=self.bucket, Key=staging_key, UploadId=upload_id,
                    PartNumber=number, Body=chunk,
                )
                parts.append({"PartNumber": number, "ETag": response["ETag"]})
            if size == 0:
                raise ValueError("Uploaded file is empty.")
            self.client.complete_multipart_upload(
                Bucket=self.bucket, Key=staging_key, UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            upload_id = None
            return StagedUpload(storage_key, staging_key, digest.hexdigest(), size)
        except Exception:
            try:
                if upload_id:
                    self.client.abort_multipart_upload(
                        Bucket=self.bucket, Key=staging_key, UploadId=upload_id
                    )
                else:
                    self.client.delete_object(Bucket=self.bucket, Key=staging_key)
            except Exception:
                pass
            raise

    def finalize(self, upload: StagedUpload) -> None:
        validate_storage_key(upload.storage_key)
        self.client.copy_object(
            Bucket=self.bucket, Key=upload.storage_key,
            CopySource={"Bucket": self.bucket, "Key": upload.staging_ref},
        )
        promoted = self.client.head_object(Bucket=self.bucket, Key=upload.storage_key)
        if promoted.get("ContentLength") != upload.size:
            raise OSError("Promoted evidence object size does not match the upload.")
        try:
            self.client.delete_object(Bucket=self.bucket, Key=upload.staging_ref)
        except Exception:
            # The final object exists. Retaining a staging duplicate is safer
            # than reporting registration failure after successful promotion.
            pass

    def discard(self, upload: StagedUpload) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=upload.staging_ref)
        except Exception:
            pass

    @contextmanager
    def open(self, storage_key: str) -> Iterator[BinaryIO]:
        validate_storage_key(storage_key)
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=storage_key)["Body"]
        except Exception as exc:
            raise FileNotFoundError("Stored evidence object is unavailable.") from exc
        try:
            yield _StoredReader(body)
        finally:
            try:
                body.close()
            except Exception:
                pass

    def sha256(self, storage_key: str) -> str:
        return _hash_stream(self.open(storage_key))


def _hash_stream(source) -> str:
    digest = hashlib.sha256()
    with source as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache
def _configured_storage(backend: str, root: str, bucket: str, region: str) -> EvidenceStorage:
    if backend == "s3":
        return S3EvidenceStorage(bucket, region)
    return LocalEvidenceStorage(root)


def get_storage() -> EvidenceStorage:
    return _configured_storage(
        settings.evidence_storage_backend,
        settings.evidence_storage_root,
        settings.s3_evidence_bucket,
        settings.aws_region,
    )


def storage_root() -> Path:
    backend = get_storage()
    if not isinstance(backend, LocalEvidenceStorage):
        raise RuntimeError("Filesystem paths are unavailable for this storage backend.")
    return backend._root()


def resolve(storage_key: str) -> Path:
    backend = get_storage()
    if not isinstance(backend, LocalEvidenceStorage):
        raise RuntimeError("Filesystem paths are unavailable for this storage backend.")
    return backend.resolve(storage_key)


def sha256_file(path: Path) -> str:
    @contextmanager
    def source():
        with path.open("rb") as handle:
            yield handle
    return _hash_stream(source())


def save_stream(stream: BinaryIO, investigation_id: int, max_bytes: int) -> StagedUpload:
    return get_storage().stage(stream, investigation_id, max_bytes)


def commit_staged(upload: StagedUpload) -> None:
    get_storage().finalize(upload)


def discard_staged(upload: StagedUpload) -> None:
    get_storage().discard(upload)


def open_stored(storage_key: str) -> ContextManager[BinaryIO]:
    return get_storage().open(storage_key)


def recompute_sha256(storage_key: str) -> str:
    return get_storage().sha256(storage_key)


@dataclass
class Snapshot:
    handle: BinaryIO
    sha256: str
    size: int


class SizeMismatch(OSError):
    """Source grew beyond the immutable registered size; full digest unavailable."""


@contextmanager
def snapshot(storage_key: str, max_bytes: int) -> Iterator[Snapshot]:
    """Hash and copy one stream into a private temporary file, then rewind it.

    Callers parse this copy, never reopen the mutable source. A concurrently
    changing source is accepted only if the copied bytes match the baseline.
    Disk and reads are bounded even when the source grows while being copied.
    """
    with tempfile.TemporaryFile(mode="w+b") as target:
        digest, size = hashlib.sha256(), 0
        with open_stored(storage_key) as source:
            while chunk := source.read(min(CHUNK_SIZE, max_bytes - size + 1)):
                size += len(chunk)
                if size > max_bytes:
                    raise SizeMismatch("Stored evidence exceeds its registered size.")
                digest.update(chunk)
                target.write(chunk)
        target.seek(0)
        yield Snapshot(target, digest.hexdigest(), size)


def recover_staged(storage_key: str, digest: str, size: int) -> None:
    backend = get_storage()
    if isinstance(backend, LocalEvidenceStorage):
        ref = str(backend.resolve(storage_key)) + ".part"
    else:
        ref = staging_key_for(storage_key)
    backend.finalize(StagedUpload(storage_key, ref, digest, size))


def replace_for_demo(storage_key: str, data: bytes) -> None:
    if settings.app_env == "production":
        raise RuntimeError("Demo storage mutation is disabled in production.")
    with resolve(storage_key).open("wb") as handle:
        handle.write(data)
