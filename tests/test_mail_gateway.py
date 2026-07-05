from pathlib import Path
from datetime import datetime, timezone

import pytest

from src.automation.mail_gateway.attachment_storage import compute_sha256, store_attachment
from src.automation.mail_gateway.cli import format_summary
from src.automation.mail_gateway.imap_client import ImapClient, MailGatewayError
from src.automation.mail_gateway.manifest import Manifest
from src.automation.mail_gateway.runner import GatewayResult, run_gateway
from src.automation.mail_gateway.validators import (
    ValidationError,
    is_allowed_extension,
    sanitize_filename,
    validate_sender,
)


def test_allowed_sender_validation():
    validate_sender("reports@example.com", {"reports@example.com"})


def test_disallowed_sender_rejection():
    with pytest.raises(ValidationError):
        validate_sender("intruder@example.com", {"reports@example.com"})


def test_allowed_extension_validation():
    assert is_allowed_extension("report.TXT", {".txt", ".xlsx"})


def test_blocked_extension_rejection():
    assert not is_allowed_extension("payload.exe", {".txt", ".xlsx"})


def test_filename_sanitization():
    assert sanitize_filename("../bad:name?.txt") == "bad_name_.txt"
    assert sanitize_filename("CON.txt") == "CON_file.txt"


def test_sha256_duplicate_detection(tmp_path: Path):
    content = b"same report"
    sha256 = compute_sha256(content)
    manifest = Manifest.load(tmp_path / "manifest.json")

    assert not manifest.has_attachment(sha256)

    manifest.add_attachment(
        sha256=sha256,
        filename="report.txt",
        saved_path=str(tmp_path / "report.txt"),
        message_uid="1",
        sender="reports@example.com",
    )

    assert manifest.has_attachment(sha256)


def test_dry_run_does_not_write_files(tmp_path: Path, monkeypatch):
    inbox_dir = tmp_path / "inbox"

    def fake_store_attachment(**kwargs):
        raise AssertionError("dry-run must not store attachments")

    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.store_attachment",
        fake_store_attachment,
    )
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeImapClient(),
    )

    config = FakeConfig(tmp_path=tmp_path, inbox_dir=inbox_dir)
    result = run_gateway(config, dry_run=True, limit=1)

    assert isinstance(result, GatewayResult)
    assert result.dry_run
    assert result.messages_accepted == 1
    assert result.attachments_found == 1
    assert result.attachments_accepted == 1
    assert result.files_written == 0
    assert result.messages_moved == 0
    assert not inbox_dir.exists()
    assert not config.manifest_path.exists()
    assert FakeImapClient.moves == []


def test_manifest_add_check_behavior(tmp_path: Path):
    path = tmp_path / "manifest.json"
    manifest = Manifest.load(path)
    sha256 = compute_sha256(b"payload")

    manifest.add_attachment(
        sha256=sha256,
        filename="report.txt",
        saved_path=str(tmp_path / "report.txt"),
        message_uid="42",
        sender="reports@example.com",
    )
    manifest.add_message(
        message_uid="42",
        status="processed",
        details={"attachments": 1},
    )
    manifest.save()

    reloaded = Manifest.load(path)

    assert reloaded.has_attachment(sha256)
    assert reloaded.message_processed("42")


def test_folder_validation_uses_readonly_select_not_list():
    connection = FakeImapConnection(select_status="OK")
    client = ImapClient(
        host="imap.mail.yahoo.com",
        port=993,
        user="user@example.com",
        password="not-used",
        connection=connection,
    )

    client.assert_folder_exists("ARS Reports")

    assert connection.selected == [('"ARS Reports"', True)]
    assert not connection.list_called


def test_folder_validation_bad_select_raises_actionable_error():
    connection = FakeImapConnection(select_status="BAD")
    client = ImapClient(
        host="imap.mail.yahoo.com",
        port=993,
        user="user@example.com",
        password="not-used",
        connection=connection,
    )

    with pytest.raises(MailGatewayError, match="ARS Reports"):
        client.assert_folder_exists("ARS Reports")


def test_dry_run_summary_reports_no_writes_or_moves():
    summary = format_summary(
        GatewayResult(
            dry_run=True,
            messages_seen=1,
            messages_accepted=1,
            attachments_found=2,
            attachments_accepted=2,
        )
    )

    assert "Dry-run mode: yes" in summary
    assert "DRY RUN - no files written" in summary
    assert "DRY RUN - no messages moved" in summary
    assert "Attachments found: 2" in summary
    assert "Files written: 0" in summary
    assert "Messages moved: 0" in summary


def test_safe_move_copies_then_deletes_and_expunges():
    connection = FakeMoveConnection(copy_status="OK", source_contains_uid=False)
    client = ImapClient(
        host="imap.mail.yahoo.com",
        port=993,
        user="user@example.com",
        password="not-used",
        connection=connection,
    )

    client.move_message("42", "ARS Processed", source_folder="ARS Reports")

    assert connection.commands == [
        ("COPY", "42", '"ARS Processed"'),
        ("STORE", "42", "+FLAGS.SILENT", r"(\Deleted)"),
        ("EXPUNGE",),
        ("SELECT", '"ARS Reports"'),
        ("SEARCH", None, "UID", "42"),
    ]


def test_failed_copy_does_not_delete_source():
    connection = FakeMoveConnection(copy_status="NO", source_contains_uid=True)
    client = ImapClient(
        host="imap.mail.yahoo.com",
        port=993,
        user="user@example.com",
        password="not-used",
        connection=connection,
    )

    with pytest.raises(MailGatewayError):
        client.move_message("42", "ARS Processed", source_folder="ARS Reports")

    assert connection.commands == [("COPY", "42", '"ARS Processed"')]


def test_move_verification_failure_is_not_counted_as_moved(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeMoveVerificationClient(source_contains_uid=True),
    )

    result = run_gateway(
        FakeConfig(tmp_path=tmp_path, inbox_dir=tmp_path / "inbox"),
        dry_run=False,
        limit=1,
        order="newest",
    )

    assert result.messages_failed == 1
    assert result.messages_moved == 0
    assert result.files_written == 1
    assert result.messages[0].result == "move_verification_failed"
    assert result.warnings


def test_retry_does_not_write_duplicate_attachment(tmp_path: Path, monkeypatch):
    inbox_dir = tmp_path / "inbox"
    config = FakeConfig(tmp_path=tmp_path, inbox_dir=inbox_dir)

    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeMoveVerificationClient(source_contains_uid=True),
    )
    first = run_gateway(config, dry_run=False, limit=1, order="newest")

    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeMoveVerificationClient(source_contains_uid=False),
    )
    second = run_gateway(config, dry_run=False, limit=1, order="newest")

    assert first.files_written == 1
    assert second.files_written == 0
    assert second.duplicate_attachments == 1
    assert second.messages_moved == 1
    assert len(list(inbox_dir.iterdir())) == 1


def test_keep_source_copies_without_delete_and_reports_retained(tmp_path: Path, monkeypatch):
    client = FakeMoveVerificationClient(source_contains_uid=True)
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: client,
    )

    result = run_gateway(
        FakeConfig(tmp_path=tmp_path, inbox_dir=tmp_path / "inbox"),
        dry_run=False,
        limit=1,
        keep_source=True,
    )

    assert result.messages_accepted == 1
    assert result.messages_moved == 0
    assert result.messages_source_retained == 1
    assert result.messages[0].result == "source_retained"
    assert client.moves == [("1", "Processed", True)]


def test_deterministic_ordering_newest_before_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeOrderedImapClient(),
    )

    result = run_gateway(
        FakeConfig(tmp_path=tmp_path, inbox_dir=tmp_path / "inbox"),
        dry_run=True,
        limit=1,
        order="newest",
    )

    assert result.messages_seen == 1
    assert result.messages[0].uid == "2"
    assert result.messages[0].subject == "Newest report"


def test_deterministic_ordering_oldest_before_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeOrderedImapClient(),
    )

    result = run_gateway(
        FakeConfig(tmp_path=tmp_path, inbox_dir=tmp_path / "inbox"),
        dry_run=True,
        limit=1,
        order="oldest",
    )

    assert result.messages_seen == 1
    assert result.messages[0].uid == "1"
    assert result.messages[0].subject == "Oldest report"


def test_attachment_size_is_captured_in_processing_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "src.automation.mail_gateway.runner.ImapClient",
        lambda **kwargs: FakeOrderedImapClient(),
    )

    result = run_gateway(
        FakeConfig(tmp_path=tmp_path, inbox_dir=tmp_path / "inbox"),
        dry_run=True,
        limit=1,
        order="newest",
    )

    attachment = result.messages[0].attachments[0]
    summary = format_summary(result)

    assert attachment.filename == "newest.txt"
    assert attachment.size_bytes == len(b"newest-payload")
    assert f"size={len(b'newest-payload')} bytes" in summary


class FakeConfig:
    imap_host = "imap.mail.yahoo.com"
    imap_port = 993
    imap_user = "user@example.com"
    imap_password = "not-used"
    source_folder = "Inbox"
    processed_folder = "Processed"
    failed_folder = "Failed"
    allowed_senders = {"reports@example.com"}
    allowed_extensions = {".txt"}

    def __init__(self, *, tmp_path: Path, inbox_dir: Path):
        self.inbox_dir = inbox_dir
        self.manifest_path = tmp_path / "manifest.json"
        self.log_path = tmp_path / "gateway.log"


class FakeImapClient:
    moves = []

    def __enter__(self):
        self.__class__.moves = []
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def assert_folder_exists(self, folder: str):
        return None

    def select_folder(self, folder: str):
        return None

    def assert_folder_exists(self, folder: str):
        return None

    def select_folder(self, folder: str):
        return None

    def search_candidate_uids(self):
        return ["1"]

    def fetch_internal_date(self, uid: str):
        return datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc)

    def fetch_message(self, uid: str):
        return (
            b"From: Reports <reports@example.com>\r\n"
            b"Subject: ARS report\r\n"
            b"MIME-Version: 1.0\r\n"
            b"Content-Type: multipart/mixed; boundary=abc\r\n"
            b"\r\n"
            b"--abc\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"Body\r\n"
            b"--abc\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Disposition: attachment; filename=report.txt\r\n"
            b"\r\n"
            b"payload\r\n"
            b"--abc--\r\n"
        )

    def move_message(self, uid: str, folder: str):
        self.__class__.moves.append((uid, folder))
        raise AssertionError("dry-run must not move messages")


class FakeImapConnection:
    def __init__(self, *, select_status: str):
        self.select_status = select_status
        self.selected = []
        self.list_called = False

    def select(self, folder: str, readonly: bool = False):
        self.selected.append((folder, readonly))
        return self.select_status, [b"folder check failed"]

    def list(self, *args, **kwargs):
        self.list_called = True
        raise AssertionError("folder validation must not use IMAP LIST")


class FakeMoveConnection:
    def __init__(self, *, copy_status: str, source_contains_uid: bool):
        self.copy_status = copy_status
        self.source_contains_uid = source_contains_uid
        self.commands = []

    def uid(self, command: str, *args):
        if command == "COPY":
            self.commands.append((command, *args))
            return self.copy_status, [b"copy failed"]
        if command == "SEARCH":
            self.commands.append((command, *args))
            return "OK", [b"42" if self.source_contains_uid else b""]
        self.commands.append((command, *args))
        return "OK", [b"ok"]

    def select(self, folder: str, readonly: bool = False):
        self.commands.append(("SELECT", folder))
        return "OK", [b"selected"]

    def expunge(self):
        self.commands.append(("EXPUNGE",))
        return "OK", [b"expunged"]


class FakeMoveVerificationClient:
    def __init__(self, *, source_contains_uid: bool):
        self.source_contains_uid = source_contains_uid
        self.moves = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def assert_folder_exists(self, folder: str):
        return None

    def select_folder(self, folder: str):
        return None

    def search_candidate_uids(self):
        return ["1"]

    def fetch_internal_date(self, uid: str):
        return datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc)

    def fetch_message(self, uid: str):
        return _message_bytes(
            subject="Retry report",
            date_header="Sun, 05 Jul 2026 10:00:00 +0000",
            filename="retry.txt",
            payload=b"same-payload",
        )

    def move_message(
        self,
        uid: str,
        folder: str,
        *,
        source_folder: str,
        keep_source: bool = False,
    ):
        self.moves.append((uid, folder, keep_source))
        if keep_source:
            from src.automation.mail_gateway.imap_client import MoveResult

            return MoveResult(
                copied=True,
                source_deleted=False,
                source_verified_absent=False,
                source_retained=True,
            )
        if self.source_contains_uid:
            from src.automation.mail_gateway.imap_client import MoveVerificationError

            raise MoveVerificationError("UID 1 still visible in source")

        from src.automation.mail_gateway.imap_client import MoveResult

        return MoveResult(
            copied=True,
            source_deleted=True,
            source_verified_absent=True,
        )


class FakeOrderedImapClient:
    dates = {
        "1": datetime(2026, 7, 4, 10, 0, tzinfo=timezone.utc),
        "2": datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc),
    }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def assert_folder_exists(self, folder: str):
        return None

    def select_folder(self, folder: str):
        return None

    def search_candidate_uids(self):
        return ["1", "2"]

    def fetch_internal_date(self, uid: str):
        return self.dates[uid]

    def fetch_message(self, uid: str):
        if uid == "2":
            return _message_bytes(
                subject="Newest report",
                date_header="Sun, 05 Jul 2026 10:00:00 +0000",
                filename="newest.txt",
                payload=b"newest-payload",
            )

        return _message_bytes(
            subject="Oldest report",
            date_header="Sat, 04 Jul 2026 10:00:00 +0000",
            filename="oldest.txt",
            payload=b"old",
        )

    def move_message(self, uid: str, folder: str):
        raise AssertionError("dry-run must not move messages")


def _message_bytes(
    *,
    subject: str,
    date_header: str,
    filename: str,
    payload: bytes,
) -> bytes:
    return b"".join(
        [
            b"From: Reports <reports@example.com>\r\n",
            f"Subject: {subject}\r\n".encode(),
            f"Date: {date_header}\r\n".encode(),
            b"MIME-Version: 1.0\r\n",
            b"Content-Type: multipart/mixed; boundary=abc\r\n",
            b"\r\n",
            b"--abc\r\n",
            b"Content-Type: text/plain\r\n",
            b"\r\n",
            b"Body\r\n",
            b"--abc\r\n",
            b"Content-Type: text/plain\r\n",
            f"Content-Disposition: attachment; filename={filename}\r\n".encode(),
            b"\r\n",
            payload,
            b"\r\n",
            b"--abc--\r\n",
        ]
    )
