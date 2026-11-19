"""Biggest markets: where the most gold changes hands a day, and what the app knows about getting each item.

The user's idea (2026-11-19): TSM's prices already show which items are worth a lot and sell every day; list them,
say which ones the app has a way into (a craft, a farming spot, a flip), and for the rest point to the item's
Wowhead Forever page to find out how to get it.

Gold traded a day = the whole region's sales a day (TSM) x the usual sale price (`pricing.usual_sale`): a measure of
the market's size, not what you would earn (your share of it is smaller, and other sellers compete). What the app
knows about getting an item comes from the game data and the addons it reads: the recipes that make it, a vendor that
sells it, QuestieDB's mobs and objects that drop it (who, not how often), and container contents read on Wowhead.
"""
from __future__ import annotations

from .pricing import sold_per_day, usual_sale

WOWHEAD = 'https://www.wowhead.com/forever/item={}'
MIN_SOLD = 1.0              # sells at least once a day in the region
# the app's rows that are a real way into a market: crafts and flips (profit a day), farming spots (gold an hour).
# Not the "Farm X" material rows: their "a day" is your share of the whole market's value, not an income.
KIND_TEXT = {'craft': 'craft', 'vendor_flip': 'vendor flip', 'mob_spot': 'mob farming', 'skin_spot': 'skinning',
             'herb_spot': 'herbalism', 'mine_spot': 'mining', 'fishing_spot': 'fishing'}
HOURLY = {'mob_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'fishing_spot'}


def ways_in(o) -> dict:
    hourly = o.kind in HOURLY
    return {'kind': KIND_TEXT.get(o.kind, o.kind), 'title': o.title, 'key': o.key,
            'value': int((o.gph if hourly else o.daily) or 0), 'per': 'an hour' if hourly else 'a day',
            'profit_unit': o.profit_unit, 'doable': o.doable, 'needs': o.needs}


def _kinds(n: int, what: str) -> str:
    return f"{n} kind{'s' if n != 1 else ''} of {what}"


def build(prices: dict, items: dict, made_by: dict, sold_by_vendor, questie_items: dict, in_containers: set,
          rows_for: dict, limit: int = 150) -> list[dict]:
    """made_by: product -> [profession names]; sold_by_vendor(iid) -> bool; rows_for: item -> [Opportunity] (the
    app's rows that supply this item: crafts, flips, farming)."""
    out = []
    for iid, p in prices.items():
        spd = sold_per_day(p)
        if spd < MIN_SOLD:
            continue
        price = usual_sale(p) or 0
        if price <= 0:
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
                    'price': int(price), 'listed': int(p.get('numAuctions') or 0), 'sources': sources,
                    'ways': rows[:3], 'wowhead': WOWHEAD.format(iid)})
    out.sort(key=lambda r: -r['gold_a_day'])
    return out[:limit]
