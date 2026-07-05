from __future__ import annotations

import argparse

from .config import ConfigError, MailGatewayConfig
from .imap_client import MailGatewayError
from .runner import GatewayResult, run_gateway


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch validated ARS report attachments from Yahoo Mail."
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files or move messages.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of candidate messages to inspect.")
    parser.add_argument(
        "--order",
        choices=["newest", "oldest"],
        default="newest",
        help="Message processing order before applying --limit. Default: newest.",
    )
    parser.add_argument(
        "--uid",
        action="append",
        default=None,
        help="Process a specific IMAP UID. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Copy processed messages to target folder but intentionally keep them in source.",
    )
    parser.add_argument("--env-file", default=None, help="Optional .env path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = MailGatewayConfig.from_env(args.env_file)
        result = run_gateway(
            config,
            dry_run=args.dry_run,
            limit=args.limit,
            order=args.order,
            target_uids=_parse_uids(args.uid),
            keep_source=args.keep_source,
        )
    except (ConfigError, MailGatewayError) as exc:
        parser.exit(status=2, message=f"mail gateway error: {exc}\n")

    print(format_summary(result))

    return 0


def format_summary(result: GatewayResult) -> str:
    lines = [
        "Mail gateway execution summary",
        f"Dry-run mode: {'yes' if result.dry_run else 'no'}",
    ]

    if result.dry_run:
        lines.extend(
            [
                "DRY RUN - no files written",
                "DRY RUN - no messages moved",
            ]
        )

    lines.extend(
        [
            f"Messages seen: {result.messages_seen}",
            f"Messages accepted: {result.messages_accepted}",
            f"Messages failed: {result.messages_failed}",
            f"Messages skipped: {result.messages_skipped}",
            f"Attachments found: {result.attachments_found}",
            f"Attachments accepted: {result.attachments_accepted}",
            f"Attachments rejected: {result.attachments_rejected}",
            f"Duplicate attachments: {result.duplicate_attachments}",
            f"Files written: {result.files_written}",
            f"Messages moved: {result.messages_moved}",
            f"Messages source retained: {result.messages_source_retained}",
        ]
    )

    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"- {warning}")

    if result.messages:
        lines.append("Message details:")
        for message in result.messages:
            identity = [
                f"UID {message.uid}",
                f"result={message.result}",
            ]
            if message.internal_date:
                identity.append(f"internal_date={message.internal_date}")
            if message.message_date:
                identity.append(f"message_date={message.message_date}")
            if message.sender:
                identity.append(f"sender={message.sender}")
            if message.subject:
                identity.append(f"subject={message.subject}")
            lines.append("- " + " | ".join(identity))

            for attachment in message.attachments:
                lines.append(
                    "  attachment: "
                    f"{attachment.filename} | "
                    f"size={attachment.size_bytes} bytes | "
                    f"sha256={attachment.sha256} | "
                    f"action={attachment.action} | "
                    f"result={attachment.result}"
                )

    return "\n".join(lines)


def _parse_uids(values: list[str] | None) -> list[str] | None:
    if not values:
        return None

    uids = []
    for value in values:
        uids.extend(uid.strip() for uid in value.split(",") if uid.strip())

    return uids or None


if __name__ == "__main__":
    raise SystemExit(main())
