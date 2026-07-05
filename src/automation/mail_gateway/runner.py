from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .attachment_storage import compute_sha256, store_attachment
from .config import MailGatewayConfig
from .imap_client import ImapClient, MoveVerificationError
from .manifest import Manifest
from .message_parser import parse_message
from .validators import ValidationError, validate_extension, validate_sender


@dataclass
class AttachmentReport:
    filename: str
    size_bytes: int
    sha256: str
    action: str
    result: str


@dataclass
class MessageReport:
    uid: str
    sender: str | None = None
    subject: str | None = None
    internal_date: str | None = None
    message_date: str | None = None
    action: str = "process_message"
    result: str = "unknown"
    attachments: list[AttachmentReport] = field(default_factory=list)


@dataclass(frozen=True)
class MessageRef:
    uid: str
    internal_date: datetime | None


@dataclass
class GatewayResult:
    dry_run: bool = False
    messages_seen: int = 0
    messages_accepted: int = 0
    messages_skipped: int = 0
    messages_failed: int = 0
    attachments_found: int = 0
    attachments_accepted: int = 0
    attachments_rejected: int = 0
    duplicate_attachments: int = 0
    files_written: int = 0
    messages_moved: int = 0
    messages_source_retained: int = 0
    warnings: list[str] = field(default_factory=list)
    messages: list[MessageReport] = field(default_factory=list)


def run_gateway(
    config: MailGatewayConfig,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    order: str = "newest",
    target_uids: list[str] | None = None,
    keep_source: bool = False,
) -> GatewayResult:
    if order not in {"newest", "oldest"}:
        raise ValueError("order must be 'newest' or 'oldest'")

    manifest = Manifest.load(config.manifest_path)
    logger = JsonlLogger(
        config.log_path,
        redacted_values=[config.imap_password],
    )
    result = GatewayResult(dry_run=dry_run)

    with ImapClient(
        host=config.imap_host,
        port=config.imap_port,
        user=config.imap_user,
        password=config.imap_password,
    ) as imap:
        imap.assert_folder_exists(config.source_folder)
        imap.assert_folder_exists(config.processed_folder)
        imap.assert_folder_exists(config.failed_folder)
        imap.select_folder(config.source_folder)

        candidate_uids = target_uids or imap.search_candidate_uids()
        candidate_messages = _order_messages(
            [
                MessageRef(
                    uid=uid,
                    internal_date=imap.fetch_internal_date(uid),
                )
                for uid in candidate_uids
            ],
            order=order,
        )

        for message_ref in candidate_messages:
            if limit is not None and result.messages_seen >= limit:
                break

            uid = message_ref.uid
            result.messages_seen += 1
            message_report = MessageReport(
                uid=uid,
                internal_date=_format_dt(message_ref.internal_date),
            )

            if manifest.message_processed(uid):
                result.messages_skipped += 1
                message_report.result = "skipped"
                result.messages.append(message_report)
                logger.write(
                    "message_skipped",
                    message_uid=uid,
                    internal_date=message_report.internal_date,
                    action="skip",
                    result="manifest",
                )
                continue

            parsed = None
            try:
                raw_message = imap.fetch_message(uid)
                parsed = parse_message(raw_message)
                message_report.sender = parsed.sender_email
                message_report.subject = parsed.subject
                message_report.message_date = parsed.message_date
                result.attachments_found += len(parsed.attachments)
                validate_sender(parsed.sender_email, config.allowed_senders)

                if not parsed.attachments:
                    raise ValidationError("Message has no attachments")

                accepted_count = 0
                files_written = 0
                duplicate_count = 0
                attachment_results = []

                for attachment in parsed.attachments:
                    sha256 = compute_sha256(attachment.content)
                    try:
                        validate_extension(
                            attachment.filename,
                            config.allowed_extensions,
                        )
                    except ValidationError:
                        result.attachments_rejected += 1
                        message_report.attachments.append(
                            AttachmentReport(
                                filename=attachment.filename,
                                size_bytes=len(attachment.content),
                                sha256=sha256,
                                action="reject",
                                result="invalid_extension",
                            )
                        )
                        logger.write(
                            "attachment_result",
                            message_uid=uid,
                            sender=parsed.sender_email,
                            subject=parsed.subject,
                            internal_date=message_report.internal_date,
                            message_date=parsed.message_date,
                            attachment_name=attachment.filename,
                            attachment_size_bytes=len(attachment.content),
                            sha256=sha256,
                            action="reject",
                            result="invalid_extension",
                            dry_run=dry_run,
                        )
                        raise

                    if manifest.has_attachment(sha256):
                        duplicate_count += 1
                        message_report.attachments.append(
                            AttachmentReport(
                                filename=attachment.filename,
                                size_bytes=len(attachment.content),
                                sha256=sha256,
                                action="skip",
                                result="duplicate",
                            )
                        )
                        logger.write(
                            "attachment_result",
                            message_uid=uid,
                            sender=parsed.sender_email,
                            subject=parsed.subject,
                            internal_date=message_report.internal_date,
                            message_date=parsed.message_date,
                            attachment_name=attachment.filename,
                            attachment_size_bytes=len(attachment.content),
                            sha256=sha256,
                            action="skip",
                            result="duplicate",
                            dry_run=dry_run,
                        )
                        continue

                    if dry_run:
                        saved_path = None
                        saved_filename = None
                        action = "dry_run"
                        result_name = "accepted"
                    else:
                        stored = store_attachment(
                            inbox_dir=config.inbox_dir,
                            original_filename=attachment.filename,
                            content=attachment.content,
                        )
                        saved_path = str(stored.saved_path)
                        saved_filename = stored.saved_filename
                        manifest.add_attachment(
                            sha256=sha256,
                            filename=stored.saved_filename,
                            saved_path=str(stored.saved_path),
                            message_uid=uid,
                            sender=parsed.sender_email,
                        )
                        action = "save"
                        result_name = "saved"
                        files_written += 1

                    attachment_results.append(
                        {
                            "original_filename": attachment.filename,
                            "saved_filename": saved_filename,
                            "saved_path": saved_path,
                            "sha256": sha256,
                            "size_bytes": len(attachment.content),
                            "action": action,
                            "result": result_name,
                        }
                    )
                    message_report.attachments.append(
                        AttachmentReport(
                            filename=attachment.filename,
                            size_bytes=len(attachment.content),
                            sha256=sha256,
                            action=action,
                            result=result_name,
                        )
                    )
                    logger.write(
                        "attachment_result",
                        message_uid=uid,
                        sender=parsed.sender_email,
                        subject=parsed.subject,
                        internal_date=message_report.internal_date,
                        message_date=parsed.message_date,
                        attachment_name=attachment.filename,
                        attachment_size_bytes=len(attachment.content),
                        sha256=sha256,
                        action=action,
                        result=result_name,
                        dry_run=dry_run,
                    )
                    accepted_count += 1

                message_details = {
                    "sender": parsed.sender_email,
                    "subject": parsed.subject,
                    "internal_date": message_report.internal_date,
                    "message_date": parsed.message_date,
                    "message_id": parsed.message_id,
                    "attachments": attachment_results,
                }

                if not dry_run:
                    manifest.save()
                    try:
                        move_result = imap.move_message(
                            uid,
                            config.processed_folder,
                            source_folder=config.source_folder,
                            keep_source=keep_source,
                        )
                    except MoveVerificationError as exc:
                        manifest.add_message(
                            message_uid=uid,
                            status="move_verification_failed",
                            details={**message_details, "error": str(exc)},
                        )
                        manifest.save()
                        result.messages_failed += 1
                        message_report.result = "move_verification_failed"
                        result.messages.append(message_report)
                        result.warnings.append(str(exc))
                        result.attachments_accepted += accepted_count
                        result.files_written += files_written
                        result.duplicate_attachments += duplicate_count
                        logger.write(
                            "message_failed",
                            message_uid=uid,
                            sender=parsed.sender_email,
                            subject=parsed.subject,
                            internal_date=message_report.internal_date,
                            message_date=parsed.message_date,
                            action="move_message",
                            result="move_verification_failed",
                            detail=str(exc),
                            dry_run=dry_run,
                        )
                        continue

                    if move_result.source_retained:
                        status = "source_retained"
                        result.messages_source_retained += 1
                        message_report.result = "source_retained"
                        result.warnings.append(
                            f"UID {uid} copied to {config.processed_folder}; source retained by --keep-source."
                        )
                    else:
                        status = "processed"
                        result.messages_moved += 1
                        message_report.result = "success"

                    manifest.add_message(
                        message_uid=uid,
                        status=status,
                        details={**message_details, "move": move_result.__dict__},
                    )
                    manifest.save()

                result.messages_accepted += 1
                if dry_run:
                    message_report.result = "success"
                result.messages.append(message_report)
                result.attachments_accepted += accepted_count
                if not dry_run:
                    result.files_written += files_written
                result.duplicate_attachments += duplicate_count
                logger.write(
                    "message_processed",
                    message_uid=uid,
                    sender=parsed.sender_email,
                    subject=parsed.subject,
                    internal_date=message_report.internal_date,
                    message_date=parsed.message_date,
                    action="process_message",
                    result="success",
                    attachments_found=len(parsed.attachments),
                    attachments_accepted=accepted_count,
                    files_written=files_written if not dry_run else 0,
                    messages_moved=0 if dry_run or keep_source else 1,
                    source_retained=keep_source,
                    duplicate_attachments=duplicate_count,
                    dry_run=dry_run,
                )

            except Exception as exc:
                result.messages_failed += 1
                message_report.result = "failed"
                if parsed:
                    message_report.sender = parsed.sender_email
                    message_report.subject = parsed.subject
                    message_report.message_date = parsed.message_date
                result.messages.append(message_report)
                logger.write(
                    "message_failed",
                    message_uid=uid,
                    sender=parsed.sender_email if parsed else None,
                    subject=parsed.subject if parsed else None,
                    internal_date=message_report.internal_date,
                    message_date=parsed.message_date if parsed else None,
                    action="process_message",
                    result="failed",
                    error=type(exc).__name__,
                    detail=str(exc),
                    dry_run=dry_run,
                )

                if not dry_run:
                    manifest.add_message(
                        message_uid=uid,
                        status="failed",
                        details={
                            "error": type(exc).__name__,
                            "detail": str(exc),
                        },
                    )
                    manifest.save()
                    move_result = imap.move_message(
                        uid,
                        config.failed_folder,
                        source_folder=config.source_folder,
                        keep_source=keep_source,
                    )
                    if move_result.source_retained:
                        result.messages_source_retained += 1
                    else:
                        result.messages_moved += 1

    return result


def _order_messages(messages: list[MessageRef], *, order: str) -> list[MessageRef]:
    reverse = order == "newest"

    return sorted(
        messages,
        key=lambda message: (
            message.internal_date or datetime.min.replace(tzinfo=timezone.utc),
            _uid_as_int(message.uid),
        ),
        reverse=reverse,
    )


def _uid_as_int(uid: str) -> int:
    try:
        return int(uid)
    except ValueError:
        return 0


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


class JsonlLogger:
    def __init__(self, path: Path, redacted_values: list[str] | None = None):
        self.path = path
        self.redacted_values = [value for value in redacted_values or [] if value]

    def write(self, event: str, **fields) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **self._redact(fields),
        }
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            log_file.write("\n")

    def _redact(self, value):
        if isinstance(value, str):
            redacted = value
            for secret in self.redacted_values:
                redacted = redacted.replace(secret, "[REDACTED]")
            return redacted

        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self._redact(item) for item in value]

        return value
