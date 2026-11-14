"""Skinning spots from Wowhead Forever "Skinned from" counts (data/wowhead_forever_skinning.json).

For each mob: how often a skin gives each item (count / times skinned), its level range and zones. A zone's value
per skin is the average over the mobs you can skin there, weighted by how often each was skinned (a stand-in for
how common it is). Gold/hour = value per skin x skins per hour (measured from ForeverMoneyBridge, else a setting).
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import DATA

SNAPSHOT = DATA / 'wowhead_forever_skinning.json'
SOLID_SAMPLE = 500      # a zone with fewer Forever skins than this is a small sample
MEASURED_MINUTES = 10   # measured skinning pace needs 10+ minutes of logs
LEVEL_REACH = 3         # mobs up to 3 levels above you count as doable


def load(path: Path = SNAPSHOT) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def skill_needed(level: int) -> int:
    """Skinning skill a mob of this level needs (WoW Classic rule; Forever may differ)."""
    if level <= 10:
        return 1
    if level <= 20:
        return (level - 10) * 10
    return level * 5


def mobs(snapshot: dict) -> dict[int, dict]:
    """npc id -> name, levels, zones, times skinned, and the share of skins giving each item."""
    out: dict[int, dict] = {}
    for iid, item in (snapshot.get('items') or {}).items():
        for r in item.get('npcs', []):
            m = out.setdefault(r['npc'], {'npc': r['npc'], 'name': r['name'], 'min_level': r['min_level'],
                                          'max_level': r['max_level'], 'zones': r['zones'], 'skinned': 0, 'items': {}})
            m['skinned'] = max(m['skinned'], r['outof'])
            m['items'][int(iid)] = r['count'] / r['outof'] if r['outof'] else 0.0
    return out


def measured_pace(activity: dict) -> tuple[float | None, float]:
    """Skins per hour from ForeverMoneyBridge's skinning logs (all zones), and the minutes logged."""
    loots = seconds = 0.0
    for acts in (activity or {}).values():
        a = (acts or {}).get('skinning') or {}
        loots += float(a.get('loots') or 0)
        seconds += float(a.get('seconds') or 0)
    minutes = seconds / 60
    if minutes < MEASURED_MINUTES or loots <= 0:
        return None, minutes
    return loots / (seconds / 3600), minutes


def spots(mob_table: dict[int, dict], value_of, zone_name, skill: int | None, level: int) -> list[dict]:
    """One spot per zone: the mobs there, value per skin over the ones you can skin, and what limits you."""
    by_zone: dict[int, list] = {}
    for m in mob_table.values():
        zone = next((z for z in m['zones'] if z > 0), None)
        if zone is None:
            continue
        per_skin = sum(share * value_of(iid) for iid, share in m['items'].items())
        need = skill_needed(m['max_level'])
        known = bool(m['max_level'])          # a level Wowhead and Questie don't give: not counted as doable
        by_zone.setdefault(zone, []).append({**m, 'value': int(per_skin), 'skill_needed': need,
                                             'can_skin': known and skill is not None and skill >= need,
                                             'can_kill': known and m['max_level'] <= level + LEVEL_REACH})
    out = []
    for zone, ms in by_zone.items():
        ms.sort(key=lambda m: -m['value'])
        ok = [m for m in ms if m['can_skin'] and m['can_kill']]
        use = ok or ms
        weight = sum(m['skinned'] for m in use) or 1
        value = sum(m['value'] * m['skinned'] for m in use) / weight
        out.append({'zone_id': zone, 'zone': zone_name(zone), 'value': int(value), 'mobs': ms, 'doable': bool(ok),
                    'skins': sum(m['skinned'] for m in ms),
                    'min_level': min((m['min_level'] for m in ms if m['max_level']), default=0),
                    'max_level': max(m['max_level'] for m in ms),
                    'skill_needed': min((m['skill_needed'] for m in ms if m['max_level']), default=1)})
    return out
