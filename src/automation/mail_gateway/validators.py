from __future__ import annotations

import re
import unicodedata
from pathlib import Path


class ValidationError(ValueError):
    """Raised when a message or attachment fails gateway validation."""


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def validate_sender(sender_email: str, allowed_senders: set[str]) -> None:
    if sender_email.lower() not in {sender.lower() for sender in allowed_senders}:
        raise ValidationError(f"Sender is not allowed: {sender_email}")


def is_allowed_extension(filename: str, allowed_extensions: set[str]) -> bool:
    return Path(filename).suffix.lower() in {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in allowed_extensions
    }


def validate_extension(filename: str, allowed_extensions: set[str]) -> None:
    if not is_allowed_extension(filename, allowed_extensions):
        raise ValidationError(f"Attachment extension is not allowed: {filename}")


def sanitize_filename(filename: str, fallback: str = "attachment") -> str:
    name = Path(filename or "").name
    name = unicodedata.normalize("NFKC", name)
    name = _UNSAFE_CHARS.sub("_", name)
    name = _WHITESPACE.sub(" ", name).strip(" .")

    if not name:
        name = fallback

    stem = Path(name).stem
    suffix = Path(name).suffix

    if stem.upper() in _RESERVED_NAMES:
        stem = f"{stem}_file"

    name = f"{stem}{suffix}"

    if len(name) > 180:
        max_stem_len = max(1, 180 - len(suffix))
        name = f"{stem[:max_stem_len]}{suffix}"

    return name

