"""Sprint A observability: per-source run metrics + health, persisted on Run.

Built up across the Sprint A commits — this file starts with the persistence
substrate (item 3) and grows to cover orchestrator metrics/health (items 1-2).
"""
from sqlalchemy import text
from sqlmodel import Session, select

from aol_leadfinder.storage.db import get_engine, init_db
from aol_leadfinder.storage.models import Run


def test_source_stats_roundtrip(tmp_path):
    engine = get_engine(tmp_path / "leads.db")
    init_db(engine)
    payload = {
        "egydir": {"found": 3, "kept": 2, "dropped": 1, "quarantined": 0, "errors": 0, "health": "ok"},
        "kompass_eg": {"found": 0, "kept": 0, "dropped": 0, "quarantined": 0, "errors": 1, "health": "blocked"},
    }
    with Session(engine) as s:
        s.add(Run(status="done", source_stats=payload))
        s.commit()
    with Session(engine) as s:
        run = s.exec(select(Run)).first()
    assert run.source_stats == payload


def test_migration_adds_source_stats_to_legacy_run_table(tmp_path):
    # Simulate a pre-Sprint-A database whose run table predates source_stats.
    engine = get_engine(tmp_path / "legacy.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE run (id INTEGER PRIMARY KEY, status TEXT)"))
    init_db(engine)  # idempotent migration must ADD the missing column
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(run)")}
    assert "source_stats" in cols
    init_db(engine)  # running again is a no-op (must not raise)
