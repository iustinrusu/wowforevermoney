"""Forever source coverage: which traded materials we have Forever loot data for, and what to read next.

The user's top priority (2026-11-14): every material needs Forever source data (which mobs drop it, which mobs
it is skinned from, which nodes or pools give it), from online sources only, never our own loot logs. The source
is Wowhead Forever, read slowly by hand. An item's Wowhead page holds every source tab at once (Dropped by,
Skinned from, Mined from, Gathered from, Fished in, Contained in), so the reading unit is one item page.

A material here = something traded on the AH (TSM region sales >= min_sold a day) that is looted rather than only
crafted or bought: trade goods of a gathered kind (cloth, leather, metal & stone, meat, herbs, elemental, other),
raw fish and meat that recipes use, or anything QuestieDB (Forever) says drops from mobs or objects.

What counts as covered: "Skinned from" read (data/wowhead_forever_skinning.json), "Fished in" through the zone
pages read (data/wowhead_forever_fishing.json), the ways an item page read in full has Forever rows for (`pages`:
item id -> ways, from data/wowhead_forever_items.json; a plain set of ids means every way), and, for herbs and ore,
any item listed on a node's own page read in full (`node_items`). QuestieDB knows who drops an item in Forever but
not how often, so it never counts as covered. An item whose page was read but has no Forever rows for some way
leaves the reading queue for `read_no_data`: Wowhead hasn't recorded it yet, so re-read it later.
"""
from __future__ import annotations

from .pricing import usual_sale

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
        # bars and bolts are made, never mined or dropped as such: only the sources Questie lists count (a bar found in
        # chests is looted from objects, not mined: Truesilver Bar was expected "mined" and could never be covered)
        crafted = is_product and kind not in ('skinning', 'herbalism')
        if not (bought or crafted):
            kinds.add(kind)
    if kinds & {'mining', 'herbalism'}:
        kinds.discard('objects')      # nodes are the objects
    return kinds


def covered_kinds(iid: int, kinds: set[str], skinned: set[int], fished: set[int], pages,
                  node_items: set[int] = frozenset()) -> set[str]:
    out = set()
    if iid in pages:
        ways = pages[iid] if isinstance(pages, dict) else None
        if ways is None:
            return set(kinds)
        out |= kinds & ways
    if iid in node_items:
        out |= kinds & {'mining', 'herbalism'}
    if 'skinning' in kinds and iid in skinned:
        out.add('skinning')
    if 'fishing' in kinds and iid in fished:
        out.add('fishing')
    return out


def audit(items: dict, prices: dict, questie_items: dict, recipes, skinning: dict | None, fishing: dict | None,
          pages: set[int] | None = None, fish_hint: set[int] | None = None, min_sold: float = MIN_SOLD,
          node_items: set[int] | None = None, unlooted: set[int] | None = None) -> dict:
    """Coverage of every traded looted item and a reading queue: materials first, then other items (gear, books),
    each by most traded value first."""
    products = {r.product_id for r in recipes}
    reagents = {m for r in recipes for m, _ in r.reagents}
    skinned = {int(i) for i in ((skinning or {}).get('items') or {})}
    fished = {int(i) for z in (fishing or {}).values() for i in ((z or {}).get('items') or {})}
    fishy = fished | set(fish_hint or ())
    pages = pages if isinstance(pages, dict) else {i: None for i in (pages or ())}
    node_items = set(node_items or ())
    rows, by_kind = [], {}
    for iid, it in items.items():
        p = prices.get(iid) or {}
        spd = float(p.get('regionSoldPerDay') or 0)
        if spd < min_sold:
            continue
        kinds = expected_kinds(it, questie_items.get(iid), iid in products, iid in reagents, iid in fishy)
        if not kinds or (iid in products and iid in (unlooted or ())):
            continue          # crafted: a recipe makes it and its Wowhead Forever page lists no way to loot it
        have = covered_kinds(iid, kinds, skinned, fished, pages, node_items)
        for k in kinds:
            c = by_kind.setdefault(k, [0, 0])
            c[1] += 1
            c[0] += k in have
        price = usual_sale(p) or p.get('marketValue') or 0
        rows.append({'item_id': iid, 'name': it.name, 'material': is_material(it), 'kinds': sorted(kinds),
                     'missing': sorted(kinds - have), 'read': iid in pages,
                     'sold_per_day': round(spd, 1), 'price': int(price), 'market': int(price * spd),
                     'url': WOWHEAD.format(iid)})
    rows.sort(key=lambda r: (not r['material'], -r['market']))
    queue = [r for r in rows if r['missing'] and not r['read']]
    waiting = [r for r in rows if r['missing'] and r['read']]
    mats = [r for r in rows if r['material']]
    return {'total': len(rows), 'covered': sum(1 for r in rows if not r['missing']), 'materials': len(mats),
            'materials_covered': sum(1 for r in mats if not r['missing']), 'by_kind': by_kind, 'queue': queue,
            'read_no_data': waiting}


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


# ---------- the reading queue: items and mobs, by gold a day the app can't see yet ----------
QUEUE_LEN = 150
MIN_SPAWNS = 5          # a mob with fewer spawn points in Forever (QuestieDB) is a rare or named one: not a farm


def spawn_points(npc: dict | None) -> int:
    sp = (npc or {}).get('spawns')
    return sum(len(v or []) for v in sp.values()) if isinstance(sp, dict) else 0


def dungeon_only(engine, iid: int) -> bool:
    """Every mob QuestieDB (Forever) lists as dropping it lives in a dungeon or raid: for the Dungeons view (to-do C4)."""
    from . import gamedata
    q = engine.q
    npcs = ((q.items.get(iid) if q else None) or {}).get('npcDrops') or []
    if not npcs or ((q.items.get(iid) or {}).get('objectDrops')):
        return False
    spawns = [(q.npcs.get(n) or {}).get('spawns') for n in npcs]
    zones = [int(z) for sp in spawns if isinstance(sp, dict) for z in sp]
    return bool(zones) and all(gamedata.is_instance(engine.gd, z) for z in zones)


def level_weight(level) -> float:
    """High levels first (the user, 2026-11-20: "start with reading high interest, high level items and mobs first"):
    level 60 counts in full, level 30 half, never under a fifth."""
    return max(0.2, min(float(level or 0), 60.0) / 60.0)


def mob_candidates(engine, opps, creatures: dict, best_use: dict, read_npcs: set[int]) -> list[dict]:
    """Open-world normal mobs whose own Wowhead Forever page isn't read, with what the WoW Classic loot table suggests
    an hour of them earns (today's prices, the market limit, their kill speed) beyond what Forever data shows now.
    The Classic table only picks what to read; it never sets a value in a row."""
    from . import gamedata
    q, gd = engine.q, engine.gd
    level = int(engine.s.get('level', 1) or 1)
    per_hour = float(engine.s.get('kills_per_hour', 60) or 60)
    from .engine import RARE_PER_HOUR
    # steady drops only (the user, 2026-11-28: "consistent farms, not extremely low drops"): a drop the Classic table
    # gives less than once an hour doesn't make a farm, so it doesn't pick a page either
    shown = {o.detail.get('npc'): (o.detail.get('steady_gph') if o.detail.get('steady_gph') is not None else (o.gph or 0))
             for o in opps if o.kind == 'mob_spot'}
    out = []
    for sid, c in (creatures or {}).items():
        npc = int(sid)
        qn = (q.npcs.get(npc) if q else None) or {}
        if npc in read_npcs or not qn or qn.get('friendlyToFaction') or spawn_points(qn) < MIN_SPAWNS:
            continue                      # read, friendly, or a rare or named mob (one or two spawn points)
        spawns = qn.get('spawns') if isinstance(qn.get('spawns'), dict) else {}
        zones = [int(z) for z in spawns if not gamedata.is_instance(gd, int(z))]
        if not zones:
            continue                      # not in Forever's open world (dungeons: to-do C4)
        hi = int(c['levels'][1] or 0)
        pace, _ = engine.kill_pace(per_hour, max(level, hi - 3), hi)
        parts = []
        for i, n in c['items'].items():
            if int(i) in gd.items and n * pace >= RARE_PER_HOUR:
                parts.append((n * engine.loot_worth(int(i), best_use, n, pace), int(i)))
        per_kill = (c.get('coins') or 0) + sum(v for v, _ in parts)
        guess = per_kill * pace
        missing = guess - shown.get(npc, 0)
        if missing <= 0:
            continue
        top = [engine.name(i) for _, i in sorted(parts, reverse=True)[:2]]
        out.append({'kind': 'npc', 'id': npc, 'name': qn.get('name') or c['name'], 'level': hi,
                    'gold': int(missing), 'score': missing * level_weight(hi),
                    'url': f'https://www.wowhead.com/forever/npc={npc}',
                    'text': (f"{qn.get('name') or c['name']} (npc {npc}, level {c['levels'][0]}-{hi}, "
                             f"{gd.zones.get(zones[0], 'zone ' + str(zones[0]))}): the WoW Classic table suggests about "
                             f"{guess / 10000:,.1f}g an hour from steady drops{' (mostly ' + ', '.join(top) + ')' if top else ''}; "
                             f"Forever data shows {shown.get(npc, 0) / 10000:,.1f}g now")})
    return out


def reading_queue(engine, opps, creatures: dict, best_use: dict, read_npcs: set[int], item_queue: list[dict],
                  share: float, n: int = QUEUE_LEN) -> list[dict]:
    """What to read next on Wowhead Forever, items and mobs together, by gold a day the app can't see yet x a level
    weight: a mob, the gold an hour its Classic table suggests beyond Forever data (an hour a day); an item without
    Forever source data, your share of what the region trades of it a day."""
    rows = mob_candidates(engine, opps, creatures, best_use, read_npcs)
    gd = engine.gd
    for r in item_queue or []:
        if dungeon_only(engine, r['item_id']):
            continue                      # dungeon gear and patterns: the Dungeons view (to-do C4)
        it = gd.items.get(r['item_id'])
        lv = getattr(it, 'item_level', 0) if it else 0
        gold = r['market'] * share
        rows.append({'kind': 'item', 'id': r['item_id'], 'name': r['name'], 'level': lv, 'gold': int(gold),
                     'score': gold * level_weight(lv), 'url': r['url'], 'text': describe(r)})
    rows.sort(key=lambda r: -r['score'])
    return rows[:n]


def queue_check(queue: list[dict], kills: float) -> dict:
    """The Data health entry."""
    mobs = sum(1 for r in queue if r['kind'] == 'npc')
    return {'name': 'Wowhead reading queue', 'status': 'pass' if not queue else 'warn',
            'detail': (f"What to read next on Wowhead Forever (one page every 2 minutes, at most 20 a session), items "
                       f"and mobs together, by the gold a day the app can't see yet, high levels first (level 60 in full, "
                       f"level 30 half). A mob: what an hour of it ({kills:g} kills for a typical mob of your level, "
                       f"paced by its health) earns by the WoW Classic loot table at today's prices and market limits, "
                       f"from steady drops only (ones that come at least once an hour: a rare recipe or epic doesn't make "
                       f"a farm), beyond what Forever data shows now; its own page gives every drop, its coins and health. The "
                       f"Classic table only picks the order: it never sets a value. An item without Forever source data: "
                       f"your share of what the region trades of it a day; its page gives every source at once. Left "
                       f"out: rare and named mobs (under {MIN_SPAWNS} spawn points), items only dungeon mobs drop (the "
                       f"Dungeons view, to-do C4). {len(queue)} listed ({mobs} mobs)."),
            'examples': [f"{'Mob' if r['kind'] == 'npc' else 'Item'}: {r['text']} (score {r['score'] / 10000:,.1f}) "
                         f"{r['url']}" for r in queue[:40]]}
