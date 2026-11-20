"""WoW Classic mob loot (cMaNGOS classic-db 1.12): only a guide for which Wowhead Forever pages to read first.

Never Forever data, never a value in a row: the reading queue (coverage.reading_queue) uses it to guess which mobs
might earn more than the app can see yet, so their own Wowhead Forever pages get read first (the user, 2026-11-20:
"start with reading high interest, high level items and mobs first"). Built from the dump `classicdb` already
downloads; cached in data/classicdb/creatures.json: per normal (non-elite) mob its name, levels, type, health at its
highest level, average coins and the items a kill gives (expected count, rare ones under 1 in 2,000 left out).
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from . import classicdb
from .paths import DATA

CACHE = DATA / 'classicdb' / 'creatures.json'
VERSION = 1
MIN_COUNT = 0.0005          # items rarer than 1 in 2,000 kills are left out (the cache stays small)
CT = ('Entry Name SubName MinLevel MaxLevel ModelId1 ModelId2 ModelId3 ModelId4 Faction Scale Family CreatureType '
      'InhabitType RegenerateStats RacialLeader NpcFlags UnitFlags DynamicFlags ExtraFlags CreatureTypeFlags StaticFlags1 '
      'StaticFlags2 StaticFlags3 StaticFlags4 SpeedWalk SpeedRun Detection CallForHelp Pursuit Leash Timeout UnitClass Rank '
      'HealthMultiplier PowerMultiplier DamageMultiplier DamageVariance ArmorMultiplier ExperienceMultiplier MinLevelHealth '
      'MaxLevelHealth MinLevelMana MaxLevelMana MinMeleeDmg MaxMeleeDmg MinRangedDmg MaxRangedDmg Armor MeleeAttackPower '
      'RangedAttackPower MeleeBaseAttackTime RangedBaseAttackTime DamageSchool MinLootGold MaxLootGold LootId').split()


def build(dump: Path) -> dict:
    """{npc id: {'name', 'levels': [lo, hi], 'type', 'health', 'coins', 'items': {item: per kill}}} for normal mobs."""
    creatures, loot, refs = {}, {}, {}
    opener = gzip.open if str(dump).endswith('.gz') else open
    with opener(dump, 'rt', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('INSERT'):
                continue
            m = classicdb._INSERT.match(line)
            if not m:
                continue
            t = m.group(1)
            if t == 'creature_template':
                for row in classicdb.parse_tuples(line, m.end()):
                    r = dict(zip(CT, row))
                    if int(r.get('Rank') or 0) == 0:
                        creatures[int(r['Entry'])] = r
            elif t in ('creature_loot_template', 'reference_loot_template'):
                for row in classicdb.parse_tuples(line, m.end()):
                    r = dict(zip(classicdb.LOOT_COLS, row))
                    (loot if t == 'creature_loot_template' else refs).setdefault(int(r['entry']), []).append(classicdb._slim(r))
    out = {}
    for e, r in creatures.items():
        lo, hi = int(r['MinLevel'] or 0), int(r['MaxLevel'] or 0)
        coins = (int(r['MinLootGold'] or 0) + int(r['MaxLootGold'] or 0)) / 2
        lid = int(r['LootId'] or 0)
        exp = classicdb.expected_items(loot.get(lid, []), refs) if lid else {}
        items = {str(i): round(o['count'], 5) for i, o in exp.items()
                 if o['count'] >= MIN_COUNT and not o['quest'] and not o['conditions']}
        if hi < 10 or not (items or coins):
            continue
        out[str(e)] = {'name': r['Name'], 'levels': [lo, hi], 'type': int(r['CreatureType'] or 0),
                       'health': int(r['MaxLevelHealth'] or 0), 'coins': round(coins, 1), 'items': items}
    return out


def load_or_build(log=print) -> dict:
    """The cached table, rebuilt from the downloaded dump when missing or older than this code; {} without a dump."""
    dump = classicdb.latest_dump()
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text(encoding='utf-8'))
            if d.get('version') == VERSION and (not dump or d.get('dump') == dump.name):
                return d['mobs']
        except (OSError, ValueError, KeyError):
            pass
    if not dump:
        return {}
    log(f'Reading WoW Classic mob loot from {dump.name} (a guide for the Wowhead reading queue)')
    mobs = build(dump)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix('.part')
    tmp.write_text(json.dumps({'version': VERSION, 'dump': dump.name, 'mobs': mobs}), encoding='utf-8')
    tmp.replace(CACHE)
    return mobs
