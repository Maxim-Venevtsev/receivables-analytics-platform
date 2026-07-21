from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_VERSION = 1
VALID_STATES = {
    "verified_inbox", "handed_off", "raw_present", "archived", "failed",
    "duplicate_content", "transfer_failed",
}


class ManifestCorruptError(ValueError):
    """Raised when an existing manifest cannot be trusted."""


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any]

    @classmethod
    def empty(cls, path: Path) -> "Manifest":
        return cls(path, {"version": MANIFEST_VERSION, "records": {}, "observations": {}, "failures": {}})

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls.empty(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _validate(data)
        except (OSError, json.JSONDecodeError, ManifestCorruptError, TypeError) as exc:
            raise ManifestCorruptError(f"Invalid Local Sync manifest: {exc}") from exc
        return cls(path, data)

    def record(self, sha256: str, **fields: Any) -> dict[str, Any]:
        now = _utc_now()
        current = self.data["records"].setdefault(
            sha256,
            {"sha256": sha256, "aliases": [], "created_at": now},
        )
        current.update({key: value for key, value in fields.items() if value is not None})
        current["updated_at"] = now
        return current

    def add_alias(self, sha256: str, remote_path: str, filename: str) -> None:
        record = self.record(sha256)
        alias = {"remote_path": remote_path, "filename": filename}
        if alias not in record["aliases"]:
            record["aliases"].append(alias)

    def observe(self, remote_path: str, remote_size: int, remote_mtime: str | None, sha256: str) -> None:
        self.data["observations"][remote_path] = {
            "remote_size": remote_size,
            "remote_mtime": remote_mtime,
            "sha256": sha256,
            "observed_at": _utc_now(),
        }

    def known_observation(self, remote_path: str, size: int, mtime: str | None) -> str | None:
        item = self.data["observations"].get(remote_path)
        if item and item.get("remote_size") == size and item.get("remote_mtime") == mtime:
            return item.get("sha256")
        return None

    def transfer_failed(self, remote_path: str, filename: str, detail: str) -> None:
        self.data["failures"][remote_path] = {
            "filename": filename,
            "state": "transfer_failed",
            "detail": detail[:500],
            "updated_at": _utc_now(),
        }

    def save(self) -> None:
        _validate(self.data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        if self.path.exists():
            shutil.copy2(self.path, backup)
        tmp.replace(self.path)


def preserve_corrupt(path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = path.with_name(f"{path.name}.corrupt-{timestamp}")
    path.replace(target)
    return target


def _validate(data: Any) -> None:
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        raise ManifestCorruptError("unsupported or missing manifest version")
    if not isinstance(data.get("records"), dict) or not isinstance(data.get("observations"), dict):
        raise ManifestCorruptError("records and observations must be objects")
    if not isinstance(data.get("failures", {}), dict):
        raise ManifestCorruptError("failures must be an object")
    data.setdefault("failures", {})
    for sha256, record in data["records"].items():
        if not isinstance(sha256, str) or len(sha256) != 64 or not isinstance(record, dict):
            raise ManifestCorruptError("invalid SHA256 record")
        state = record.get("state")
        if state is not None and state not in VALID_STATES:
            raise ManifestCorruptError(f"invalid state: {state}")
        if not isinstance(record.get("aliases", []), list):
            raise ManifestCorruptError("aliases must be a list")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
