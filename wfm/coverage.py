"""Forever source coverage: which traded materials we have Forever loot data for, and what to read next.

The user's top priority (2026-11-14): every material needs Forever source data (which mobs drop it, which mobs
it is skinned from, which nodes or pools give it), from online sources only, never our own loot logs. The source
is Wowhead Forever, read slowly by hand. An item's Wowhead page holds every source tab at once (Dropped by,
Skinned from, Mined from, Gathered from, Fished in, Contained in), so the reading unit is one item page.

A material here = something traded on the AH (TSM region sales >= min_sold a day) that is looted rather than only
crafted or bought: trade goods of a gathered kind (cloth, leather, metal & stone, meat, herbs, elemental, other),
raw fish and meat that recipes use, or anything QuestieDB (Forever) says drops from mobs or objects.

What counts as covered today: "Skinned from" read (data/wowhead_forever_skinning.json), "Fished in" through the
zone pages read (data/wowhead_forever_fishing.json), and any item page read in full (`pages`: item ids). Mob drops
and node yields have no Forever data yet: QuestieDB knows who drops an item in Forever but not how often.
"""
from __future__ import annotations

WOWHEAD = 'https://www.wowhead.com/forever/item={}'
TRADE_GOODS, CONSUMABLE, FOOD = 7, 0, 5
# trade goods subclass -> how it is mainly obtained (meat 8 and "other" 11 depend on whether it is a fish: see fish_hint)
KIND_OF_SUBCLASS = {5: 'drops', 6: 'skinning', 7: 'mining', 9: 'herbalism', 10: 'drops'}
MEAT, OTHER = 8, 11
KIND_TEXT = {'drops': 'dropped by mobs', 'skinning': 'skinned from mobs', 'mining': 'mined from veins',
             'herbalism': 'gathered from herbs', 'fishing': 'fished', 'objects': 'found in objects (nodes, chests)'}
MIN_SOLD = 1.0


def is_material(item) -> bool:
    return item.class_id == TRADE_GOODS or (item.class_id == CONSUMABLE and item.subclass_id == FOOD)


def expected_kinds(item, questie_item: dict, is_product: bool, is_reagent: bool, is_fish: bool = False) -> set[str]:
    """The ways this item is obtained in the world (empty: not looted). is_fish: it is in a fishing loot table (the
    Classic tables only say what to look for here; they are never used as data)."""
    q = questie_item or {}
    kinds = set()
    if is_fish:
        kinds.add('fishing')
    if q.get('npcDrops'):
        kinds.add('drops')
    if q.get('objectDrops'):
        kinds.add('objects')
    if item.class_id == TRADE_GOODS and item.subclass_id == MEAT and not is_fish and not is_product:
        kinds.add('drops')                                    # meat from beasts
    elif item.class_id == TRADE_GOODS and item.subclass_id in KIND_OF_SUBCLASS:
        kind = KIND_OF_SUBCLASS[item.subclass_id]
        bought = bool(q.get('vendors')) and not kinds
        crafted = is_product and not kinds and kind not in ('skinning', 'herbalism')   # bars, bolts
        if not (bought or crafted):
            kinds.add(kind)
    if kinds & {'mining', 'herbalism'}:
        kinds.discard('objects')      # nodes are the objects
    return kinds


def covered_kinds(iid: int, kinds: set[str], skinned: set[int], fished: set[int], pages: set[int]) -> set[str]:
    if iid in pages:
        return set(kinds)
    out = set()
    if 'skinning' in kinds and iid in skinned:
        out.add('skinning')
    if 'fishing' in kinds and iid in fished:
        out.add('fishing')
    return out


def audit(items: dict, prices: dict, questie_items: dict, recipes, skinning: dict | None, fishing: dict | None,
          pages: set[int] | None = None, fish_hint: set[int] | None = None, min_sold: float = MIN_SOLD) -> dict:
    """Coverage of every traded looted item and a reading queue: materials first, then other items (gear, books),
    each by most traded value first."""
    products = {r.product_id for r in recipes}
    reagents = {m for r in recipes for m, _ in r.reagents}
    skinned = {int(i) for i in ((skinning or {}).get('items') or {})}
    fished = {int(i) for z in (fishing or {}).values() for i in ((z or {}).get('items') or {})}
    fishy = fished | set(fish_hint or ())
    pages = set(pages or ())
    rows, by_kind = [], {}
    for iid, it in items.items():
        p = prices.get(iid) or {}
        spd = float(p.get('regionSoldPerDay') or 0)
        if spd < min_sold:
            continue
        kinds = expected_kinds(it, questie_items.get(iid), iid in products, iid in reagents, iid in fishy)
        if not kinds:
            continue
        have = covered_kinds(iid, kinds, skinned, fished, pages)
        for k in kinds:
            c = by_kind.setdefault(k, [0, 0])
            c[1] += 1
            c[0] += k in have
        price = p.get('regionSale') or p.get('marketValue') or 0
        rows.append({'item_id': iid, 'name': it.name, 'material': is_material(it), 'kinds': sorted(kinds), 'missing': sorted(kinds - have),
                     'sold_per_day': round(spd, 1), 'price': int(price), 'market': int(price * spd),
                     'url': WOWHEAD.format(iid)})
    rows.sort(key=lambda r: (not r['material'], -r['market']))
    queue = [r for r in rows if r['missing']]
    mats = [r for r in rows if r['material']]
    return {'total': len(rows), 'covered': len(rows) - len(queue), 'materials': len(mats),
            'materials_covered': sum(1 for r in mats if not r['missing']), 'by_kind': by_kind, 'queue': queue}


def describe(row: dict) -> str:
    """'Heavy Hide (4235): no Forever data on how it is skinned from mobs; ~12g traded a day'."""
    miss = ', '.join(KIND_TEXT[k] for k in row['missing'])
    return (f"{row['name']} ({row['item_id']}): no Forever data on how it is {miss}; "
            f"about {row['market'] / 10000:,.0f}g traded a day in the region")


def fish_items(classic_fishing) -> set[int]:
    """Items in any fishing or pool loot table: only a hint of what to look for on Wowhead Forever, never data."""
    if not classic_fishing:
        return set()
    from .classicdb import expected_items
    tables = list(classic_fishing.loot.values()) + [p.get('loot') or [] for p in classic_fishing.pools.values()]
    return {int(i) for t in tables for i in expected_items(t, classic_fishing.refs)}
