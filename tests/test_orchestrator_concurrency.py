"""Concurrent search (max_workers > 1) must match the sequential path's totals
and never trip SQLite's single-writer lock. The producer/consumer design keeps
all DB writes on the main thread, so the two paths are observationally equal."""
from typing import Iterator

from aol_leadfinder.config import Settings
from aol_leadfinder.core import orchestrator
from aol_leadfinder.core.orchestrator import run_search
from aol_leadfinder.scrapers.base import BaseScraper, RawLead, SearchRequest


class _SrcA(BaseScraper):
    key = "_srcA"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        for i in range(5):
            yield RawLead(company_name=f"A Co {i}", source=self.key, website=f"a{i}.example")


class _SrcB(BaseScraper):
    key = "_srcB"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        for i in range(5):
            yield RawLead(company_name=f"B Co {i}", source=self.key, website=f"b{i}.example")
        yield RawLead(company_name="Broken Co", source=self.key)  # no contact -> quarantine


class _Boom(BaseScraper):
    key = "_boom"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise RuntimeError("403 Client Error: Forbidden (cloudflare)")
        yield  # pragma: no cover - marks this a generator


def _totals(stats):
    return (stats.found, stats.kept, stats.dropped, stats.quarantined, stats.created, stats.updated)


def _run(monkeypatch, data_dir, scrapers, workers):
    monkeypatch.setattr(orchestrator, "get_filters", lambda: {})
    monkeypatch.setattr(orchestrator, "get_scoring", lambda: {})
    monkeypatch.setattr(orchestrator.registry, "instantiate", lambda keys: scrapers)
    settings = Settings(data_dir=data_dir)
    return run_search(SearchRequest(max_results=50), list(scrapers), settings=settings, max_workers=workers)


def test_concurrent_matches_sequential(tmp_path, monkeypatch):
    scrapers = {"_srcA": _SrcA(), "_srcB": _SrcB()}

    seq = _run(monkeypatch, tmp_path / "seq", scrapers, workers=1)
    conc = _run(monkeypatch, tmp_path / "conc", scrapers, workers=4)

    # 10 good leads (5+5, unique domains => no merges) + 1 quarantine.
    assert _totals(seq) == (11, 10, 0, 1, 10, 0)
    assert _totals(conc) == _totals(seq)
    assert conc.per_source["_srcA"].health == "ok"
    assert conc.per_source["_srcB"].health == "ok"


def test_concurrent_source_isolation(tmp_path, monkeypatch):
    scrapers = {"_srcA": _SrcA(), "_srcB": _SrcB(), "_boom": _Boom()}
    stats = _run(monkeypatch, tmp_path / "iso", scrapers, workers=4)

    # The raising source is recorded and classified, the others are unaffected.
    assert "_boom" in stats.errors
    assert stats.per_source["_boom"].health == "blocked"
    assert stats.per_source["_srcA"].health == "ok"
    assert stats.per_source["_srcB"].health == "ok"
    assert stats.kept == 10  # no DB lock, no lost leads
