"""Sprint metrics report — does enrichment actually raise lead quality?

Runs the chosen GREEN sources, scores each lead BEFORE enrichment, crawls its
website (About/Services/Contact), scores AFTER, and reports:
  - companies found / kept per source
  - leads upgraded Weak -> Medium/Hot by enrichment
  - tier distribution after enrichment
  - Top N Hot leads by Shipping Intent
  - per-source coverage (website / phone / email / enriched)

Usage:
  AOL_INSECURE_SSL=true python scripts/sprint_report.py \
    --source forwarding_companies --source freightclub --source wsdconnect \
    --category "Freight Forwarder" --country Egypt --max 10
"""
from __future__ import annotations

import argparse
import itertools
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from aol_leadfinder.config import get_categories, get_filters, get_scoring, get_settings  # noqa: E402
from aol_leadfinder.core.orchestrator import _enrich_website  # noqa: E402
from aol_leadfinder.enrichment.intelligence import classify_company  # noqa: E402
from aol_leadfinder.pipeline.filters import passes_filters  # noqa: E402
from aol_leadfinder.pipeline.normalize import normalize_lead  # noqa: E402
from aol_leadfinder.pipeline.score import score_lead  # noqa: E402
from aol_leadfinder.scrapers import registry  # noqa: E402
from aol_leadfinder.scrapers.base import SearchRequest  # noqa: E402

_RANK = {"Weak": 0, "Medium": 1, "Hot": 2}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", action="append", required=True)
    ap.add_argument("--category", default="Freight Forwarder")
    ap.add_argument("--country", default="Egypt")
    ap.add_argument("--max", type=int, default=10)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    scoring, filters = get_scoring(), get_filters()
    region = get_settings().default_region
    keywords = next((c.get("keywords", []) for c in get_categories() if c["name"] == args.category), [])
    req = SearchRequest(country=args.country, category=args.category, keywords=keywords, max_results=args.max)

    records: list[dict] = []
    coverage: dict[str, dict] = {}

    for src in args.source:
        scrapers = registry.instantiate([src])
        if src not in scrapers:
            print(f"[skip] {src} unavailable")
            continue
        cov = {"found": 0, "kept": 0, "upgraded": 0, "website": 0, "phone": 0, "email": 0, "enriched": 0, "drop": {}}
        try:
            for raw in itertools.islice(scrapers[src].search(req), args.max):
                cov["found"] += 1
                norm = normalize_lead(raw, default_country=args.country, region=region)
                if norm.description or norm.category:
                    intel = classify_company(norm.description or "", norm.category)
                    norm.company_type, norm.shipping_intent = intel.company_type, intel.shipping_intent
                    if intel.has_online_store:
                        norm.has_online_store = True
                ok, reason = passes_filters(norm, filters)
                if not ok:
                    cov["drop"][reason] = cov["drop"].get(reason, 0) + 1
                    continue
                cov["kept"] += 1
                _, tier_before, _ = score_lead(norm, scoring)
                if norm.website:
                    _enrich_website(norm, region)
                score_after, tier_after, _ = score_lead(norm, scoring)
                if _RANK.get(tier_after, 0) > _RANK.get(tier_before, 0):
                    cov["upgraded"] += 1
                cov["website"] += bool(norm.website)
                cov["phone"] += bool(norm.phone_e164)
                cov["email"] += bool(norm.email)
                cov["enriched"] += bool(norm.enriched)
                records.append({
                    "src": src, "name": norm.company_name, "type": norm.company_type,
                    "intent": norm.shipping_intent or 0, "tier_before": tier_before,
                    "tier_after": tier_after, "score_after": score_after,
                    "contact": norm.phone_e164 or norm.email or norm.website or "-",
                    "markets": ", ".join(norm.target_markets or []),
                })
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {src}: {type(exc).__name__}: {str(exc)[:120]}")
        coverage[src] = cov

    print("\n================ SPRINT ENRICHMENT REPORT ================")
    print(f"category={args.category!r} country={args.country!r} max/source={args.max}")

    print("\n--- Coverage per source ---")
    tot_kept = tot_up = 0
    for src, c in coverage.items():
        tot_kept += c["kept"]
        tot_up += c["upgraded"]
        print(f"  {src:22} found={c['found']:3} kept={c['kept']:3} enriched={c['enriched']:3} "
              f"web={c['website']:3} phone={c['phone']:3} email={c['email']:3} "
              f"upgraded={c['upgraded']:3} drops={c['drop']}")

    before_weak = sum(1 for r in records if r["tier_before"] == "Weak")
    print("\n--- Enrichment impact ---")
    print(f"  companies kept (before=after): {tot_kept}")
    print(f"  Weak before enrichment: {before_weak}")
    print(f"  upgraded Weak -> Medium/Hot:  {tot_up}")
    print(f"  tier AFTER enrichment: {dict(Counter(r['tier_after'] for r in records))}")

    print(f"\n--- Top {args.top} Hot Leads by Shipping Intent ---")
    for r in sorted(records, key=lambda x: x["intent"], reverse=True)[: args.top]:
        markets = f" [{r['markets']}]" if r["markets"] else ""
        print(f"  intent={r['intent']:3} {r['tier_after']:6} {r['name'][:30]:30} "
              f"{(r['type'] or '-'):16} {r['contact']}{markets}")


if __name__ == "__main__":
    main()
