"""Local evidence storage behind a small replaceable abstraction.

Files live under a configured root as ``<investigation_id>/<uuid>``. The
original filename is never used for storage, so path traversal and
collisions are impossible by construction. Only this module touches the
evidence directory; routers and services use the functions below.
"""

import hashlib
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings

CHUNK_SIZE = 65536


def storage_root() -> Path:
    root = Path(settings.evidence_storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve(storage_key: str) -> Path:
    """Resolve a storage key to a path, confined to the storage root."""
    root = storage_root().resolve()
    candidate = (root / Path(*storage_key.split("/"))).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Storage key escapes the storage root.")
    return candidate


def sha256_file(path: Path) -> str:
    """Chunked SHA-256 so large files never load fully into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def save_stream(
    stream: BinaryIO, investigation_id: int, max_bytes: int
) -> tuple[str, Path, str, int]:
    """Stream an upload to a staging file while hashing.

    Returns (storage_key, staging_path, sha256, size). Raises ValueError on
    empty input and OverflowError when the size limit is exceeded. The caller
    commits the staging file with ``commit_staged`` after the database
    transaction succeeds.
    """
    storage_key = f"{investigation_id}/{uuid.uuid4().hex}"
    final_path = resolve(storage_key)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = final_path.with_name(final_path.name + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with open(staging_path, "wb") as out:
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise OverflowError("File exceeds the maximum upload size.")
                digest.update(chunk)
                out.write(chunk)
    except Exception:
        if staging_path.exists():
            staging_path.unlink()
        raise
    if size == 0:
        staging_path.unlink()
        raise ValueError("Uploaded file is empty.")
    return storage_key, staging_path, digest.hexdigest(), size


def commit_staged(staging_path: Path) -> Path:
    """Atomically promote a staged upload to its final location."""
    final_path = staging_path.with_name(staging_path.name.removesuffix(".part"))
    os.replace(staging_path, final_path)
    return final_path


def discard_staged(staging_path: Path) -> None:
    staging_path.unlink(missing_ok=True)


def open_stored(storage_key: str) -> BinaryIO:
    return open(resolve(storage_key), "rb")


def replace_for_demo(storage_key: str, data: bytes) -> None:
    """Replace stored bytes only for deterministic non-production integrity demos."""
    if settings.app_env == "production":
        raise RuntimeError("Demo storage mutation is disabled in production.")
    path = resolve(storage_key)
    with open(path, "wb") as handle:
        handle.write(data)
