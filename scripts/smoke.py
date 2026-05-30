"""Smoke-test a source end-to-end from the command line.

Useful to validate a scraper / detect DOM drift before relying on it.

Examples:
    python scripts/smoke.py --source dummy
    python scripts/smoke.py --source egydir --city Alexandria --category Cosmetics --max 20
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from aol_leadfinder.config import get_categories, get_settings  # noqa: E402
from aol_leadfinder.core.orchestrator import run_search  # noqa: E402
from aol_leadfinder.scrapers.base import SearchRequest  # noqa: E402
from aol_leadfinder.storage.db import get_engine, read_all_leads  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, help="source key (repeatable)")
    parser.add_argument("--country", default="Egypt")
    parser.add_argument("--city", default="Alexandria")
    parser.add_argument("--category", default="Cosmetics")
    parser.add_argument("--max", type=int, default=25)
    args = parser.parse_args()

    keywords = next((c.get("keywords", []) for c in get_categories() if c["name"] == args.category), [])
    req = SearchRequest(
        country=args.country, city=args.city, category=args.category,
        keywords=keywords, max_results=args.max,
    )
    stats = run_search(req, args.source)
    print(f"STATS: found={stats.found} kept={stats.kept} dropped={stats.dropped} "
          f"created={stats.created} updated={stats.updated}")
    print(f"drop_reasons={stats.drop_reasons} errors={stats.errors}")

    leads = read_all_leads(get_engine(get_settings().db_path))
    print(f"\nDB now has {len(leads)} leads. Top 10 by score:")
    for lead in leads[:10]:
        print(f"  [{lead.tier:6}] {lead.score:3}  {lead.company_name}  "
              f"{lead.phone_e164 or '-'}  {lead.website or '-'}")


if __name__ == "__main__":
    main()
