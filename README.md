# 🚢 Air Ocean Lead Finder

A zero-budget, locally-run **B2B lead-generation tool** for Air Ocean Line (freight & shipping, Alexandria). It collects **publicly-published business contact data** from business directories, **filters** and **scores** it, and produces a clean **Excel / Google Sheet** for the sales team.

> **Compliance posture (v1).** The tool focuses on *public business data* (directories where companies publish their own contact details to be reached). Outreach in v1 is **manual** — the tool exports a list; the team messages people themselves. There is **no automated messaging** and the social-media / Truecaller scrapers are **off by default**. See [Deferred sources](#deferred-red-zone-sources) and [Legal notes](#legal--compliance-notes).

---

## Quickstart

### Windows (for the sales team)
1. Install **Python 3.10+** (tick *“Add Python to PATH”* in the installer).
2. Double-click **`setup.bat`** once (creates the environment, installs everything).
3. Double-click **`launcher.bat`** to start. The app opens in your browser.

### macOS / Linux (developers)
```bash
./setup.sh      # one-time
./run.sh        # start the app
```

---

## How it works (data flow)

```
Search (country / city / category / sources)
  → scrape (polite, rate-limited)
  → normalize (phone → E.164, website → domain, clean name)
  → dedup / upsert (no duplicates across re-runs)
  → filter (drop inactive / low-followers / no-phone / no-website)
  → score (0–100 → Hot / Medium / Weak, with an explainable breakdown)
  → store (SQLite) → display (grid) → export (Excel / Google Sheet)
```

## Data sources (tiered by feasibility)

| Tier | Sources | Status |
|---|---|---|
| 🟢 **green** | EgyDir ✅ *(implemented)* · Kompass EG, Freight Club, WSD Connect, Forwarding Companies *(wired, stubbed)* | public business directories — easy & compliant |
| 🟡 **yellow** | Google Maps, Yellow Pages EG | harder (Playwright + stealth), Phase 2, best-effort |
| 🔴 **deferred** | Facebook, Instagram, LinkedIn, Truecaller | **OFF by default**, ToS/legal risk — see below |

The **dummy** source (offline demo data) is enabled so you can see the whole pipeline work without any network.

---

## Configuration (no code needed)

All behaviour lives in `config/*.yaml`:

- **`categories.yaml`** — target industries + Arabic/English search keywords. Add one here or via the **Settings** page (➕).
- **`sources.yaml`** — which sources exist, their tier, whether they’re `enabled`, rate limits, and (for deferred) the required feature flag.
- **`scoring.yaml`** — lead-scoring weights and tier thresholds. Edit to retune; the score is transparent and shows *why* on screen.
- **`filters.yaml`** — the sales team’s quality rules: drop inactive pages (e.g. last active ≤ 2023), minimum followers, require phone, require website.

---

## Add a new directory source

1. Copy `src/aol_leadfinder/scrapers/green/egydir.py` to a new module.
2. Implement a pure `parse_listing(html)` classmethod with the site’s CSS selectors, and a thin `search()` that fetches.
3. Record a fixture in `tests/fixtures/<source>_sample.html` and add a parse test (see `tests/test_scrape_egydir.py`).
4. Add an entry in `config/sources.yaml` pointing at the module, and set `enabled: true`.

The scraper auto-registers (via `BaseScraper.__init_subclass__`) — no other wiring needed.

---

## Project structure

```
src/aol_leadfinder/
  ui/            Streamlit app (app.py + pages/)
  scrapers/      base.py + registry.py + green/ yellow/ deferred/
  pipeline/      normalize.py, dedup.py, filters.py, score.py
  storage/       models.py (SQLModel), db.py (upsert), sheets_sync.py
  export/        excel.py
  config.py      loads config/*.yaml + .env
config/          categories / sources / scoring / filters  (YAML)
tests/           unit tests + recorded HTML fixtures
scripts/smoke.py CLI to test a source end-to-end
```

## Testing

```bash
. .venv/bin/activate
pytest                                   # unit + fixture-based parse tests
python scripts/smoke.py --source dummy   # end-to-end smoke (offline)
```

Scraper tests run against **recorded HTML fixtures** (no live network) so they stay stable even when sites change. Use `scripts/smoke.py` against a live source to detect DOM drift.

---

## Deferred (RED-zone) sources

Facebook, Instagram, LinkedIn and Truecaller scraping are **scaffolded but intentionally not implemented**, and disabled behind `FEATURE_*` flags in `.env`. They:

- **violate those platforms’ Terms of Service** (active enforcement — e.g. *hiQ v. LinkedIn*), and
- may involve **individuals’ personal data**, which is restricted under Egypt’s PDPL.

Enabling them is opt-in and **at your own legal/operational risk**. Compliant alternatives: manual research, opt-in lead forms/landing pages, and platforms’ own messaging.

## Legal & compliance notes

- **Egypt PDPL (Law 151/2020):** executive regulations issued Nov 2025; full enforcement **Oct 31 2026**. Direct marketing (WhatsApp/SMS) requires **prior opt-in consent** + opt-out + a consent log. That’s why v1 outreach is manual.
- Respect each source’s **robots.txt / Terms** and keep the polite rate limits in `sources.yaml`.
- All data is stored **locally** (`data/leads.db`, git-ignored).
- Before enabling any automated outreach later, add opt-in capture, opt-out handling, and register the promotional line with the operator/NTRA.

## Roadmap

- **Phase 1 (now):** GREEN directories + filters + scoring + Excel/Sheets. *(EgyDir implemented; others stubbed.)*
- **Phase 2:** Google Maps + Yellow Pages (Playwright + stealth, best-effort).
- **Phase 3:** enrichment (website crawl for emails, e-commerce platform detection), better recency.
- **Phase 4 (separate decision):** compliant WhatsApp outreach (Cloud API + opt-in templates), follow-ups.
