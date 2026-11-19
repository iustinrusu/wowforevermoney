"""Biggest markets: every item that sells, ranked by what it is worth and how big its market is, with what the app knows
about getting it.

The user's idea (2026-11-19): TSM's prices already show which items are worth a lot and sell every day; list them,
say which ones the app has a way into, and point to the item's Wowhead Forever page for the rest. Then (same day):
"biggest markets should be a complete list, ranked by individual value (and market cap should matter too), and the
ones that I can obtain or craft should be highlighted".

Three numbers per item (TSM, region): price each (`pricing.usual_sale`), sold a day, gold traded a day (sold a day x
price: the market's size, not your income). The ranking weighs both price and market size:
    score = price each x square root of sold a day   (= the square root of price x gold traded a day)
so a 180g sword that sells twice a day (score 255g) ranks next to Arcanite Bar (44g, 37 a day: 269g), far above
Runecloth (6s, 10,000 a day: 6g) whose market is huge but whose single unit is worth little. Other orders: gold
traded a day, or price each.

"Yours": the app has a row for it you can do now (a craft or flip you have the skill and tools for, a farming spot
you can do). "Way in": any row at all, doable or not.
"""
from __future__ import annotations

import math

from .pricing import sold_per_day, usual_sale

WOWHEAD = 'https://www.wowhead.com/forever/item={}'
# the app's rows that are a real way into a market: crafts and flips (profit a day), farming spots (gold an hour).
# Not the "Farm X" material rows: their "a day" is your share of the whole market's value, not an income.
KIND_TEXT = {'craft': 'craft', 'vendor_flip': 'vendor flip', 'mob_spot': 'mob farming', 'skin_spot': 'skinning',
             'herb_spot': 'herbalism', 'mine_spot': 'mining', 'fishing_spot': 'fishing'}
HOURLY = {'mob_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'fishing_spot'}
SORTS = {'score': lambda r: -r['score'], 'gold': lambda r: -r['gold_a_day'], 'price': lambda r: -r['price']}
FILTERS = {'all': lambda r: True, 'yours': lambda r: r['yours'], 'way': lambda r: bool(r['ways']),
           'noway': lambda r: not r['ways']}


def ways_in(o) -> dict:
    hourly = o.kind in HOURLY
    return {'kind': KIND_TEXT.get(o.kind, o.kind), 'title': o.title, 'key': o.key,
            'value': int((o.gph if hourly else o.daily) or 0), 'per': 'an hour' if hourly else 'a day',
            'profit_unit': o.profit_unit, 'doable': o.doable, 'needs': o.needs}


def _kinds(n: int, what: str) -> str:
    return f"{n} kind{'s' if n != 1 else ''} of {what}"


def score(price: float, sold: float) -> int:
    return int(price * math.sqrt(max(sold, 0.0)))


def build(prices: dict, items: dict, made_by: dict, sold_by_vendor, questie_items: dict, in_containers: set,
          rows_for: dict) -> list[dict]:
    """Every priced item with recorded sales. made_by: product -> [profession names]; sold_by_vendor(iid) -> bool;
    rows_for: item -> [Opportunity] (the app's rows that supply this item: crafts, flips, farming)."""
    out = []
    for iid, p in prices.items():
        spd = sold_per_day(p)
        price = usual_sale(p) or 0
        if spd <= 0 or price <= 0:
            continue
        it = items.get(iid)
        q = questie_items.get(iid) or {}
        sources = []
        if made_by.get(iid):
            sources.append('made by ' + ', '.join(sorted(set(made_by[iid]))))
        if sold_by_vendor(iid):
            sources.append('sold by a vendor')
        if q.get('npcDrops'):
            sources.append('drops from ' + _kinds(len(q['npcDrops']), 'mob'))
        if q.get('objectDrops'):
            sources.append('found in ' + _kinds(len(q['objectDrops']), 'object') + ' (nodes, chests)')
        if iid in in_containers:
            sources.append('found in containers')
        seen, rows = set(), []
        for o in rows_for.get(iid, []):
            if o.kind in KIND_TEXT and o.key not in seen and ((o.gph if o.kind in HOURLY else o.daily) or 0) > 0:
                seen.add(o.key)
                rows.append(ways_in(o))
        rows.sort(key=lambda r: (not r['doable'], r['per'] == 'an hour', -r['value']))
        out.append({'item_id': iid, 'name': it.name if it else str(iid), 'quality': it.quality if it else 1,
                    'category': it.category if it else '', 'gold_a_day': int(spd * price), 'sold_per_day': spd,
                    'price': int(price), 'score': score(price, spd), 'listed': int(p.get('numAuctions') or 0),
                    'sources': sources, 'ways': rows[:3], 'yours': any(r['doable'] for r in rows),
                    'wowhead': WOWHEAD.format(iid)})
    out.sort(key=SORTS['score'])
    return out


def page(rows: list[dict], sort: str = 'score', filt: str = 'all', offset: int = 0, limit: int = 100) -> dict:
    """One page of the list, sorted and filtered, with the counts for the page's header."""
    chosen = sorted((r for r in rows if FILTERS.get(filt, FILTERS['all'])(r)), key=SORTS.get(sort, SORTS['score']))
    for n, r in enumerate(chosen):
        r['rank'] = n + 1
    return {'rows': chosen[offset:offset + limit], 'total': len(chosen), 'all': len(rows),
            'yours': sum(1 for r in rows if r['yours']), 'way': sum(1 for r in rows if r['ways'])}
