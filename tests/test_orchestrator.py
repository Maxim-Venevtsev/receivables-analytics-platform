from pathlib import Path
from subprocess import CompletedProcess

import pytest

from src.automation.mail_gateway.runner import GatewayResult
from src.automation.orchestrator.config import OrchestratorConfig
from src.automation.orchestrator.file_handoff import (
    compute_sha256,
    handoff_file,
    list_eligible_inbox_files,
)
from src.automation.orchestrator.runner import run_orchestrator


def test_dry_run_does_not_move_files(tmp_path: Path):
    inbox = tmp_path / "inbox"
    raw = tmp_path / "raw"
    inbox.mkdir()
    source = inbox / "report.txt"
    source.write_bytes(b"payload")

    result = handoff_file(source, raw, dry_run=True)

    assert not result.handed_off
    assert source.exists()
    assert not raw.exists()


def test_file_handoff_preserves_sha256(tmp_path: Path):
    inbox = tmp_path / "inbox"
    raw = tmp_path / "raw"
    inbox.mkdir()
    source = inbox / "report.txt"
    source.write_bytes(b"payload")
    expected_sha256 = compute_sha256(source)

    result = handoff_file(source, raw)

    assert result.handed_off
    assert result.sha256 == expected_sha256
    assert result.destination_path.exists()
    assert compute_sha256(result.destination_path) == expected_sha256
    assert not source.exists()


def test_filename_collision_creates_suffix(tmp_path: Path):
    inbox = tmp_path / "inbox"
    raw = tmp_path / "raw"
    inbox.mkdir()
    raw.mkdir()
    (raw / "report.txt").write_bytes(b"existing")
    source = inbox / "report.txt"
    source.write_bytes(b"new")

    result = handoff_file(source, raw)

    assert result.destination_path.name == "report_1.txt"
    assert (raw / "report.txt").read_bytes() == b"existing"
    assert result.destination_path.read_bytes() == b"new"


def test_ingestion_skipped_when_no_new_files(tmp_path: Path, monkeypatch):
    calls = {"ingestion": 0}
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_gateway",
        lambda *args, **kwargs: GatewayResult(dry_run=kwargs.get("dry_run", False)),
    )
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.MailGatewayConfig.from_env",
        lambda: object(),
    )
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: calls.__setitem__("ingestion", calls["ingestion"] + 1),
    )

    result = run_orchestrator(_config(tmp_path), dry_run=False)

    assert result.ingestion_skipped
    assert calls["ingestion"] == 0


def test_existing_inbox_file_detected_when_mail_writes_zero(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "030729.txt").write_bytes(b"backlog")

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_gateway",
        lambda *args, **kwargs: GatewayResult(dry_run=kwargs.get("dry_run", False), files_written=0),
    )
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.MailGatewayConfig.from_env",
        lambda: object(),
    )

    result = run_orchestrator(config, skip_ingestion=True)

    assert result.mail_ran
    assert result.mail_files_written == 0
    assert result.files_detected == 1
    assert result.files_handed_off == 1
    assert (config.raw_dir / "030729.txt").exists()
    assert not (config.mail_inbox_dir / "030729.txt").exists()


def test_ingestion_called_when_files_handed_off(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "report.txt").write_bytes(b"payload")
    calls = {"ingestion": 0}

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: _completed(returncode=0, calls=calls),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert result.files_handed_off == 1
    assert result.ingestion_ran
    assert result.success
    assert calls["ingestion"] == 1


def test_ingestion_runs_when_raw_already_contains_files_without_handoff(
    tmp_path: Path,
    monkeypatch,
):
    config = _config(tmp_path)
    config.raw_dir.mkdir()
    (config.raw_dir / "already_handed_off.txt").write_bytes(b"payload")
    calls = {"ingestion": 0}

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: _completed(returncode=0, calls=calls),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert result.files_handed_off == 0
    assert result.raw_files_detected == 1
    assert result.ingestion_ran
    assert not result.ingestion_skipped
    assert calls["ingestion"] == 1


def test_empty_raw_directory_skips_ingestion(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.raw_dir.mkdir()
    calls = {"ingestion": 0}

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: _completed(returncode=0, calls=calls),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert result.raw_files_detected == 0
    assert result.ingestion_skipped
    assert result.ingestion_skip_reason == "empty raw"
    assert not result.ingestion_ran
    assert calls["ingestion"] == 0


def test_skip_mail_behavior_hands_off_existing_inbox_file(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "report.txt").write_bytes(b"payload")
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert not result.mail_ran
    assert result.files_detected == 1
    assert result.files_handed_off == 1


def test_skip_mail_hands_off_backlog_file(tmp_path: Path):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "030729.txt").write_bytes(b"payload")

    result = run_orchestrator(config, skip_mail=True, skip_ingestion=True)

    assert not result.mail_ran
    assert result.files_detected == 1
    assert result.files_handed_off == 1
    assert (config.raw_dir / "030729.txt").exists()


def test_dry_run_detects_backlog_but_does_not_move(tmp_path: Path):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    source = config.mail_inbox_dir / "030729.txt"
    source.write_bytes(b"payload")

    result = run_orchestrator(config, skip_mail=True, dry_run=True)

    assert result.files_detected == 1
    assert result.files_handed_off == 0
    assert source.exists()
    assert not config.raw_dir.exists()


def test_skip_ingestion_behavior(tmp_path: Path):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "report.txt").write_bytes(b"payload")

    result = run_orchestrator(config, skip_mail=True, skip_ingestion=True)

    assert result.files_handed_off == 1
    assert result.ingestion_skipped
    assert not result.ingestion_ran


def test_failed_handoff_prevents_ingestion(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "report.txt").write_bytes(b"payload")
    calls = {"ingestion": 0}

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.handoff_files",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("handoff failed")),
    )
    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: calls.__setitem__("ingestion", calls["ingestion"] + 1),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert not result.success
    assert not result.ingestion_ran
    assert calls["ingestion"] == 0
    assert result.errors


def test_failed_ingestion_returns_non_zero_result(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.mail_inbox_dir.mkdir()
    (config.mail_inbox_dir / "report.txt").write_bytes(b"payload")

    monkeypatch.setattr(
        "src.automation.orchestrator.runner.run_ingestion_command",
        lambda raw_dir: CompletedProcess(args=[], returncode=3, stdout="", stderr="boom"),
    )

    result = run_orchestrator(config, skip_mail=True)

    assert result.ingestion_ran
    assert result.ingestion_exit_code == 3
    assert result.exit_code == 1
    assert result.errors == ["Ingestion failed with exit code 3"]


def test_file_extension_filtering_ignores_non_handoff_files(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "report.txt").write_bytes(b"txt")
    (inbox / "report.xls").write_bytes(b"xls")
    (inbox / "report.xlsx").write_bytes(b"xlsx")
    (inbox / "manifest.json").write_bytes(b"{}")
    (inbox / "gateway.jsonl").write_bytes(b"{}")
    (inbox / "partial.tmp").write_bytes(b"tmp")
    (inbox / "payload.csv").write_bytes(b"csv")
    (inbox / "note.docx").write_bytes(b"docx")

    files = list_eligible_inbox_files(inbox)

    assert [path.name for path in files] == [
        "report.txt",
        "report.xls",
        "report.xlsx",
    ]


def _config(tmp_path: Path) -> OrchestratorConfig:
    return OrchestratorConfig(
        mail_inbox_dir=tmp_path / "inbox",
        raw_dir=tmp_path / "raw",
        log_path=tmp_path / "logs" / "automation.jsonl",
    )


def _completed(*, returncode: int, calls: dict[str, int]) -> CompletedProcess[str]:
    calls["ingestion"] += 1
    return CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")
