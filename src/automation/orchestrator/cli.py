from __future__ import annotations

import argparse

from .config import OrchestratorConfig, OrchestratorConfigError
from .runner import OrchestratorResult, run_orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Mail Gateway, hand off files, and trigger ingestion."
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write, move, or run ingestion.")
    parser.add_argument("--skip-mail", action="store_true", help="Skip Mail Gateway and hand off existing inbox files.")
    parser.add_argument("--skip-ingestion", action="store_true", help="Skip ingestion after handoff.")
    parser.add_argument("--limit", type=int, default=None, help="Mail Gateway message limit.")
    parser.add_argument(
        "--order",
        choices=["newest", "oldest"],
        default="newest",
        help="Mail Gateway message order. Default: newest.",
    )
    parser.add_argument("--env-file", default=None, help="Optional .env path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = OrchestratorConfig.from_env(args.env_file)
    except OrchestratorConfigError as exc:
        parser.exit(status=2, message=f"orchestrator config error: {exc}\n")

    result = run_orchestrator(
        config,
        dry_run=args.dry_run,
        skip_mail=args.skip_mail,
        skip_ingestion=args.skip_ingestion,
        limit=args.limit,
        mail_order=args.order,
    )

    print(format_summary(result))
    return result.exit_code


def format_summary(result: OrchestratorResult) -> str:
    lines = [
        "Automation orchestrator summary",
        f"Dry-run mode: {'yes' if result.dry_run else 'no'}",
        f"Mail Gateway ran: {'yes' if result.mail_ran else 'no'}",
        f"Mail files written this run: {result.mail_files_written}",
        f"Inbox files detected for handoff: {result.files_detected}",
        f"Files handed off: {result.files_handed_off}",
        f"RAW files detected: {result.raw_files_detected}",
        f"Ingestion executed: {'yes' if result.ingestion_ran else 'no'}",
        f"Ingestion skipped: {'yes' if result.ingestion_skipped else 'no'}",
        f"Reason: {result.ingestion_skip_reason or '-'}",
    ]

    if result.ingestion_exit_code is not None:
        lines.append(f"Ingestion exit code: {result.ingestion_exit_code}")

    if result.mail_result is not None:
        lines.extend(
            [
                f"Mail messages seen: {result.mail_result.messages_seen}",
                f"Mail attachments found: {result.mail_result.attachments_found}",
                f"Mail files written: {result.mail_result.files_written}",
            ]
        )

    if result.handoffs:
        lines.append("Handoff details:")
        for handoff in result.handoffs:
            lines.append(
                "- "
                f"{handoff.source_path.name} -> {handoff.destination_path.name} | "
                f"size={handoff.size_bytes} bytes | sha256={handoff.sha256} | "
                f"result={'handed_off' if handoff.handed_off else 'dry_run'}"
            )

    if result.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
