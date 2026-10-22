"""Tests for standalone hot backup utility (tools.backup_db)."""

import gzip
from pathlib import Path
import sqlite3
import pytest

from tools.backup_db import backup_database, get_default_db_path, main


def test_backup_database_creates_valid_compressed_archive(tmp_path: Path) -> None:
    # 1. Create a dummy sqlite db with tables and data
    src_db = tmp_path / "test_source.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO test (name) VALUES ('Garuda'), ('Bhubaneswar');")
    conn.commit()
    conn.close()

    # 2. Run backup
    backup_dir = tmp_path / "backups"
    archive = backup_database(db_path=src_db, output_dir=backup_dir)

    assert archive.exists()
    assert archive.name.endswith(".db.gz")
    assert archive.parent == backup_dir

    # 3. Verify latest symlink
    latest_symlink = backup_dir / f"{src_db.stem}_latest.db.gz"
    if latest_symlink.exists():
        assert latest_symlink.resolve() == archive.resolve()

    # 4. Decompress and verify integrity
    with gzip.open(archive, "rb") as f_gz:
        content = f_gz.read()

    restored_db = tmp_path / "restored.db"
    restored_db.write_bytes(content)

    r_conn = sqlite3.connect(str(restored_db))
    assert r_conn.execute("PRAGMA integrity_check;").fetchall() == [("ok",)]
    rows = r_conn.execute("SELECT name FROM test ORDER BY id;").fetchall()
    assert rows == [("Garuda",), ("Bhubaneswar",)]
    r_conn.close()


def test_backup_database_raises_when_source_missing(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.db"
    backup_dir = tmp_path / "backups"

    with pytest.raises(FileNotFoundError, match="Source database file not found"):
        backup_database(db_path=non_existent, output_dir=backup_dir)


def test_backup_database_raises_on_integrity_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src_db = tmp_path / "test_corrupt.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (x INT);")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"

    original_connect = sqlite3.connect

    class FakeCursor:
        def execute(self, sql: str) -> None:
            pass

        def fetchall(self) -> list[tuple[str]]:
            return [("corruption detected in page 2",)]

        def close(self) -> None:
            pass

    class FakeConn:
        def __init__(self, real_conn: sqlite3.Connection):
            self.real_conn = real_conn

        def backup(self, target: sqlite3.Connection) -> None:
            self.real_conn.backup(target)

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            self.real_conn.close()

    call_count = 0

    def fake_connect(database: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        real = original_connect(database, *args, **kwargs)
        if call_count == 3:
            return FakeConn(real)
        return real

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    with pytest.raises(RuntimeError, match="Integrity check failed"):
        backup_database(db_path=src_db, output_dir=backup_dir)


def test_backup_main_cli_success(tmp_path: Path) -> None:
    src_db = tmp_path / "cli_test.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (val TEXT);")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "cli_backups"
    exit_code = main(["--db-path", str(src_db), "--output-dir", str(backup_dir)])
    assert exit_code == 0
    assert any(backup_dir.glob("*.db.gz"))


def test_get_default_db_path_fallback() -> None:
    path = get_default_db_path()
    assert isinstance(path, Path)
