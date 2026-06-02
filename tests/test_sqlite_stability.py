"""SQLite stability pragmas (Sprint A, item 4): WAL + busy_timeout so the UI can
read while a run writes, and contended connections wait instead of erroring."""
from aol_leadfinder.storage.db import get_engine


def test_wal_mode_enabled(tmp_path):
    engine = get_engine(tmp_path / "leads.db")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def test_busy_timeout_set(tmp_path):
    engine = get_engine(tmp_path / "leads.db")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
