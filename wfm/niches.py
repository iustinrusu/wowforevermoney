"""Niches: steady demand, low supply (strategy item 10, the user's idea of 2026-11-14).

An item is a niche when all of these hold (TSM data, region-wide counts from TSM users):
  it sells every day       your share of the region's sales is at least one a day
  most listings sell       sale rate of at least half
  few are listed           your realm lists at most 10, and less than a day of the region's sales (realm listings
                           against region sales alone let big commodities through: Silk Cloth, 1,132 listed)
  the price holds          the lowest listing is at least 90% of the usual sale price (or nothing is listed)
  you can supply it        a recipe (yours, or one you can learn), a vendor that sells it, or something you gather
Our own price snapshots add how often it was sold out (nothing listed while it keeps selling): the best sign that few
people supply it. It needs a week or more of snapshots to mean much; until then it is shown with its sample size and
only ranks a niche higher, never makes one. Limits: TSM has no seller counts, and a niche closes once others notice.
"""
from __future__ import annotations

MIN_SALE_RATE = 0.5
MAX_DAYS_LISTED = 1.0
MAX_LISTED = 10
PRICE_HOLDS = 0.9
SOLD_OUT_HINT = 0.3        # sold out in 30%+ of our snapshots: a sign of thin supply
SOLID_SCANS = 7 * 12       # about a week of hourly scans before the sold-out share means much


def sold_out_stats(rows) -> dict[int, dict]:
    """rows: (item, scans seen, scans with nothing listed) from the price history -> {item: {scans, sold_out}}."""
    return {int(i): {'scans': int(n), 'sold_out': (int(z) / int(n)) if n else 0.0} for i, n, z in rows}


def build(prices: dict, supply: dict[int, list], share: float, stats: dict[int, dict] | None = None,
          usual_sale=None, names=None) -> list[dict]:
    """supply: item -> [{kind, title, key, profit_unit, doable, needs}], the ways you can make or get it."""
    from .pricing import usual_sale as _usual
    usual_sale = usual_sale or _usual
    out = []
    for iid, ways in supply.items():
        p = prices.get(iid) or {}
        spd = float(p.get('regionSoldPerDay') or 0)
        rate = float(p.get('regionSalePercent') or 0)
        yours = spd * share
        if yours < 1 or rate < MIN_SALE_RATE:
            continue
        listed = int(p.get('numAuctions') or 0)
        days = listed / spd if spd else None
        if listed > MAX_LISTED or (days is not None and days >= MAX_DAYS_LISTED):
            continue
        sale = usual_sale(p)
        low = int(p.get('minBuyout') or 0) if listed else 0
        if not sale or (low and low < PRICE_HOLDS * sale):
            continue
        ways = [w for w in ways if (w.get('profit_unit') or 0) > 0]
        if not ways:
            continue
        best = max(ways, key=lambda w: (bool(w.get('doable')), w['profit_unit']))
        st = (stats or {}).get(iid) or {}
        why = [f'{yours:.1f} a day at your share of the region\'s {spd:,.0f}', f'{rate:.0%} of listings sell',
               f'{listed} listed on your realm' + (f' ({days:.1f} days of sales)' if days is not None else ''),
               ('nothing listed now' if not low else f'lowest listing {low / sale:.0%} of the usual sale price')]
        if st.get('scans'):
            why.append(f"sold out in {st['sold_out']:.0%} of our {st['scans']} snapshots"
                       + ('' if st['scans'] >= SOLID_SCANS else ' (too few snapshots yet to mean much)'))
        thin = st.get('sold_out', 0) >= SOLD_OUT_HINT
        out.append({'item_id': iid, 'name': names(iid) if names else str(iid), 'sold_per_day': round(yours, 1),
                    'sale_rate': round(rate, 2), 'listed': listed, 'days_listed': None if days is None else round(days, 2),
                    'sale': int(sale), 'lowest': low, 'sold_out': round(st.get('sold_out', 0), 2),
                    'scans': st.get('scans', 0), 'thin_supply': thin, 'how': best, 'ways': ways[:4],
                    'profit_day': int(best['profit_unit'] * yours), 'why': '; '.join(why)})
    # profit a day at your share, a thin-supply sign first among similar ones; what you can do now before the rest
    out.sort(key=lambda r: (not r['how'].get('doable'), -(r['profit_day'] * (1.25 if r['thin_supply'] else 1.0))))
    return out
