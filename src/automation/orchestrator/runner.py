from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.automation.mail_gateway.config import MailGatewayConfig
from src.automation.mail_gateway.runner import GatewayResult, run_gateway

from .config import PROJECT_ROOT, OrchestratorConfig
from .file_handoff import HandoffResult, handoff_files, list_eligible_inbox_files


@dataclass
class OrchestratorResult:
    dry_run: bool = False
    mail_ran: bool = False
    ingestion_ran: bool = False
    ingestion_skipped: bool = False
    handoff_count: int = 0
    files_detected: int = 0
    files_handed_off: int = 0
    raw_files_detected: int = 0
    ingestion_exit_code: int | None = None
    ingestion_skip_reason: str | None = None
    mail_files_written: int = 0
    success: bool = True
    mail_result: GatewayResult | None = None
    handoffs: list[HandoffResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.success else 1


def run_orchestrator(
    config: OrchestratorConfig,
    *,
    dry_run: bool = False,
    skip_mail: bool = False,
    skip_ingestion: bool = False,
    limit: int | None = None,
    mail_order: str = "newest",
) -> OrchestratorResult:
    logger = JsonlLogger(config.log_path)
    result = OrchestratorResult(dry_run=dry_run)

    try:
        if skip_mail:
            logger.write("mail_skipped", result="skipped")
        else:
            mail_config = MailGatewayConfig.from_env()
            result.mail_result = run_gateway(
                mail_config,
                dry_run=dry_run,
                limit=limit,
                order=mail_order,
            )
            result.mail_ran = True
            result.mail_files_written = result.mail_result.files_written
            logger.write(
                "mail_completed",
                result="success",
                files_written=result.mail_files_written,
                dry_run=dry_run,
            )

        candidate_files = list_eligible_inbox_files(config.mail_inbox_dir)
        if limit is not None:
            candidate_files = candidate_files[:limit]

        result.files_detected = len(candidate_files)
        result.handoffs = handoff_files(
            candidate_files,
            config.raw_dir,
            dry_run=dry_run,
        )
        result.handoff_count = len(result.handoffs)
        result.files_handed_off = sum(1 for handoff in result.handoffs if handoff.handed_off)

        for handoff in result.handoffs:
            logger.write(
                "file_handoff",
                result="handed_off" if handoff.handed_off else "dry_run",
                source_path=str(handoff.source_path),
                destination_path=str(handoff.destination_path),
                sha256=handoff.sha256,
                size_bytes=handoff.size_bytes,
                dry_run=dry_run,
            )

        raw_files = list_eligible_inbox_files(config.raw_dir)
        result.raw_files_detected = len(raw_files)
        logger.write(
            "raw_scan_completed",
            result="success",
            raw_files_detected=result.raw_files_detected,
            raw_dir=str(config.raw_dir),
        )

        if skip_ingestion:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "--skip-ingestion"
            logger.write("ingestion_skipped", result="skip_ingestion")
            return result

        if dry_run:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "dry_run"
            logger.write("ingestion_skipped", result="dry_run")
            return result

        if not raw_files:
            result.ingestion_skipped = True
            result.ingestion_skip_reason = "empty raw"
            logger.write("ingestion_skipped", result="empty_raw")
            return result

        completed = run_ingestion_command(config.raw_dir)
        result.ingestion_ran = True
        result.ingestion_exit_code = completed.returncode
        logger.write(
            "ingestion_finished",
            result="success" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

        if completed.returncode != 0:
            result.success = False
            result.errors.append(f"Ingestion failed with exit code {completed.returncode}")

    except Exception as exc:
        result.success = False
        result.errors.append(str(exc))
        logger.write(
            "orchestrator_failed",
            result="failed",
            error=type(exc).__name__,
            detail=str(exc),
        )

    return result


def run_ingestion_command(raw_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["RAW_DIR"] = str(raw_dir)

    return subprocess.run(
        [sys.executable, "-m", "src.ingestion.run_ingestion"],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
        env=env,
    )


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path

    def write(self, event: str, **fields) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            log_file.write("\n")
