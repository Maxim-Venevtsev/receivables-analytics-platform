from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.automation.mail_gateway.validators import sanitize_filename

from .remote_client import RemoteFile


@dataclass(frozen=True)
class VerifiedFile:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class HandoffResult:
    source_path: Path
    destination_path: Path
    sha256: str


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_verify(remote_client, remote: RemoteFile, inbox_dir: Path) -> VerifiedFile:
    safe_name = sanitize_filename(remote.filename, fallback="report.txt")
    final = _safe_child(inbox_dir, safe_name)
    part = _safe_child(inbox_dir, f"{safe_name}.part")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    part.unlink(missing_ok=True)
    try:
        remote_client.download_file(remote, part)
        if not part.exists():
            raise RuntimeError("Download completed without creating the .part file")
        size = part.stat().st_size
        if size != remote.size_bytes:
            raise RuntimeError(
                f"Downloaded size mismatch for {remote.filename}: expected {remote.size_bytes}, got {size}"
            )
        sha256 = compute_sha256(part)
        if final.exists():
            if compute_sha256(final) == sha256:
                part.unlink()
                return VerifiedFile(final, sha256, size)
            final = _safe_child(inbox_dir, hash_suffix_name(safe_name, sha256))
            if final.exists() and compute_sha256(final) != sha256:
                raise RuntimeError(f"Verified staging collision for {remote.filename}")
        part.replace(final)
        return VerifiedFile(final, sha256, size)
    except Exception:
        # An interrupted or invalid transfer is never exposed as a completed file.
        raise


def handoff_verified(source: Path, raw_dir: Path, sha256: str, *, force_hash_suffix: bool = False) -> HandoffResult:
    if compute_sha256(source) != sha256:
        raise RuntimeError(f"Staging hash changed before handoff: {source.name}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = hash_suffix_name(source.name, sha256) if force_hash_suffix else source.name
    destination = _safe_child(raw_dir, name)
    if destination.exists():
        if compute_sha256(destination) == sha256:
            source.unlink()
            return HandoffResult(source, destination, sha256)
        destination = _safe_child(raw_dir, hash_suffix_name(source.name, sha256))
        if destination.exists():
            if compute_sha256(destination) == sha256:
                source.unlink()
                return HandoffResult(source, destination, sha256)
            raise RuntimeError(f"RAW collision for {source.name}")
    temporary = _safe_child(raw_dir, f"{destination.name}.part")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copy2(source, temporary)
        if compute_sha256(temporary) != sha256:
            raise RuntimeError(f"Handoff hash mismatch for {source.name}")
        temporary.replace(destination)
        source.unlink()
        return HandoffResult(source, destination, sha256)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def hash_suffix_name(filename: str, sha256: str) -> str:
    path = Path(filename)
    return f"{path.stem}__{sha256[:12]}{path.suffix.lower()}"


def eligible_txt_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt" and not path.name.lower().endswith(".part")
    )


def _safe_child(directory: Path, filename: str) -> Path:
    if Path(filename).name != filename:
        raise ValueError("Filename must not contain a path")
    root = directory.resolve()
    target = (directory / filename).resolve()
    if target.parent != root:
        raise ValueError("Target path escapes the configured directory")
    return target
