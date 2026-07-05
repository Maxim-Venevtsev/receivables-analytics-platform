from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        manifest_path = Path(path)

        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            data = {
                "version": 1,
                "attachments": {},
                "messages": {},
            }

        data.setdefault("version", 1)
        data.setdefault("attachments", {})
        data.setdefault("messages", {})

        return cls(path=manifest_path, data=data)

    def has_attachment(self, sha256: str) -> bool:
        return sha256 in self.data["attachments"]

    def add_attachment(
        self,
        *,
        sha256: str,
        filename: str,
        saved_path: str,
        message_uid: str,
        sender: str,
    ) -> None:
        self.data["attachments"][sha256] = {
            "filename": filename,
            "saved_path": saved_path,
            "message_uid": message_uid,
            "sender": sender,
            "created_at": _utc_now(),
        }

    def message_processed(self, message_uid: str) -> bool:
        message = self.data["messages"].get(message_uid)
        return bool(message and message.get("status") == "processed")

    def add_message(self, *, message_uid: str, status: str, details: dict) -> None:
        self.data["messages"][message_uid] = {
            "status": status,
            "details": details,
            "updated_at": _utc_now(),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
