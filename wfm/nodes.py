"""Herbalism and mining spots.

Where nodes are: QuestieDB's Forever object database (spawn points per zone). What a node gives: Wowhead Forever
pages read by hand (wowhead_items.py: an item's "Mined from"/"Gathered from" rows, or the node's own page), item by
item; whatever is not read yet comes from the WoW Classic 1.12 node loot tables (cMaNGOS classic-db), labelled, and
keeps the spot out of Top picks. Gathers per node (data4/data5) are Classic too. Skill per node: Classic table.
"""
from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path

from . import classicdb
from .paths import DATA

CACHE = DATA / 'classicdb' / 'nodes.json'
VERSION = 2
CHEST = 3                   # gameobject type: chest-like (herb and ore nodes are these); data1 = loot id,
                            # data4/data5 = min/max successful gathers before the node is used up
MEASURED_MINUTES = 10
# rare spawns: many spawn points but few active at once, so spawn points overstate them (kept out of the average)
RARE_NODES = {'Black Lotus'}
MIN_NODES = 5              # fewer node spawns than this in a zone is not a farming route

# Classic skill to gather each node (Forever may differ: labelled "Classic rule" wherever it is used)
HERB_SKILL = {'Peacebloom': 1, 'Silverleaf': 1, 'Bloodthistle': 1, 'Earthroot': 15, 'Mageroyal': 50,
              'Briarthorn': 70, 'Stranglekelp': 85, 'Bruiseweed': 100, 'Wild Steelbloom': 115, 'Grave Moss': 120,
              'Kingsblood': 125, 'Liferoot': 150, 'Fadeleaf': 160, 'Goldthorn': 170, "Khadgar's Whisker": 185,
              'Wintersbite': 195, 'Firebloom': 205, 'Purple Lotus': 210, "Arthas' Tears": 220, 'Sungrass': 230,
              'Blindweed': 235, 'Ghost Mushroom': 245, 'Gromsblood': 250, 'Golden Sansam': 260, 'Dreamfoil': 270,
              'Mountain Silversage': 280, 'Plaguebloom': 285, 'Icecap': 290, 'Black Lotus': 300}
ORE_SKILL = {'Copper Vein': 1, 'Tin Vein': 65, 'Incendicite Mineral Vein': 65, 'Silver Vein': 75,
             'Lesser Bloodstone Deposit': 75, 'Iron Deposit': 125, 'Indurium Mineral Vein': 150, 'Gold Vein': 155,
             'Mithril Deposit': 175, 'Truesilver Deposit': 230, 'Dark Iron Deposit': 230, 'Small Thorium Vein': 245,
             'Rich Thorium Vein': 275, 'Hakkari Thorium Vein': 275}


def node_kind(name: str, herb_names: set[str]) -> str | None:
    base = re.sub(r'^Ooze Covered ', '', name)
    if base in ORE_SKILL or base.endswith((' Vein', ' Deposit')):
        return 'mining'
    if base in HERB_SKILL or base in herb_names:
        return 'herbalism'
    return None


def node_skill(name: str) -> int | None:
    base = re.sub(r'^Ooze Covered ', '', name)
    return HERB_SKILL.get(base, ORE_SKILL.get(base))


def extract(dump: Path, object_ids: set[int]) -> dict:
    """Node loot (per object id) from the Classic dump: {'nodes': {id: {name, loot}}, 'refs': {ref: rows}}."""
    want = {'gameobject_template', 'gameobject_loot_template', 'reference_loot_template'}
    tables: dict[str, list] = {t: [] for t in want}
    opener = gzip.open if str(dump).endswith('.gz') else open
    with opener(dump, 'rt', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('INSERT'):
                continue
            m = classicdb._INSERT.match(line)
            if not m or m.group(1) not in want:
                continue
            t = m.group(1)
            cols = [c.strip(' `') for c in m.group(3).split(',')] if m.group(2) else None
            for row in classicdb.parse_tuples(line, m.end()):
                r = classicdb._row_dict(t, cols, row)
                if t == 'gameobject_template' and (int(r.get('type') or 0) != CHEST or int(r['entry']) not in object_ids):
                    continue
                tables[t].append(r)
    loot: dict[int, list] = {}
    for r in tables['gameobject_loot_template']:
        loot.setdefault(int(r['entry']), []).append(classicdb._slim(r))
    refs_all: dict[int, list] = {}
    for r in tables['reference_loot_template']:
        refs_all.setdefault(int(r['entry']), []).append(classicdb._slim(r))
    nodes = {}
    for r in tables['gameobject_template']:
        lid = int(r.get('data1') or 0)
        if lid in loot:
            lo, hi = int(r.get('data4') or 0), int(r.get('data5') or 0)
            nodes[int(r['entry'])] = {'name': r['name'], 'loot': loot[lid],
                                      'uses': (lo + hi) / 2 if hi >= lo > 0 else 1.0}
    refs: dict[int, list] = {}
    todo = [-e['minref'] for n in nodes.values() for e in n['loot'] if e['minref'] < 0]
    while todo:
        ref = todo.pop()
        if ref in refs or ref not in refs_all:
            continue
        refs[ref] = refs_all[ref]
        todo += [-e['minref'] for e in refs_all[ref] if e['minref'] < 0]
    return {'nodes': nodes, 'refs': refs}


def load_or_build(object_ids: set[int], log=print) -> dict:
    """Cached node loot; rebuilt when the dump, the node list or this extractor changes."""
    dump = classicdb.latest_dump()
    if not dump:
        return {}
    key = {'version': VERSION, 'dump': dump.name, 'objects': len(object_ids)}
    try:
        cached = json.loads(CACHE.read_text(encoding='utf-8'))
        if cached.get('key') == key:
            return cached
    except (OSError, ValueError):
        pass
    log('Reading herb and ore node loot from the Classic database (once)')
    data = extract(dump, object_ids)
    data['key'], data['built_at'] = key, int(time.time())
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data)
    CACHE.write_text(text, encoding='utf-8')
    return json.loads(text)          # same shape (string keys) as a cached load


def per_node(node: dict, refs: dict) -> dict[int, float]:
    """Expected items per node, over all the gathers it allows (Classic loot x average gathers)."""
    rr = {int(k): v for k, v in refs.items()}
    uses = float(node.get('uses') or 1.0)
    return {i: o['count'] * uses for i, o in classicdb.expected_items(node['loot'], rr).items()
            if not o['quest'] and o['count'] > 0}


def combine(classic_items: dict[int, float], forever: dict | None, uses: float,
            main_item: int) -> tuple[dict[int, float], dict[int, str]]:
    """Items per node from both sources: Forever rates (Wowhead Forever, per gather) times the gathers a node allows,
    replacing Classic item by item; a node's own page read in full (`complete`) replaces the Classic table whole.
    Returns ({item: count per node}, {item: 'forever' | 'classic' | 'assumed'})."""
    fy = (forever or {}).get('items') or {}
    if forever and forever.get('complete'):
        return {i: q * uses for i, q in fy.items()}, {i: 'forever' for i in fy}
    items = dict(classic_items)
    src = {i: 'classic' for i in classic_items}
    for i, q in fy.items():
        items[i] = q * uses
        src[i] = 'forever'
    if not items:
        return {main_item: 1.0}, {main_item: 'assumed'}
    return items, src


def measured_pace(activity: dict, act: str) -> tuple[float | None, float]:
    """Nodes per hour from ForeverMoneyBridge's herbalism/mining logs (all zones) and the minutes logged."""
    loots = seconds = 0.0
    for acts in (activity or {}).values():
        a = (acts or {}).get(act) or {}
        loots += float(a.get('loots') or 0)
        seconds += float(a.get('seconds') or 0)
    if seconds / 60 < MEASURED_MINUTES or loots <= 0:
        return None, seconds / 60
    return loots / (seconds / 3600), seconds / 60


def spots(nodes: list[dict], zone_name, skill: int | None) -> list[dict]:
    """Group nodes ({id, name, kind, skill, value, zones: {zone: count}}) into one spot per zone and profession."""
    by: dict[tuple[str, int], list] = {}
    for n in nodes:
        for zone, count in n['zones'].items():
            if count > 0 and zone > 0:
                by.setdefault((n['kind'], zone), []).append({**n, 'count': count})
    out = []
    for (kind, zone), ns in by.items():
        if sum(n['count'] for n in ns) < MIN_NODES:
            continue          # a node or two is not a route
        for n in ns:
            n['can'] = skill is not None and (n['skill'] is None or skill >= n['skill'])
            n['rare'] = n['name'] in RARE_NODES
        common = [n for n in ns if not n['rare']] or ns
        usable = [n for n in common if n['can']] or common
        total = sum(n['count'] for n in usable) or 1
        value = sum(n['value'] * n['count'] for n in usable) / total
        ns.sort(key=lambda n: -n['value'] * n['count'])
        known = [n['skill'] for n in ns if n['skill'] is not None]
        out.append({'kind': kind, 'zone_id': zone, 'zone': zone_name(zone), 'value': int(value), 'nodes': ns,
                    'node_count': sum(n['count'] for n in ns), 'doable': any(n['can'] for n in ns),
                    'skill_needed': min(known) if known else None})
    return out
