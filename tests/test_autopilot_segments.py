"""Autopilot segment builder — pure rotation + de-dup logic (no network)."""
from aol_leadfinder.autopilot import build_segments

CFG = {
    "country": "Egypt",
    "roles": ["Manufacturer", "Importer"],
    "governorates": ["Cairo", "Giza"],
    "categories": ["Cosmetics", "Textiles"],
    "ecommerce_categories": ["Gift Shops"],
}
# matrix: 2 cats x 2 roles x 2 govs = 8, plus 1 ecom cat x 2 govs = 2 -> 10 combos


def test_builds_full_matrix_when_no_limit():
    segs = build_segments(CFG, today_ordinal=0, max_results=30, enrich=True, limit=None)
    assert len(segs) == 10
    assert all(s.country == "Egypt" and s.max_results == 30 and s.enrich_websites for s in segs)
    # e-commerce segments carry no role
    assert any(s.category == "Gift Shops" and s.role is None for s in segs)


def test_daily_slice_rotates_and_covers_everything():
    limit = 4
    seen = set()
    # 10 combos / 4 per day -> 3 slices; three consecutive days should cover all 10.
    for day in range(3):
        for s in build_segments(CFG, today_ordinal=day, max_results=30, enrich=True, limit=limit):
            seen.add((s.category, s.role, s.city))
    assert len(seen) == 10  # full coverage across the rotation

    day0 = {(s.category, s.role, s.city) for s in build_segments(CFG, today_ordinal=0, max_results=30, enrich=True, limit=limit)}
    day1 = {(s.category, s.role, s.city) for s in build_segments(CFG, today_ordinal=1, max_results=30, enrich=True, limit=limit)}
    assert day0 and day1 and day0 != day1  # different days -> different slices
    assert len(day0) <= limit


def test_enrich_flag_threads_through():
    segs = build_segments(CFG, today_ordinal=0, max_results=20, enrich=False, limit=None)
    assert all(s.enrich_websites is False for s in segs)
    assert all(s.max_results == 20 for s in segs)
