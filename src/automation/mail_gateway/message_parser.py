from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True)
class ParsedMessage:
    sender_email: str
    subject: str
    message_date: str
    message_id: str
    attachments: list[Attachment]


def parse_message(raw_message: bytes) -> ParsedMessage:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)

    sender_email = _extract_sender(message)
    subject = str(message.get("Subject", ""))
    message_date = str(message.get("Date", ""))
    message_id = str(message.get("Message-ID", ""))

    attachments: list[Attachment] = []

    for part in message.walk():
        if part.get_content_disposition() != "attachment":
            continue

        filename = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            Attachment(
                filename=filename,
                content=payload,
                content_type=part.get_content_type(),
            )
        )

    return ParsedMessage(
        sender_email=sender_email,
        subject=subject,
        message_date=message_date,
        message_id=message_id,
        attachments=attachments,
    )


def _extract_sender(message: EmailMessage) -> str:
    addresses = getaddresses(message.get_all("From", []))
    if not addresses:
        return ""

    return addresses[0][1].lower()
