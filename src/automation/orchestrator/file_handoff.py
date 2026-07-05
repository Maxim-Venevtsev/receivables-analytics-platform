from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


ALLOWED_HANDOFF_EXTENSIONS = {".txt", ".xls", ".xlsx"}
IGNORED_SUFFIXES = {".log", ".json", ".jsonl", ".tmp", ".part", ".lock"}


@dataclass(frozen=True)
class HandoffResult:
    source_path: Path
    destination_path: Path
    sha256: str
    size_bytes: int
    dry_run: bool = False
    handed_off: bool = False


def list_inbox_files(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        return []
    return sorted(path for path in inbox_dir.iterdir() if path.is_file())


def list_eligible_inbox_files(inbox_dir: Path) -> list[Path]:
    return [path for path in list_inbox_files(inbox_dir) if is_eligible_inbox_file(path)]


def is_eligible_inbox_file(path: Path) -> bool:
    if not path.is_file():
        return False

    suffix = path.suffix.lower()
    if suffix in IGNORED_SUFFIXES:
        return False

    return suffix in ALLOWED_HANDOFF_EXTENSIONS


def handoff_file(source_path: Path, raw_dir: Path, *, dry_run: bool = False) -> HandoffResult:
    source_path = source_path.resolve()
    raw_dir = raw_dir.resolve()

    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Handoff source file not found: {source_path}")

    source_sha256 = compute_sha256(source_path)
    size_bytes = source_path.stat().st_size
    destination_path = unique_destination(raw_dir, source_path.name)

    if dry_run:
        return HandoffResult(
            source_path=source_path,
            destination_path=destination_path,
            sha256=source_sha256,
            size_bytes=size_bytes,
            dry_run=True,
            handed_off=False,
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)

    destination_sha256 = compute_sha256(destination_path)
    if destination_sha256 != source_sha256:
        destination_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Handoff hash mismatch for {source_path.name}: source and destination differ"
        )

    source_path.unlink()

    return HandoffResult(
        source_path=source_path,
        destination_path=destination_path,
        sha256=source_sha256,
        size_bytes=size_bytes,
        handed_off=True,
    )


def handoff_files(
    files: list[Path],
    raw_dir: Path,
    *,
    dry_run: bool = False,
) -> list[HandoffResult]:
    return [handoff_file(path, raw_dir, dry_run=dry_run) for path in files]


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_destination(directory: Path, filename: str) -> Path:
    original = directory / Path(filename).name
    candidate = original
    if not candidate.exists():
        return candidate

    for index in range(1, 10_000):
        candidate = directory / f"{original.stem}_{index}{original.suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not allocate unique destination for {filename}")
