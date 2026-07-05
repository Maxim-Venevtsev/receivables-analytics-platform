from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when mail gateway configuration is incomplete or invalid."""


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []

    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _split_extensions(value: str | None) -> set[str]:
    extensions = set()

    for item in _split_list(value):
        ext = item.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        extensions.add(ext)

    return extensions


@dataclass(frozen=True)
class MailGatewayConfig:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    source_folder: str
    processed_folder: str
    failed_folder: str
    allowed_senders: set[str]
    allowed_extensions: set[str]
    inbox_dir: Path
    manifest_path: Path
    log_path: Path

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "MailGatewayConfig":
        if env_path is not None:
            load_dotenv(env_path)
        else:
            load_dotenv()

        missing = [
            name
            for name in [
                "YAHOO_IMAP_HOST",
                "YAHOO_IMAP_PORT",
                "YAHOO_IMAP_USER",
                "YAHOO_IMAP_PASSWORD",
                "MAIL_SOURCE_FOLDER",
                "MAIL_PROCESSED_FOLDER",
                "MAIL_FAILED_FOLDER",
                "MAIL_ALLOWED_SENDERS",
                "MAIL_ALLOWED_EXTENSIONS",
                "MAIL_INBOX_DIR",
                "MAIL_MANIFEST_PATH",
                "MAIL_LOG_PATH",
            ]
            if not os.getenv(name)
        ]

        if missing:
            raise ConfigError(
                "Missing mail gateway environment variables: "
                + ", ".join(missing)
            )

        try:
            imap_port = int(os.environ["YAHOO_IMAP_PORT"])
        except ValueError as exc:
            raise ConfigError("YAHOO_IMAP_PORT must be an integer") from exc

        allowed_senders = {
            sender.lower()
            for sender in _split_list(os.environ["MAIL_ALLOWED_SENDERS"])
        }
        allowed_extensions = _split_extensions(os.environ["MAIL_ALLOWED_EXTENSIONS"])

        if not allowed_senders:
            raise ConfigError("MAIL_ALLOWED_SENDERS must contain at least one sender")

        if not allowed_extensions:
            raise ConfigError(
                "MAIL_ALLOWED_EXTENSIONS must contain at least one extension"
            )

        return cls(
            imap_host=os.environ["YAHOO_IMAP_HOST"],
            imap_port=imap_port,
            imap_user=os.environ["YAHOO_IMAP_USER"],
            imap_password=os.environ["YAHOO_IMAP_PASSWORD"],
            source_folder=os.environ["MAIL_SOURCE_FOLDER"],
            processed_folder=os.environ["MAIL_PROCESSED_FOLDER"],
            failed_folder=os.environ["MAIL_FAILED_FOLDER"],
            allowed_senders=allowed_senders,
            allowed_extensions=allowed_extensions,
            inbox_dir=Path(os.environ["MAIL_INBOX_DIR"]),
            manifest_path=Path(os.environ["MAIL_MANIFEST_PATH"]),
            log_path=Path(os.environ["MAIL_LOG_PATH"]),
        )

