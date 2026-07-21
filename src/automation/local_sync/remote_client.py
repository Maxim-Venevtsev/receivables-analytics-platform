from __future__ import annotations

import posixpath
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .config import LocalSyncConfig


class RemoteClientError(RuntimeError):
    """Raised for a failed or unsafe read-only SFTP operation."""


@dataclass(frozen=True)
class RemoteFile:
    remote_path: str
    filename: str
    size_bytes: int
    modified_at: str | None = None


class OpenSftpRemoteClient:
    """Narrow read-only adapter around the native OpenSSH sftp client."""

    def __init__(self, config: LocalSyncConfig, executable: str = "sftp"):
        self.config = config
        self.executable = executable

    def list_files(self) -> list[RemoteFile]:
        output = self._run_batch(f'ls -l "{_quote(self.config.remote_archive_dir)}"')
        files: list[RemoteFile] = []
        for line in output.splitlines():
            if not line.startswith("-"):
                continue
            parts = line.split(maxsplit=8)
            if len(parts) != 9:
                raise RemoteClientError("Could not safely parse SFTP directory listing")
            try:
                size = int(parts[4])
            except ValueError as exc:
                raise RemoteClientError("Invalid size in SFTP directory listing") from exc
            filename = parts[8]
            _validate_filename(filename)
            if PurePosixPath(filename).suffix.lower() not in self.config.allowed_extensions:
                continue
            remote_path = posixpath.join(self.config.remote_archive_dir, filename)
            files.append(
                RemoteFile(remote_path, filename, size, _parse_sftp_mtime(parts[5:8]))
            )
        return sorted(files, key=lambda item: item.remote_path)

    def stat_file(self, remote_path: str) -> RemoteFile:
        _validate_remote_child(remote_path, self.config.remote_archive_dir)
        output = self._run_batch(f'ls -ld "{_quote(remote_path)}"')
        entries = [line for line in output.splitlines() if line.startswith("-")]
        if len(entries) != 1:
            raise RemoteClientError("Could not safely parse SFTP file metadata")
        parts = entries[0].split(maxsplit=8)
        if len(parts) != 9:
            raise RemoteClientError("Could not safely parse SFTP file metadata")
        filename = PurePosixPath(remote_path).name
        return RemoteFile(remote_path, filename, int(parts[4]), _parse_sftp_mtime(parts[5:8]))

    def download_file(self, remote: RemoteFile, destination: Path) -> None:
        _validate_remote_child(remote.remote_path, self.config.remote_archive_dir)
        command = f'get "{_quote(remote.remote_path)}" "{_quote(str(destination))}"'
        self._run_batch(command)

    def _run_batch(self, command: str) -> str:
        args = [
            self.executable,
            "-b", "-",
            "-P", str(self.config.ssh_port),
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={self.config.connect_timeout_seconds}",
        ]
        if self.config.ssh_identity_file is not None:
            args.extend(["-i", str(self.config.ssh_identity_file)])
        args.append(f"{self.config.ssh_user}@{self.config.ssh_host}")
        try:
            completed = subprocess.run(
                args,
                input=command + "\n",
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
        except OSError as exc:
            raise RemoteClientError(f"Could not start native SFTP client: {exc}") from exc
        if completed.returncode != 0:
            detail = _redact(completed.stderr.strip(), self.config)
            raise RemoteClientError(f"SFTP read operation failed: {detail or 'unknown error'}")
        return completed.stdout


def _validate_filename(filename: str) -> None:
    if not filename or filename in {".", ".."} or PurePosixPath(filename).name != filename:
        raise RemoteClientError("Unsafe filename returned by SFTP server")
    if any(char in filename for char in "\x00\r\n"):
        raise RemoteClientError("Control character in remote filename")


def _validate_remote_child(remote_path: str, archive_dir: str) -> None:
    normalized = posixpath.normpath(remote_path)
    parent = posixpath.normpath(archive_dir)
    if posixpath.dirname(normalized) != parent or normalized in {parent, "/"}:
        raise RemoteClientError("Remote path is outside the configured archive directory")


def _quote(value: str) -> str:
    if any(char in value for char in "\x00\r\n"):
        raise RemoteClientError("Control character in SFTP path")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_sftp_mtime(parts: list[str]) -> str | None:
    if len(parts) != 3:
        return None
    month, day, year_or_time = parts
    year = datetime.now(timezone.utc).year
    formats = [(f"{month} {day} {year_or_time}", "%b %d %Y")]
    if ":" in year_or_time:
        formats.insert(0, (f"{month} {day} {year} {year_or_time}", "%b %d %Y %H:%M"))
    for value, fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return None


def _redact(value: str, config: LocalSyncConfig) -> str:
    redacted = value
    for secret in (config.ssh_user, config.ssh_host, str(config.ssh_identity_file or "")):
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted[:1000]

