from pathlib import Path

import pytest

from src.ingestion import load_to_postgres


class FakeConnection:
    def __init__(self):
        self.snapshot_loads = []


class FakeTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.before = list(self.connection.snapshot_loads)
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.committed = True
        else:
            self.connection.snapshot_loads[:] = self.before
            self.rolled_back = True
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()
        self.transaction = FakeTransaction(self.connection)
        self.begin_calls = 0

    def begin(self):
        self.begin_calls += 1
        return self.transaction


def test_normal_loader_rolls_back_snapshot_metadata_when_fact_insert_fails(
    monkeypatch,
):
    engine = FakeEngine()
    source_path = Path("snapshot.txt")

    monkeypatch.setattr(load_to_postgres, "get_engine", lambda: engine)

    def create_snapshot_load(conn, df, metadata, path):
        assert conn is engine.connection
        conn.snapshot_loads.append(path.name)
        return 42

    def fail_fact_insert(conn, df, load_id):
        assert conn is engine.connection
        assert conn.snapshot_loads == [source_path.name]
        assert load_id == 42
        raise RuntimeError("fact insertion failed")

    monkeypatch.setattr(
        load_to_postgres,
        "_create_snapshot_load",
        create_snapshot_load,
    )
    monkeypatch.setattr(
        load_to_postgres,
        "_append_snapshot_facts",
        fail_fact_insert,
    )

    with pytest.raises(RuntimeError, match="fact insertion failed"):
        load_to_postgres.load_receivables_snapshot(
            object(),
            {},
            source_path,
        )

    assert engine.begin_calls == 1
    assert engine.connection.snapshot_loads == []
    assert engine.transaction.rolled_back is True
    assert engine.transaction.committed is False
