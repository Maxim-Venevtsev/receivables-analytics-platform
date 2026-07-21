from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class LocalSyncConfigError(ValueError):
    """Raised when Local Sync configuration is missing or unsafe."""


@dataclass(frozen=True)
class LocalSyncConfig:
    ssh_host: str
    ssh_port: int
    ssh_user: str
    ssh_identity_file: Path | None
    remote_archive_dir: str
    inbox_dir: Path
    manifest_path: Path
    log_path: Path
    raw_dir: Path
    archive_dir: Path
    failed_dir: Path
    allowed_extensions: frozenset[str]
    connect_timeout_seconds: int

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "LocalSyncConfig":
        load_dotenv(env_path or PROJECT_ROOT / ".env", override=env_path is not None)
        host = _required("LOCAL_SYNC_SSH_HOST")
        user = _required("LOCAL_SYNC_SSH_USER")
        remote_dir = _required("LOCAL_SYNC_REMOTE_ARCHIVE_DIR")
        port = _positive_int("LOCAL_SYNC_SSH_PORT", 22)
        timeout = _positive_int("LOCAL_SYNC_CONNECT_TIMEOUT_SECONDS", 30)

        identity_value = os.getenv("LOCAL_SYNC_SSH_IDENTITY_FILE", "").strip()
        identity = _local_path(identity_value) if identity_value else None
        raw_dir = _local_path(os.getenv("LOCAL_SYNC_RAW_DIR", "data/raw_work"))
        effective_raw = _local_path(os.getenv("RAW_DIR", "data/raw"))
        if raw_dir.resolve() != effective_raw.resolve():
            raise LocalSyncConfigError(
                "LOCAL_SYNC_RAW_DIR must resolve to the same directory as RAW_DIR"
            )

        extensions = frozenset(
            ext if ext.startswith(".") else f".{ext}"
            for ext in (
                item.strip().lower()
                for item in os.getenv("LOCAL_SYNC_ALLOWED_EXTENSIONS", ".txt").split(",")
            )
            if ext
        )
        if extensions != frozenset({".txt"}):
            raise LocalSyncConfigError("LOCAL_SYNC_ALLOWED_EXTENSIONS must be exactly .txt")

        return cls(
            ssh_host=host,
            ssh_port=port,
            ssh_user=user,
            ssh_identity_file=identity,
            remote_archive_dir=remote_dir.rstrip("/"),
            inbox_dir=_local_path(os.getenv("LOCAL_SYNC_INBOX_DIR", "data/local_sync_inbox")),
            manifest_path=_local_path(os.getenv("LOCAL_SYNC_MANIFEST_PATH", "data/local_sync_manifest.json")),
            log_path=_local_path(os.getenv("LOCAL_SYNC_LOG_PATH", "data/local_sync_logs/local_sync.jsonl")),
            raw_dir=raw_dir,
            archive_dir=_local_path(os.getenv("LOCAL_SYNC_ARCHIVE_DIR", "data/archive_work")),
            failed_dir=_local_path(os.getenv("LOCAL_SYNC_FAILED_DIR", "data/failed_work")),
            allowed_extensions=extensions,
            connect_timeout_seconds=timeout,
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise LocalSyncConfigError(f"Missing environment variable: {name}")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise LocalSyncConfigError(f"Invalid control character in {name}")
    return value


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise LocalSyncConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise LocalSyncConfigError(f"{name} must be greater than zero")
    return value


def _local_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path

