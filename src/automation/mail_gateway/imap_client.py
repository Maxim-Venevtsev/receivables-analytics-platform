from __future__ import annotations

import imaplib
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import re


class MailGatewayError(RuntimeError):
    """Raised for actionable IMAP gateway errors."""


class MoveVerificationError(MailGatewayError):
    """Raised when a copied message remains visible in the source folder."""


@dataclass(frozen=True)
class MoveResult:
    copied: bool
    source_deleted: bool
    source_verified_absent: bool
    source_retained: bool = False


@dataclass
class ImapClient:
    host: str
    port: int
    user: str
    password: str
    connection: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "ImapClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        try:
            self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        except OSError as exc:
            raise MailGatewayError(
                "Could not connect to IMAP server; verify host and port."
            ) from exc

        try:
            status, _ = self.connection.login(self.user, self.password)
        except imaplib.IMAP4.error as exc:
            raise MailGatewayError(
                "IMAP login failed; verify mailbox user, app password, and Yahoo IMAP settings."
            ) from exc

        if status != "OK":
            raise MailGatewayError(
                "IMAP login failed; verify mailbox user, app password, and Yahoo IMAP settings."
            )

    def close(self) -> None:
        if self.connection is None:
            return

        try:
            self.connection.close()
        except imaplib.IMAP4.error:
            pass
        finally:
            self.connection.logout()
            self.connection = None

    def select_folder(self, folder: str) -> None:
        status, data = self._conn.select(_quote_mailbox(folder))
        if status != "OK":
            detail = _decode_response(data)
            raise MailGatewayError(
                f"IMAP folder is missing or cannot be selected: {folder}. "
                f"Create the folder or update the MAIL_*_FOLDER setting. {detail}"
            )

    def assert_folder_exists(self, folder: str) -> None:
        try:
            status, data = self._conn.select(_quote_mailbox(folder), readonly=True)
        except imaplib.IMAP4.error as exc:
            raise MailGatewayError(
                f"IMAP folder is missing or cannot be selected: {folder}. "
                "Create it in Yahoo Mail or update the MAIL_*_FOLDER setting."
            ) from exc

        if status != "OK":
            detail = _decode_response(data)
            raise MailGatewayError(
                f"IMAP folder is missing or cannot be selected: {folder}. "
                f"Create it in Yahoo Mail or update the MAIL_*_FOLDER setting. {detail}"
            )

    def search_candidate_uids(self) -> list[str]:
        status, data = self._conn.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise MailGatewayError("Could not search IMAP messages")

        raw = data[0] or b""
        return [uid.decode("ascii") for uid in raw.split()]

    def uid_exists(self, uid: str) -> bool:
        status, data = self._conn.uid("SEARCH", None, "UID", uid)
        if status != "OK":
            raise MailGatewayError(f"Could not verify IMAP message UID {uid}")

        raw = data[0] or b""
        return uid.encode("ascii") in raw.split()

    def fetch_internal_date(self, uid: str) -> datetime | None:
        status, data = self._conn.uid("FETCH", uid, "(INTERNALDATE)")
        if status != "OK":
            raise MailGatewayError(f"Could not fetch IMAP INTERNALDATE for UID {uid}")

        detail = _decode_response(data)
        match = re.search(r'INTERNALDATE "([^"]+)"', detail)
        if not match:
            return None

        try:
            return parsedate_to_datetime(match.group(1))
        except (TypeError, ValueError):
            return None

    def fetch_message(self, uid: str) -> bytes:
        status, data = self._conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK":
            raise MailGatewayError(f"Could not fetch IMAP message UID {uid}")

        for item in data:
            if isinstance(item, tuple):
                return item[1]

        raise MailGatewayError(f"IMAP message UID {uid} did not include RFC822 data")

    def move_message(
        self,
        uid: str,
        folder: str,
        *,
        source_folder: str,
        keep_source: bool = False,
    ) -> MoveResult:
        status, data = self._conn.uid("COPY", uid, _quote_mailbox(folder))
        if status != "OK":
            detail = _decode_response(data)
            raise MailGatewayError(
                f"Could not copy IMAP message UID {uid} to {folder}. "
                "Source message was not marked deleted. "
                f"{detail}"
            )

        if keep_source:
            return MoveResult(
                copied=True,
                source_deleted=False,
                source_verified_absent=False,
                source_retained=True,
            )

        status, data = self._conn.uid("STORE", uid, "+FLAGS.SILENT", r"(\Deleted)")
        if status != "OK":
            detail = _decode_response(data)
            raise MailGatewayError(
                f"Copied IMAP message UID {uid} to {folder}, but could not mark "
                f"the source message deleted. Check mailbox manually. {detail}"
            )

        status, data = self._conn.expunge()
        if status != "OK":
            detail = _decode_response(data)
            raise MailGatewayError(
                f"Copied IMAP message UID {uid} to {folder} and marked the source "
                f"deleted, but expunge failed. Check mailbox manually. {detail}"
            )

        self.select_folder(source_folder)
        if self.uid_exists(uid):
            raise MoveVerificationError(
                f"Copied IMAP message UID {uid} to {folder}, but the UID is still "
                f"visible in source folder {source_folder} after expunge."
            )

        return MoveResult(
            copied=True,
            source_deleted=True,
            source_verified_absent=True,
        )

    @property
    def _conn(self) -> imaplib.IMAP4_SSL:
        if self.connection is None:
            raise MailGatewayError("IMAP client is not connected")
        return self.connection


def _decode_response(data) -> str:
    if not data:
        return ""

    parts = []
    for item in data:
        if isinstance(item, bytes):
            parts.append(item.decode("utf-8", "replace"))
        else:
            parts.append(str(item))

    return " ".join(parts)


def _quote_mailbox(folder: str) -> str:
    escaped = folder.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
