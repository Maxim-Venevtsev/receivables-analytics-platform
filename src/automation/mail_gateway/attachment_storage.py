from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .validators import sanitize_filename


@dataclass(frozen=True)
class StoredAttachment:
    original_filename: str
    saved_filename: str
    saved_path: Path
    sha256: str
    size_bytes: int


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    for index in range(1, 10_000):
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not allocate a unique filename for {filename}")


def store_attachment(
    *,
    inbox_dir: Path,
    original_filename: str,
    content: bytes,
) -> StoredAttachment:
    inbox_dir.mkdir(parents=True, exist_ok=True)

    saved_filename = sanitize_filename(original_filename)
    saved_path = unique_path(inbox_dir, saved_filename)

    inbox_root = inbox_dir.resolve()
    target_path = saved_path.resolve()
    if inbox_root != target_path.parent and inbox_root not in target_path.parents:
        raise RuntimeError("Attachment path escaped the configured inbox directory")

    saved_path.write_bytes(content)

    return StoredAttachment(
        original_filename=original_filename,
        saved_filename=saved_path.name,
        saved_path=saved_path,
        sha256=compute_sha256(content),
        size_bytes=len(content),
    )
