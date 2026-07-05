from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class OrchestratorConfigError(ValueError):
    """Raised when orchestrator configuration is incomplete or invalid."""


@dataclass(frozen=True)
class OrchestratorConfig:
    mail_inbox_dir: Path
    raw_dir: Path
    log_path: Path

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "OrchestratorConfig":
        load_dotenv(env_path or PROJECT_ROOT / ".env")

        mail_inbox_dir = _required_path("MAIL_INBOX_DIR")
        log_path = _required_path("AUTOMATION_LOG_PATH")

        raw_dir_value = os.getenv("AUTOMATION_RAW_DIR") or os.getenv("RAW_DIR")
        if raw_dir_value:
            raw_dir = _resolve_project_path(raw_dir_value)
        else:
            raw_dir = PROJECT_ROOT / "data" / "raw"

        return cls(
            mail_inbox_dir=mail_inbox_dir,
            raw_dir=raw_dir,
            log_path=log_path,
        )


def _required_path(name: str) -> Path:
    value = os.getenv(name)
    if not value:
        raise OrchestratorConfigError(f"Missing environment variable: {name}")
    return _resolve_project_path(value)


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
