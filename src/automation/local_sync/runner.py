from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import LocalSyncConfig, PROJECT_ROOT
from .file_transfer import (
    compute_sha256,
    download_and_verify,
    eligible_txt_files,
    handoff_verified,
)
from .manifest import Manifest, ManifestCorruptError, preserve_corrupt
from .remote_client import OpenSftpRemoteClient, RemoteFile


class LocalSyncLockedError(RuntimeError):
    """Raised when another Local Sync process owns the lock."""


@dataclass
class FileDetail:
    remote_filename: str
    remote_size: int
    remote_mtime: str | None
    sha256: str | None = None
    verified_filename: str | None = None
    handoff_filename: str | None = None
    action: str = ""
    result: str = ""


@dataclass
class LocalSyncResult:
    dry_run: bool = False
    remote_files_seen: int = 0
    eligible_remote_files: int = 0
    known_content_files: int = 0
    missing_candidates: int = 0
    files_selected: int = 0
    files_downloaded: int = 0
    files_verified: int = 0
    duplicate_content_files: int = 0
    files_handed_off: int = 0
    raw_files_detected: int = 0
    ingestion_executed: bool = False
    ingestion_skipped: bool = False
    ingestion_skip_reason: str | None = None
    ingestion_exit_code: int | None = None
    success: bool = True
    failures: list[str] = field(default_factory=list)
    details: list[FileDetail] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.success else 1


def run_local_sync(
    config: LocalSyncConfig,
    *,
    remote_client=None,
    dry_run: bool = False,
    skip_ingestion: bool = False,
    limit: int | None = None,
    order: str = "oldest",
) -> LocalSyncResult:
    if limit is not None and limit <= 0:
        raise ValueError("--limit must be greater than zero")
    if order not in {"oldest", "newest"}:
        raise ValueError("order must be oldest or newest")

    result = LocalSyncResult(dry_run=dry_run)
    logger = JsonlLogger(config.log_path, enabled=not dry_run)
    client = remote_client or OpenSftpRemoteClient(config)
    lock_context = _no_lock() if dry_run else process_lock(config.manifest_path.with_suffix(".lock"))

    with lock_context:
        manifest = _load_and_reconcile(config, dry_run=dry_run, logger=logger)
        result.known_content_files = len(manifest.data["records"])
        logger.write("configuration", result="valid", ssh_port=config.ssh_port)

        remote_files = client.list_files()
        result.remote_files_seen = len(remote_files)
        eligible = [item for item in remote_files if Path(item.filename).suffix.lower() == ".txt"]
        result.eligible_remote_files = len(eligible)
        logger.write("remote_inventory", result="success", files=len(eligible))

        candidates: list[RemoteFile] = []
        for remote in eligible:
            known_hash = manifest.known_observation(
                remote.remote_path, remote.size_bytes, remote.modified_at
            )
            if known_hash and known_hash in manifest.data["records"]:
                result.details.append(_detail(remote, known_hash, "skip", "known_content"))
            else:
                candidates.append(remote)
        result.missing_candidates = len(candidates)
        candidates.sort(key=_remote_order_key, reverse=order == "newest")
        selected = candidates[:limit] if limit is not None else candidates
        result.files_selected = len(selected)
        logger.write("candidate_selection", missing=len(candidates), selected=len(selected), order=order)

        if dry_run:
            for remote in selected:
                result.details.append(_detail(remote, None, "download", "dry_run"))
        else:
            for remote in selected:
                detail = _detail(remote, None, "download", "started")
                result.details.append(detail)
                logger.write("transfer_start", filename=remote.filename, size_bytes=remote.size_bytes)
                try:
                    current = client.stat_file(remote.remote_path)
                    if current.filename != remote.filename:
                        raise RuntimeError("Remote filename changed between inventory and transfer")
                    remote = current
                    detail.remote_size = remote.size_bytes
                    detail.remote_mtime = remote.modified_at
                    verified = download_and_verify(client, remote, config.inbox_dir)
                    result.files_downloaded += 1
                    result.files_verified += 1
                    detail.sha256 = verified.sha256
                    detail.verified_filename = verified.path.name
                    existing = manifest.data["records"].get(verified.sha256)
                    if existing and existing.get("state") == "verified_inbox":
                        canonical_path = existing.get("local_path")
                        manifest.add_alias(verified.sha256, remote.remote_path, remote.filename)
                        manifest.observe(remote.remote_path, remote.size_bytes, remote.modified_at, verified.sha256)
                        if canonical_path and str(verified.path) != canonical_path:
                            verified.path.unlink(missing_ok=True)
                        result.duplicate_content_files += 1
                        detail.verified_filename = existing.get("verified_local_filename")
                        detail.action = "skip"
                        detail.result = "duplicate_verified_inbox"
                        logger.write(
                            "hash_verification",
                            filename=remote.filename,
                            result="duplicate_verified_inbox",
                            sha256=verified.sha256,
                        )
                        continue
                    if existing and existing.get("state") in {"archived", "raw_present", "failed", "handed_off"}:
                        manifest.add_alias(verified.sha256, remote.remote_path, remote.filename)
                        manifest.observe(remote.remote_path, remote.size_bytes, remote.modified_at, verified.sha256)
                        existing_path = existing.get("local_path")
                        if str(verified.path) != existing_path:
                            verified.path.unlink(missing_ok=True)
                        result.duplicate_content_files += 1
                        detail.action = "skip"
                        detail.result = "duplicate_content"
                        logger.write("hash_verification", filename=remote.filename, result="duplicate", sha256=verified.sha256)
                        continue
                    manifest.record(
                        verified.sha256,
                        original_remote_path=remote.remote_path,
                        remote_filename=remote.filename,
                        remote_size=remote.size_bytes,
                        remote_mtime=remote.modified_at,
                        verified_local_filename=verified.path.name,
                        local_path=str(verified.path),
                        state="verified_inbox",
                    )
                    manifest.add_alias(verified.sha256, remote.remote_path, remote.filename)
                    manifest.observe(remote.remote_path, remote.size_bytes, remote.modified_at, verified.sha256)
                    detail.result = "verified"
                    logger.write("hash_verification", filename=remote.filename, result="verified", sha256=verified.sha256)
                except Exception as exc:
                    message = _safe_error(exc, config)
                    manifest.transfer_failed(remote.remote_path, remote.filename, message)
                    detail.result = "failed"
                    result.failures.append(f"{remote.filename}: {message}")
                    result.success = False
                    logger.write("transfer_result", filename=remote.filename, result="failed", detail=message)

            _handoff_verified_inbox(config, manifest, result, logger)
            manifest.save()

        raw_files = eligible_txt_files(config.raw_dir)
        result.raw_files_detected = len(raw_files)
        if skip_ingestion:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "--skip-ingestion"
        elif dry_run:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "dry_run"
        elif not raw_files:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "empty raw"
        else:
            completed = run_ingestion_command(config)
            result.ingestion_executed = True
            result.ingestion_exit_code = completed.returncode
            ingestion_fields = {
                "result": "success" if completed.returncode == 0 else "failed",
                "exit_code": completed.returncode,
            }
            if completed.returncode != 0:
                stdout_tail = _redacted_tail(completed.stdout, config)
                stderr_tail = _redacted_tail(completed.stderr, config)
                ingestion_fields.update(stdout_tail=stdout_tail, stderr_tail=stderr_tail)
                result.success = False
                diagnostic = stderr_tail or stdout_tail or "no subprocess output"
                result.failures.append(
                    f"Ingestion failed with exit code {completed.returncode}: {diagnostic}"
                )
            logger.write("ingestion", **ingestion_fields)
            _reconcile_manifest(manifest, config, logger)
            manifest.save()

        logger.write("summary", result="success" if result.success else "failed", downloaded=result.files_downloaded, handed_off=result.files_handed_off, failures=len(result.failures))
    return result


def _load_and_reconcile(config: LocalSyncConfig, *, dry_run: bool, logger: "JsonlLogger") -> Manifest:
    try:
        manifest = Manifest.load(config.manifest_path)
    except ManifestCorruptError:
        if not dry_run:
            preserve_corrupt(config.manifest_path)
        manifest = Manifest.empty(config.manifest_path)

    _reconcile_manifest(manifest, config, logger)
    return manifest


def _reconcile_manifest(manifest: Manifest, config: LocalSyncConfig, logger: "JsonlLogger") -> None:
    locations = [
        (config.inbox_dir, "verified_inbox"),
        (config.failed_dir, "failed"),
        (config.raw_dir, "raw_present"),
        (config.archive_dir, "archived"),
    ]
    # Later, more authoritative ingestion states override staging state.
    for directory, state in locations:
        for path in eligible_txt_files(directory):
            sha256 = compute_sha256(path)
            manifest.record(
                sha256,
                verified_local_filename=path.name if state == "verified_inbox" else None,
                handoff_filename=path.name if state != "verified_inbox" else None,
                local_path=str(path),
                state=state,
            )
    logger.write("bootstrap_reconciliation", records=len(manifest.data["records"]))


def _handoff_verified_inbox(config: LocalSyncConfig, manifest: Manifest, result: LocalSyncResult, logger: "JsonlLogger") -> None:
    for source in eligible_txt_files(config.inbox_dir):
        sha256 = compute_sha256(source)
        record = manifest.data["records"].get(sha256)
        if not record or record.get("state") != "verified_inbox":
            continue
        same_name_other_hash = any(
            other_hash != sha256 and (
                other.get("handoff_filename") == source.name
                or other.get("verified_local_filename") == source.name
            )
            for other_hash, other in manifest.data["records"].items()
        )
        try:
            handoff = handoff_verified(source, config.raw_dir, sha256, force_hash_suffix=same_name_other_hash)
            manifest.record(
                sha256,
                handoff_filename=handoff.destination_path.name,
                local_path=str(handoff.destination_path),
                state="raw_present",
            )
            result.files_handed_off += 1
            for detail in result.details:
                if detail.sha256 == sha256:
                    detail.handoff_filename = handoff.destination_path.name
                    detail.action = "handoff"
                    detail.result = "handed_off"
            logger.write("handoff", filename=handoff.destination_path.name, result="success", sha256=sha256)
        except Exception as exc:
            message = _safe_error(exc, config)
            result.success = False
            result.failures.append(f"{source.name}: handoff failed: {message}")
            logger.write("handoff", filename=source.name, result="failed", detail=message)


def run_ingestion_command(config: LocalSyncConfig) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["RAW_DIR"] = str(config.raw_dir)
    env["ARCHIVE_DIR"] = str(config.archive_dir)
    env["FAILED_DIR"] = str(config.failed_dir)
    return subprocess.run(
        [sys.executable, "-m", "src.ingestion.run_ingestion"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


@contextmanager
def process_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LocalSyncLockedError("Another Local Sync execution is already running") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)


@contextmanager
def _no_lock() -> Iterator[None]:
    yield


class JsonlLogger:
    def __init__(self, path: Path, *, enabled: bool = True):
        self.path = path
        self.enabled = enabled

    def write(self, event: str, **fields) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _remote_order_key(remote: RemoteFile) -> tuple[str, str]:
    return (remote.modified_at or "9999-12-31T23:59:59+00:00", remote.remote_path)


def _detail(remote: RemoteFile, sha256: str | None, action: str, result: str) -> FileDetail:
    return FileDetail(remote.filename, remote.size_bytes, remote.modified_at, sha256=sha256, action=action, result=result)


def _safe_error(exc: Exception, config: LocalSyncConfig) -> str:
    return _redact_text(str(exc), config)[:1000]


def _redacted_tail(value: str | None, config: LocalSyncConfig, limit: int = 2000) -> str:
    return _redact_text(value or "", config)[-limit:]


def _redact_text(message: str, config: LocalSyncConfig) -> str:
    sensitive_values = {
        config.ssh_host,
        config.ssh_user,
        str(config.ssh_identity_file or ""),
    }
    for name, value in os.environ.items():
        upper_name = name.upper()
        if any(marker in upper_name for marker in ("PASSWORD", "TOKEN", "SECRET")):
            sensitive_values.add(value)
    redacted = message
    for value in sensitive_values:
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted
