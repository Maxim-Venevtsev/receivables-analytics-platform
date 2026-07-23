from __future__ import annotations

import hashlib
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from src.automation.local_sync.config import LocalSyncConfig, LocalSyncConfigError
from src.automation.local_sync.file_transfer import (
    compute_sha256,
    download_and_verify,
    eligible_txt_files,
    handoff_verified,
    hash_suffix_name,
)
from src.automation.local_sync import file_transfer as file_transfer_module
from src.automation.local_sync.manifest import Manifest
from src.automation.local_sync.remote_client import (
    OpenSftpRemoteClient,
    RemoteClientError,
    RemoteFile,
)
from src.automation.local_sync.runner import (
    LocalSyncLockedError,
    process_lock,
    run_local_sync,
)


class FakeRemoteClient:
    def __init__(self, files: list[tuple[RemoteFile, bytes]], *, fail: set[str] | None = None):
        self.files = [item[0] for item in files]
        self.content = {item.remote_path: payload for item, payload in files}
        self.fail = fail or set()
        self.downloads: list[str] = []

    def list_files(self) -> list[RemoteFile]:
        return list(self.files)

    def stat_file(self, remote_path: str) -> RemoteFile:
        return next(item for item in self.files if item.remote_path == remote_path)

    def download_file(self, remote: RemoteFile, destination: Path) -> None:
        self.downloads.append(remote.remote_path)
        payload = self.content[remote.remote_path]
        if remote.filename in self.fail:
            destination.write_bytes(payload[: max(1, len(payload) // 2)])
            raise RuntimeError("interrupted")
        destination.write_bytes(payload)


def _remote(name: str, payload: bytes, mtime: str = "2026-01-01T00:00:00+00:00") -> tuple[RemoteFile, bytes]:
    return RemoteFile(f"/archive/{name}", name, len(payload), mtime), payload


def _config(tmp_path: Path) -> LocalSyncConfig:
    return LocalSyncConfig(
        ssh_host="example.invalid",
        ssh_port=22,
        ssh_user="sync-user",
        ssh_identity_file=None,
        remote_archive_dir="/archive",
        inbox_dir=tmp_path / "inbox",
        manifest_path=tmp_path / "manifest.json",
        log_path=tmp_path / "logs" / "sync.jsonl",
        raw_dir=tmp_path / "raw",
        archive_dir=tmp_path / "archive",
        failed_dir=tmp_path / "failed",
        allowed_extensions=frozenset({".txt"}),
        connect_timeout_seconds=30,
    )


def _set_required_env(monkeypatch, tmp_path: Path) -> None:
    values = {
        "LOCAL_SYNC_SSH_HOST": "example.invalid",
        "LOCAL_SYNC_SSH_USER": "sync-user",
        "LOCAL_SYNC_REMOTE_ARCHIVE_DIR": "/archive",
        "LOCAL_SYNC_RAW_DIR": str(tmp_path / "raw"),
        "RAW_DIR": str(tmp_path / "raw"),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_config_validation(monkeypatch, tmp_path: Path):
    for name in ["LOCAL_SYNC_SSH_HOST", "LOCAL_SYNC_SSH_USER", "LOCAL_SYNC_REMOTE_ARCHIVE_DIR"]:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LocalSyncConfigError, match="LOCAL_SYNC_SSH_HOST"):
        LocalSyncConfig.from_env(tmp_path / "missing.env")

    _set_required_env(monkeypatch, tmp_path)
    config = LocalSyncConfig.from_env(tmp_path / "missing.env")
    assert config.ssh_identity_file is None
    assert config.allowed_extensions == frozenset({".txt"})


def test_raw_dir_mismatch_rejected(monkeypatch, tmp_path: Path):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("RAW_DIR", str(tmp_path / "other"))
    with pytest.raises(LocalSyncConfigError, match="same directory"):
        LocalSyncConfig.from_env(tmp_path / "missing.env")


def test_dry_run_has_zero_writes(tmp_path: Path):
    config = _config(tmp_path)
    client = FakeRemoteClient([_remote("report.txt", b"payload")])
    result = run_local_sync(config, remote_client=client, dry_run=True)
    assert result.files_selected == 1
    assert result.ingestion_skipped
    assert list(tmp_path.iterdir()) == []


def test_empty_remote_archive(tmp_path: Path):
    result = run_local_sync(_config(tmp_path), remote_client=FakeRemoteClient([]), skip_ingestion=True)
    assert result.remote_files_seen == 0
    assert result.files_downloaded == 0


def test_one_missing_txt_downloads_verifies_and_hands_off(tmp_path: Path):
    config = _config(tmp_path)
    payload = b"payload"
    result = run_local_sync(config, remote_client=FakeRemoteClient([_remote("report.txt", payload)]), skip_ingestion=True)
    assert result.files_downloaded == result.files_verified == result.files_handed_off == 1
    assert (config.raw_dir / "report.txt").read_bytes() == payload
    assert not list(config.inbox_dir.glob("*.part"))


def test_no_missing_files_after_observation(tmp_path: Path):
    config = _config(tmp_path)
    item = _remote("report.txt", b"payload")
    client = FakeRemoteClient([item])
    run_local_sync(config, remote_client=client, skip_ingestion=True)
    second = run_local_sync(config, remote_client=client, skip_ingestion=True)
    assert second.missing_candidates == 0
    assert len(client.downloads) == 1


@pytest.mark.parametrize(
    ("order", "expected"),
    [("oldest", ["/archive/old.txt", "/archive/new.txt"]), ("newest", ["/archive/new.txt", "/archive/old.txt"])],
)
def test_multiple_file_order(tmp_path: Path, order: str, expected: list[str]):
    files = [
        _remote("new.txt", b"new", "2026-02-01T00:00:00+00:00"),
        _remote("old.txt", b"old", "2026-01-01T00:00:00+00:00"),
    ]
    client = FakeRemoteClient(files)
    run_local_sync(_config(tmp_path), remote_client=client, skip_ingestion=True, order=order)
    assert client.downloads == expected


def test_limit_applies_after_duplicate_filtering(tmp_path: Path):
    config = _config(tmp_path)
    files = [_remote("known.txt", b"known"), _remote("missing.txt", b"missing", "2026-02-01T00:00:00+00:00")]
    client = FakeRemoteClient(files)
    run_local_sync(config, remote_client=client, skip_ingestion=True, limit=1)
    second = run_local_sync(config, remote_client=client, skip_ingestion=True, limit=1)
    assert second.files_selected == 1
    assert client.downloads[-1] == "/archive/missing.txt"


def test_non_txt_remote_file_ignored(tmp_path: Path):
    item = RemoteFile("/archive/report.xlsx", "report.xlsx", 1, None)
    result = run_local_sync(_config(tmp_path), remote_client=FakeRemoteClient([(item, b"x")]), dry_run=True)
    assert result.eligible_remote_files == 0
    assert result.files_selected == 0


def test_interrupted_transfer_leaves_only_part(tmp_path: Path):
    config = _config(tmp_path)
    client = FakeRemoteClient([_remote("report.txt", b"payload")], fail={"report.txt"})
    result = run_local_sync(config, remote_client=client, skip_ingestion=True)
    assert not result.success
    assert (config.inbox_dir / "report.txt.part").exists()
    assert not (config.inbox_dir / "report.txt").exists()


def test_size_mismatch_blocks_publication(tmp_path: Path):
    config = _config(tmp_path)
    remote = RemoteFile("/archive/report.txt", "report.txt", 99, None)
    result = run_local_sync(config, remote_client=FakeRemoteClient([(remote, b"short")]), skip_ingestion=True)
    assert not result.success
    assert not (config.inbox_dir / "report.txt").exists()


def test_streaming_hash_calculation(tmp_path: Path):
    path = tmp_path / "large.txt"
    payload = b"abc" * 500_000
    path.write_bytes(payload)
    assert compute_sha256(path) == hashlib.sha256(payload).hexdigest()


def test_raw_copy_failure_removes_part_and_retains_staging(tmp_path: Path, monkeypatch):
    source = tmp_path / "inbox" / "report.txt"
    raw = tmp_path / "raw"
    source.parent.mkdir()
    source.write_bytes(b"verified payload")
    sha256 = compute_sha256(source)

    def partial_copy(_source, destination):
        Path(destination).write_bytes(b"partial")
        raise OSError("copy interrupted")

    monkeypatch.setattr(file_transfer_module.shutil, "copy2", partial_copy)
    with pytest.raises(OSError, match="interrupted"):
        handoff_verified(source, raw, sha256)

    assert source.exists()
    assert not (raw / "report.txt.part").exists()
    assert not (raw / "report.txt").exists()
    assert eligible_txt_files(raw) == []


def test_stale_raw_part_is_removed_before_copy(tmp_path: Path, monkeypatch):
    source = tmp_path / "inbox" / "report.txt"
    raw = tmp_path / "raw"
    source.parent.mkdir()
    raw.mkdir()
    source.write_bytes(b"payload")
    stale = raw / "report.txt.part"
    stale.write_bytes(b"stale partial")
    real_copy = file_transfer_module.shutil.copy2

    def checked_copy(copy_source, destination):
        assert not Path(destination).exists()
        return real_copy(copy_source, destination)

    monkeypatch.setattr(file_transfer_module.shutil, "copy2", checked_copy)
    result = handoff_verified(source, raw, compute_sha256(source))

    assert result.destination_path.read_bytes() == b"payload"
    assert not stale.exists()


def test_raw_hash_mismatch_blocks_publication_and_retains_staging(tmp_path: Path, monkeypatch):
    source = tmp_path / "inbox" / "report.txt"
    raw = tmp_path / "raw"
    source.parent.mkdir()
    source.write_bytes(b"payload")
    expected = compute_sha256(source)
    real_hash = file_transfer_module.compute_sha256

    def mismatching_hash(path: Path):
        if path.name.endswith(".part"):
            return "0" * 64
        return real_hash(path)

    monkeypatch.setattr(file_transfer_module, "compute_sha256", mismatching_hash)
    with pytest.raises(RuntimeError, match="hash mismatch"):
        handoff_verified(source, raw, expected)

    assert source.exists()
    assert not (raw / "report.txt.part").exists()
    assert not (raw / "report.txt").exists()
    assert eligible_txt_files(raw) == []


def test_raw_file_published_only_after_verified_part(tmp_path: Path, monkeypatch):
    source = tmp_path / "inbox" / "report.txt"
    raw = tmp_path / "raw"
    source.parent.mkdir()
    source.write_bytes(b"payload")
    real_copy = file_transfer_module.shutil.copy2
    observations = []

    def observed_copy(copy_source, destination):
        destination = Path(destination)
        observations.append((destination.name, (raw / "report.txt").exists()))
        return real_copy(copy_source, destination)

    monkeypatch.setattr(file_transfer_module.shutil, "copy2", observed_copy)
    result = handoff_verified(source, raw, compute_sha256(source))

    assert observations == [("report.txt.part", False)]
    assert result.destination_path.read_bytes() == b"payload"
    assert not source.exists()
    assert not (raw / "report.txt.part").exists()


def test_same_filename_same_hash_is_not_ingested_twice(tmp_path: Path):
    config = _config(tmp_path)
    config.archive_dir.mkdir()
    (config.archive_dir / "report.txt").write_bytes(b"payload")
    result = run_local_sync(config, remote_client=FakeRemoteClient([_remote("report.txt", b"payload")]), skip_ingestion=True)
    assert result.duplicate_content_files == 1
    assert result.files_handed_off == 0


def test_different_filename_same_hash_records_alias_without_handoff(tmp_path: Path):
    config = _config(tmp_path)
    config.archive_dir.mkdir()
    (config.archive_dir / "old.txt").write_bytes(b"payload")
    result = run_local_sync(config, remote_client=FakeRemoteClient([_remote("new.txt", b"payload")]), skip_ingestion=True)
    assert result.duplicate_content_files == 1
    assert not config.raw_dir.exists()


def test_duplicate_sha_in_verified_inbox_preserves_canonical_and_hands_off_once(tmp_path: Path):
    config = _config(tmp_path)
    config.inbox_dir.mkdir()
    canonical = config.inbox_dir / "canonical.txt"
    canonical.write_bytes(b"payload")
    sha256 = compute_sha256(canonical)
    manifest = Manifest.empty(config.manifest_path)
    manifest.record(
        sha256,
        verified_local_filename=canonical.name,
        local_path=str(canonical),
        state="verified_inbox",
    )
    manifest.save()

    result = run_local_sync(
        config,
        remote_client=FakeRemoteClient([_remote("alias.txt", b"payload")]),
        skip_ingestion=True,
    )
    record = Manifest.load(config.manifest_path).data["records"][sha256]

    assert result.duplicate_content_files == 1
    assert result.files_handed_off == 1
    assert record["handoff_filename"] == "canonical.txt"
    assert (config.raw_dir / "canonical.txt").exists()
    assert not (config.raw_dir / "alias.txt").exists()
    assert not (config.inbox_dir / "alias.txt").exists()
    assert {alias["filename"] for alias in record["aliases"]} == {"alias.txt"}


def test_same_filename_different_hash_gets_hash_suffix(tmp_path: Path):
    config = _config(tmp_path)
    config.archive_dir.mkdir()
    (config.archive_dir / "report.txt").write_bytes(b"old")
    payload = b"new"
    sha256 = hashlib.sha256(payload).hexdigest()
    result = run_local_sync(config, remote_client=FakeRemoteClient([_remote("report.txt", payload)]), skip_ingestion=True)
    assert result.files_handed_off == 1
    assert (config.raw_dir / hash_suffix_name("report.txt", sha256)).exists()


def test_archive_bootstrap_is_processed(tmp_path: Path):
    config = _config(tmp_path)
    config.archive_dir.mkdir()
    source = config.archive_dir / "historical.txt"
    source.write_bytes(b"history")
    run_local_sync(config, remote_client=FakeRemoteClient([]), skip_ingestion=True)
    record = Manifest.load(config.manifest_path).data["records"][compute_sha256(source)]
    assert record["state"] == "archived"


def test_existing_raw_triggers_ingestion(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.raw_dir.mkdir()
    (config.raw_dir / "pending.txt").write_bytes(b"payload")
    calls = []
    monkeypatch.setattr("src.automation.local_sync.runner.run_ingestion_command", lambda cfg: calls.append(cfg) or CompletedProcess([], 0, "", ""))
    result = run_local_sync(config, remote_client=FakeRemoteClient([]))
    assert result.ingestion_executed
    assert len(calls) == 1


def test_existing_failed_is_not_retried(tmp_path: Path):
    config = _config(tmp_path)
    config.failed_dir.mkdir()
    (config.failed_dir / "bad.txt").write_bytes(b"bad")
    result = run_local_sync(config, remote_client=FakeRemoteClient([_remote("bad.txt", b"bad")]), skip_ingestion=True)
    assert result.duplicate_content_files == 1
    assert not config.raw_dir.exists()


def test_verified_staging_resumes_handoff(tmp_path: Path):
    config = _config(tmp_path)
    config.inbox_dir.mkdir()
    (config.inbox_dir / "resume.txt").write_bytes(b"payload")
    result = run_local_sync(config, remote_client=FakeRemoteClient([]), skip_ingestion=True)
    assert result.files_handed_off == 1
    assert (config.raw_dir / "resume.txt").exists()


def test_corrupt_manifest_preserved_and_rebuilt(tmp_path: Path):
    config = _config(tmp_path)
    config.manifest_path.write_text("not json", encoding="utf-8")
    config.archive_dir.mkdir()
    (config.archive_dir / "history.txt").write_bytes(b"history")
    run_local_sync(config, remote_client=FakeRemoteClient([]), skip_ingestion=True)
    assert list(tmp_path.glob("manifest.json.corrupt-*"))
    assert len(Manifest.load(config.manifest_path).data["records"]) == 1


def test_atomic_manifest_save_and_backup(tmp_path: Path):
    path = tmp_path / "manifest.json"
    manifest = Manifest.empty(path)
    manifest.save()
    manifest.record("a" * 64, state="archived")
    manifest.save()
    assert path.with_suffix(".json.bak").exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_second_concurrent_process_is_blocked(tmp_path: Path):
    lock = tmp_path / "sync.lock"
    with process_lock(lock):
        with pytest.raises(LocalSyncLockedError):
            with process_lock(lock):
                pass


def test_ingestion_skipped_when_raw_empty(tmp_path: Path):
    result = run_local_sync(_config(tmp_path), remote_client=FakeRemoteClient([]))
    assert result.ingestion_skipped
    assert result.ingestion_skip_reason == "empty raw"


def test_ingestion_nonzero_exit_is_surfaced(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.raw_dir.mkdir()
    (config.raw_dir / "pending.txt").write_bytes(b"payload")
    monkeypatch.setattr("src.automation.local_sync.runner.run_ingestion_command", lambda cfg: CompletedProcess([], 7, "", "boom"))
    result = run_local_sync(config, remote_client=FakeRemoteClient([]))
    assert result.ingestion_exit_code == 7
    assert not result.success


def test_ingestion_failure_logs_redacted_bounded_output_tails(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.raw_dir.mkdir()
    (config.raw_dir / "pending.txt").write_bytes(b"payload")
    identity = tmp_path / "private-key"
    config = LocalSyncConfig(**{**config.__dict__, "ssh_identity_file": identity})
    stdout = "x" * 2500 + f" host={config.ssh_host}"
    stderr = "y" * 2500 + f" user={config.ssh_user} key={identity}"
    monkeypatch.setattr(
        "src.automation.local_sync.runner.run_ingestion_command",
        lambda cfg: CompletedProcess([], 9, stdout, stderr),
    )

    result = run_local_sync(config, remote_client=FakeRemoteClient([]))
    events = [json.loads(line) for line in config.log_path.read_text(encoding="utf-8").splitlines()]
    ingestion = next(event for event in events if event["event"] == "ingestion")
    combined = json.dumps(ingestion) + "\n" + "\n".join(result.failures)

    assert len(ingestion["stdout_tail"]) <= 2000
    assert len(ingestion["stderr_tail"]) <= 2000
    assert config.ssh_host not in combined
    assert config.ssh_user not in combined
    assert str(identity) not in combined
    assert "<redacted>" in combined
    assert "exit code 9" in result.failures[-1]


def test_remote_client_has_no_mutating_public_operations(tmp_path: Path):
    client = OpenSftpRemoteClient(_config(tmp_path))
    for name in ("upload", "delete", "remove", "rename", "move", "mkdir", "command"):
        assert not hasattr(client, name)


@pytest.mark.parametrize(
    "listed_path",
    ["report one.txt", "/archive/report one.txt"],
)
def test_sftp_inventory_accepts_filename_and_absolute_path_identically(
    tmp_path: Path,
    monkeypatch,
    listed_path: str,
):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        stdout = (
            "sftp> ls -l /archive\n"
            f"-rw-r--r-- 1 owner group 7 Jan 01 2026 {listed_path}\n"
            "drwxr-xr-x 1 owner group 0 Jan 01 2026 nested\n"
            "-rw-r--r-- 1 owner group 9 Jan 01 2026 ignored.xlsx\n"
        )
        return CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr("src.automation.local_sync.remote_client.subprocess.run", fake_run)
    files = OpenSftpRemoteClient(_config(tmp_path)).list_files()
    assert files == [RemoteFile("/archive/report one.txt", "report one.txt", 7, "2026-01-01T00:00:00+00:00")]
    assert captured["shell"] is False
    assert "StrictHostKeyChecking=no" not in captured["args"]
    assert captured["args"][-1] == "sync-user@example.invalid"


@pytest.mark.parametrize(
    "listed_path",
    [
        "/outside/report.txt",
        "/archive/../outside/report.txt",
        "../report.txt",
        "subdirectory/report.txt",
    ],
)
def test_sftp_inventory_rejects_unsafe_or_outside_paths(
    tmp_path: Path,
    monkeypatch,
    listed_path: str,
):
    def fake_run(args, **kwargs):
        stdout = f"-rw-r--r-- 1 owner group 7 Jan 01 2026 {listed_path}\n"
        return CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr("src.automation.local_sync.remote_client.subprocess.run", fake_run)
    with pytest.raises(RemoteClientError):
        OpenSftpRemoteClient(_config(tmp_path)).list_files()


@pytest.mark.parametrize(
    "listed_path",
    ["report.txt", "/archive/report.txt"],
)
def test_sftp_stat_accepts_filename_and_absolute_path_output(
    tmp_path: Path,
    monkeypatch,
    listed_path: str,
):
    commands = []

    def fake_batch(self, command):
        commands.append(command)
        return f"-rw-r--r-- 1 owner group 7 Jul 1 2026 {listed_path}\n"

    monkeypatch.setattr(OpenSftpRemoteClient, "_run_batch", fake_batch)
    result = OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")

    assert result == RemoteFile(
        "/archive/report.txt",
        "report.txt",
        7,
        "2026-07-01T00:00:00+00:00",
    )
    assert commands == ['ls -l "/archive/report.txt"']
    assert "-d" not in commands[0]


@pytest.mark.parametrize(
    "output",
    [
        "",
        "sftp> ls -l /archive/report.txt\n",
        "drwxr-xr-x 1 owner group 0 Jul 1 2026 /archive/report.txt\n",
        "lrwxrwxrwx 1 owner group 7 Jul 1 2026 /archive/report.txt\n",
    ],
)
def test_sftp_stat_rejects_zero_or_non_regular_entries(
    tmp_path: Path,
    monkeypatch,
    output: str,
):
    monkeypatch.setattr(OpenSftpRemoteClient, "_run_batch", lambda self, command: output)
    with pytest.raises(RemoteClientError, match="exactly one regular-file"):
        OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")


def test_sftp_stat_rejects_multiple_regular_entries(tmp_path: Path, monkeypatch):
    output = (
        "-rw-r--r-- 1 owner group 7 Jul 1 2026 /archive/report.txt\n"
        "-rw-r--r-- 1 owner group 8 Jul 1 2026 /archive/other.txt\n"
    )
    monkeypatch.setattr(OpenSftpRemoteClient, "_run_batch", lambda self, command: output)
    with pytest.raises(RemoteClientError, match="exactly one regular-file"):
        OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")


@pytest.mark.parametrize(
    "output",
    [
        "-rw-r--r-- malformed\n",
        "-rw-r--r-- 1 owner group not-a-size Jul 1 2026 /archive/report.txt\n",
    ],
)
def test_sftp_stat_rejects_malformed_regular_listing(
    tmp_path: Path,
    monkeypatch,
    output: str,
):
    monkeypatch.setattr(OpenSftpRemoteClient, "_run_batch", lambda self, command: output)
    with pytest.raises(RemoteClientError):
        OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")


@pytest.mark.parametrize(
    ("listed_path", "message"),
    [
        ("/archive/other.txt", "does not match"),
        ("/outside/report.txt", "outside"),
        ("/archive/../outside/report.txt", "Unsafe path"),
    ],
)
def test_sftp_stat_rejects_wrong_outside_or_traversal_result(
    tmp_path: Path,
    monkeypatch,
    listed_path: str,
    message: str,
):
    output = f"-rw-r--r-- 1 owner group 7 Jul 1 2026 {listed_path}\n"
    monkeypatch.setattr(OpenSftpRemoteClient, "_run_batch", lambda self, command: output)
    with pytest.raises(RemoteClientError, match=message):
        OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")


def test_sftp_stat_rejects_unsupported_sftp_command(tmp_path: Path, monkeypatch):
    def fake_run(args, **kwargs):
        return CompletedProcess(args, 1, "", "ls: Invalid flag -d")

    monkeypatch.setattr("src.automation.local_sync.remote_client.subprocess.run", fake_run)
    with pytest.raises(RemoteClientError, match="SFTP read operation failed"):
        OpenSftpRemoteClient(_config(tmp_path)).stat_file("/archive/report.txt")


def test_sftp_download_uses_read_only_get_command(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("src.automation.local_sync.remote_client.subprocess.run", fake_run)
    remote = RemoteFile("/archive/report one.txt", "report one.txt", 7, None)
    OpenSftpRemoteClient(_config(tmp_path)).download_file(remote, tmp_path / "report one.txt.part")
    assert captured["input"].startswith('get "/archive/report one.txt" ')
    assert all(word not in captured["input"] for word in ("put ", "rm ", "rename ", "mkdir "))


def test_remote_path_traversal_rejected(tmp_path: Path):
    client = OpenSftpRemoteClient(_config(tmp_path), executable="does-not-matter")
    remote = RemoteFile("/outside/report.txt", "report.txt", 1, None)
    with pytest.raises(RemoteClientError, match="outside"):
        client.download_file(remote, tmp_path / "report.txt.part")


def test_secrets_absent_from_logs_and_errors(tmp_path: Path):
    config = _config(tmp_path)
    secret_path = tmp_path / "private-secret-key"
    config = LocalSyncConfig(**{**config.__dict__, "ssh_identity_file": secret_path})

    class SecretFailure(FakeRemoteClient):
        def download_file(self, remote, destination):
            raise RuntimeError(f"failure for {config.ssh_user} {config.ssh_host} {secret_path}")

    result = run_local_sync(config, remote_client=SecretFailure([_remote("report.txt", b"x")]), skip_ingestion=True)
    combined = "\n".join(result.failures) + config.log_path.read_text(encoding="utf-8")
    assert config.ssh_user not in combined
    assert config.ssh_host not in combined
    assert str(secret_path) not in combined
