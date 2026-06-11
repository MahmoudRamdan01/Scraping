"""End-to-end wiring: run_search quarantines broken leads (separate from drops),
keeps valid ones, and excludes quarantined rows from the working list."""
from typing import Iterator

from aol_leadfinder.config import Settings
from aol_leadfinder.core import orchestrator
from aol_leadfinder.core.orchestrator import run_search
from aol_leadfinder.scrapers.base import BaseScraper, RawLead, SearchRequest
from aol_leadfinder.storage.db import get_engine, read_all_leads, read_quarantined


class _MixedScraper(BaseScraper):
    key = "_test_mixed"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        yield RawLead(company_name="Good Co", source=self.key, phone_raw="01012345678", website="good.example")
        yield RawLead(company_name="Broken Co", source=self.key)  # no contact -> quarantine
        yield RawLead(company_name="--", source=self.key, phone_raw="01087654321")  # junk name -> quarantine


def test_run_search_quarantines_broken_leads(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "get_filters", lambda: {})
    monkeypatch.setattr(orchestrator, "get_scoring", lambda: {})
    monkeypatch.setattr(orchestrator.registry, "instantiate", lambda keys: {"_test_mixed": _MixedScraper()})

    settings = Settings(data_dir=tmp_path)
    stats = run_search(SearchRequest(max_results=10), ["_test_mixed"], settings=settings)

    assert stats.found == 3
    assert stats.kept == 1
    assert stats.dropped == 0
    assert stats.quarantined == 2
    assert set(stats.quarantine_reasons) == {"no_contact", "junk_name"}

    engine = get_engine(settings.db_path)
    assert len(read_all_leads(engine)) == 1  # only the good lead reaches the working list
    assert len(read_quarantined(engine)) == 2  # both broken records held for review
