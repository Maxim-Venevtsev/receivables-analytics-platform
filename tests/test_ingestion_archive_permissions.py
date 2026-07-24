import importlib
import sys
import types
from pathlib import Path


def _import_run_ingestion(monkeypatch):
    parse_ascii = types.ModuleType("src.ingestion.parse_ascii")
    parse_ascii.parse_receivables_txt = lambda path: (None, {})
    load_to_postgres = types.ModuleType("src.ingestion.load_to_postgres")
    load_to_postgres.load_receivables_snapshot = lambda *args, **kwargs: None
    load_to_postgres.get_engine = lambda: None
    monkeypatch.setitem(sys.modules, "src.ingestion.parse_ascii", parse_ascii)
    monkeypatch.setitem(
        sys.modules,
        "src.ingestion.load_to_postgres",
        load_to_postgres,
    )
    monkeypatch.delitem(sys.modules, "src.ingestion.run_ingestion", raising=False)
    return importlib.import_module("src.ingestion.run_ingestion")


def test_archive_file_sets_0644_only_after_final_file_is_published(
    tmp_path: Path,
    monkeypatch,
):
    run_ingestion = _import_run_ingestion(monkeypatch)
    raw_dir = tmp_path / "raw"
    archive_dir = tmp_path / "archive"
    raw_dir.mkdir()
    archive_dir.mkdir()
    source = raw_dir / "report.txt"
    source.write_bytes(b"payload")
    chmod_calls = []
    real_chmod = Path.chmod

    def observed_chmod(path: Path, mode: int):
        assert path.parent == archive_dir
        assert path.exists()
        assert not source.exists()
        chmod_calls.append((path, mode))
        return real_chmod(path, mode)

    monkeypatch.setattr(run_ingestion, "ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(Path, "chmod", observed_chmod)

    archived = run_ingestion.archive_file(source)

    assert archived == archive_dir / "report.txt"
    assert archived.read_bytes() == b"payload"
    assert chmod_calls == [(archived, 0o644)]


def test_safe_move_to_non_archive_directory_does_not_change_permissions(
    tmp_path: Path,
    monkeypatch,
):
    run_ingestion = _import_run_ingestion(monkeypatch)
    source = tmp_path / "report.txt"
    failed_dir = tmp_path / "failed"
    failed_dir.mkdir()
    source.write_bytes(b"payload")
    chmod_calls = []

    monkeypatch.setattr(
        Path,
        "chmod",
        lambda path, mode: chmod_calls.append((path, mode)),
    )

    moved = run_ingestion.safe_move(source, failed_dir)

    assert moved == failed_dir / "report.txt"
    assert chmod_calls == []
