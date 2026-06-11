"""Sprint A observability: per-source run metrics + health, persisted on Run.

Covers the persistence substrate (item 3) and the orchestrator-level per-source
metrics + health classification (items 1-2).
"""
from datetime import datetime, timedelta
from typing import Iterator

from sqlalchemy import text
from sqlmodel import Session, select

from aol_leadfinder.config import Settings
from aol_leadfinder.core import orchestrator
from aol_leadfinder.core.orchestrator import _looks_blocked, run_search
from aol_leadfinder.scrapers.base import BaseScraper, RawLead, SearchRequest
from aol_leadfinder.storage.db import get_engine, init_db
from aol_leadfinder.storage.models import Run


# ---- item 3: persistence substrate ----------------------------------------

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


# ---- items 1-2: per-source metrics + health -------------------------------

class _MixedScraper(BaseScraper):
    key = "_mixed"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        yield RawLead(company_name="Good Co", source=self.key, phone_raw="01012345678", website="good.example")
        yield RawLead(company_name="Broken Co", source=self.key)  # no contact -> quarantine
        yield RawLead(company_name="--", source=self.key, phone_raw="01087654321")  # junk name -> quarantine


class _EmptyScraper(BaseScraper):
    key = "_empty"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        return iter(())


class _BlockedScraper(BaseScraper):
    key = "_blocked"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise RuntimeError("403 Client Error: Forbidden (cloudflare)")
        yield  # pragma: no cover - marks this a generator


class _BoomScraper(BaseScraper):
    key = "_boom"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise RuntimeError("unexpected kaboom")
        yield  # pragma: no cover - marks this a generator


def _run(monkeypatch, tmp_path, scrapers):
    monkeypatch.setattr(orchestrator, "get_filters", lambda: {})
    monkeypatch.setattr(orchestrator, "get_scoring", lambda: {})
    monkeypatch.setattr(orchestrator.registry, "instantiate", lambda keys: scrapers)
    settings = Settings(data_dir=tmp_path)
    stats = run_search(SearchRequest(max_results=10), list(scrapers), settings=settings)
    return stats, settings


def test_per_source_metrics_and_ok_health(tmp_path, monkeypatch):
    stats, settings = _run(monkeypatch, tmp_path, {"_mixed": _MixedScraper()})

    ss = stats.per_source["_mixed"]
    assert (ss.found, ss.kept, ss.quarantined, ss.dropped) == (3, 1, 2, 0)
    assert ss.health == "ok"
    # aggregate totals are unchanged by the per-source bookkeeping
    assert (stats.found, stats.kept, stats.quarantined) == (3, 1, 2)

    # persisted on the Run row as JSON
    engine = get_engine(settings.db_path)
    with Session(engine) as s:
        run = s.exec(select(Run)).first()
    assert run.source_stats["_mixed"]["kept"] == 1
    assert run.source_stats["_mixed"]["health"] == "ok"
    assert run.source_stats["_mixed"]["errors"] == 0


def test_empty_blocked_error_health_and_source_isolation(tmp_path, monkeypatch):
    scrapers = {
        "_mixed": _MixedScraper(),
        "_empty": _EmptyScraper(),
        "_blocked": _BlockedScraper(),
        "_boom": _BoomScraper(),
    }
    stats, _ = _run(monkeypatch, tmp_path, scrapers)

    assert stats.per_source["_empty"].health == "empty"
    assert stats.per_source["_blocked"].health == "blocked"
    assert stats.per_source["_boom"].health == "error"
    # a failing source never aborts the others
    assert stats.per_source["_mixed"].health == "ok"
    assert stats.kept == 1


def test_looks_blocked():
    assert _looks_blocked("403 Forbidden")
    assert _looks_blocked("Cloudflare challenge encountered")
    assert _looks_blocked("HTTP 429 Too Many Requests")
    assert not _looks_blocked("connection reset by peer")
    assert not _looks_blocked(None)


def test_read_runs_newest_first(tmp_path):
    from aol_leadfinder.storage.db import read_runs

    engine = get_engine(tmp_path / "leads.db")
    init_db(engine)
    t0 = datetime(2026, 1, 1, 10, 0, 0)
    with Session(engine) as s:
        s.add(Run(status="done", started_at=t0, source_stats={"a": {"found": 1, "kept": 1, "health": "ok"}}))
        s.add(Run(status="done", started_at=t0 + timedelta(hours=1),
                  source_stats={"a": {"found": 0, "kept": 0, "health": "empty"}}))
        s.commit()
    runs = read_runs(engine, limit=10)
    assert [r.started_at for r in runs] == [t0 + timedelta(hours=1), t0]
