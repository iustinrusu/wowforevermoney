"""Worth adding to your TSM Sniper: items our own price snapshots often caught listed far below what they sell for.

Snipes themselves are not suggested any more (the user's decision, 2026-11-15): TSM's data reaches the app at best
hourly, so a cheap listing seen there is usually gone, and sniping happens in game within seconds (TSM's Sniper scans
live). What the history can tell is which items are worth watching for, and at what price:
  resale snipe   a snapshot's lowest listing under CHEAP x its reference (the lower of the realm's listing average
                 and the region's sale price at that time), for an item that sells (region 1+ a day). Snipe at
                 CHEAP x today's reference or less: about 35% profit after the AH cut at the usual price, a return
                 (ROI) of about 58% on what you pay at the snipe price, more if you buy for less.
  vendor snipe   a lowest listing under what a vendor pays for it. Snipe at the vendor price or less.
Ranked by how often it happened in our snapshots times what one catch is worth.
"""
from __future__ import annotations

from .pricing import roi, usual_sale

CHEAP = 0.6
MIN_SOLD = 1.0
MIN_SEEN = 2           # caught cheap in at least this many snapshots


def build(rows, prices: dict, vendor_sell: dict[int, int], names=None, scans: int = 0, cut: float = 0.05) -> list[dict]:
    """rows: (item, min_buyout, market, region_sale) per snapshot from the price history.

    A catch = a snapshot's lowest listing under CHEAP x the item's normal price: the lower of its typical lowest
    listing (the median over our snapshots) and its usual sale price. Measuring against the listing average instead
    made items whose lowest listing simply sits below the average look like snipes in 40% of snapshots."""
    lows: dict[int, list] = {}
    for item, mb, mv, rs in rows:
        if mb and mb > 0:
            lows.setdefault(item, []).append(mb)
    out = []
    for item, mbs in lows.items():
        p = prices.get(item) or {}
        spd = float(p.get('regionSoldPerDay') or 0)
        typical = sorted(mbs)[len(mbs) // 2]
        normal = min(x for x in (typical, usual_sale(p)) if x)
        v = vendor_sell.get(item) or 0
        options = []
        resale = sum(1 for mb in mbs if mb < CHEAP * normal)
        if resale >= MIN_SEEN and spd >= MIN_SOLD:
            price = int(CHEAP * normal)
            options.append(('resell on the AH', price, int(normal * (1 - cut)) - price, resale))
        vendor = sum(1 for mb in mbs if v and mb < v)
        if vendor >= MIN_SEEN:
            options.append(('sell to a vendor', v, 0, vendor))          # gain per catch depends on the listing
        for how, price, gain, k in options:
            out.append({'item_id': item, 'name': names(item) if names else str(item), 'how': how, 'snipe_at': price,
                        # resale: the profit on what you pay at the snipe price (at least: a cheaper catch gives more);
                        # vendor: none, the profit depends on the listing you catch
                        'gain': gain, 'roi': roi(gain, price) if gain else None,
                        'times': k, 'snapshots': len(mbs), 'share': round(k / len(mbs), 3),
                        'sold_per_day': round(spd, 1),
                        'why': (f"caught under {CHEAP:.0%} of its normal price ({normal}c: its typical lowest listing "
                                f"or usual sale, the lower) in {k} of {len(mbs)} snapshots; sells {spd:,.0f} a day in "
                                f"the region" if how.startswith('resell') else
                                f"listed below the vendor price ({v}c) in {k} of {len(mbs)} snapshots")})
    out.sort(key=lambda r: -(r['share'] * max(r['gain'], r['snipe_at'] // 10)))
    return out
