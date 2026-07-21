from __future__ import annotations

import argparse

from .config import LocalSyncConfig, LocalSyncConfigError
from .remote_client import RemoteClientError
from .runner import LocalSyncLockedError, LocalSyncResult, run_local_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize the VPS report archive into local ingestion.")
    parser.add_argument("--dry-run", action="store_true", help="Plan without local writes or ingestion.")
    parser.add_argument("--skip-ingestion", action="store_true", help="Download and hand off without ingestion.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum missing files to download.")
    parser.add_argument("--order", choices=["oldest", "newest"], default="oldest", help="Missing-file selection order. Default: oldest.")
    parser.add_argument("--env-file", default=None, help="Optional environment file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    try:
        config = LocalSyncConfig.from_env(args.env_file)
        result = run_local_sync(
            config,
            dry_run=args.dry_run,
            skip_ingestion=args.skip_ingestion,
            limit=args.limit,
            order=args.order,
        )
    except (LocalSyncConfigError, LocalSyncLockedError, RemoteClientError) as exc:
        parser.exit(2, f"local sync error: {exc}\n")
    print(format_summary(result))
    return result.exit_code


def format_summary(result: LocalSyncResult) -> str:
    lines = [
        "Local Sync execution summary",
        f"Dry-run mode: {'yes' if result.dry_run else 'no'}",
        f"Remote files seen: {result.remote_files_seen}",
        f"Eligible remote TXT files: {result.eligible_remote_files}",
        f"Known content files: {result.known_content_files}",
        f"Missing candidates: {result.missing_candidates}",
        f"Files selected: {result.files_selected}",
        f"Files downloaded: {result.files_downloaded}",
        f"Files verified: {result.files_verified}",
        f"Duplicate-content files: {result.duplicate_content_files}",
        f"Files handed off: {result.files_handed_off}",
        f"RAW files detected: {result.raw_files_detected}",
        f"Ingestion executed: {'yes' if result.ingestion_executed else 'no'}",
        f"Ingestion skipped: {'yes' if result.ingestion_skipped else 'no'}",
        f"Reason: {result.ingestion_skip_reason or '-'}",
        f"Ingestion exit code: {result.ingestion_exit_code if result.ingestion_exit_code is not None else '-'}",
        f"Failures: {len(result.failures)}",
    ]
    for detail in result.details:
        lines.append(
            "- "
            f"{detail.remote_filename} | size={detail.remote_size} | "
            f"mtime={detail.remote_mtime or '-'} | sha256={detail.sha256 or '-'} | "
            f"verified={detail.verified_filename or '-'} | handoff={detail.handoff_filename or '-'} | "
            f"action={detail.action or '-'} | result={detail.result or '-'}"
        )
    lines.extend(f"- failure: {failure}" for failure in result.failures)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

