"""Read the QuestieDB "baked" database that ships inside QuestieDB_Forever.toc.

Every entity is stored as TOC metadata lines:
  ## X-<Prefix><id>-S: <base64 CBOR scalar row>        (map: field index -> value, 'p' = table presence mask)
  ## X-<Prefix><id>-<field>: <base64 CBOR table value>
  ## X-<Prefix>IDS: <base64 zlib/deflate CBOR id list>
Values that start with "~N~" are split into N parts stored under <key>-1 .. <key>-N.
"""
from __future__ import annotations

import base64
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import cbor2

ITEM_FIELDS = ['name', 'npcDrops', 'objectDrops', 'itemDrops', 'startQuest', 'questRewards', 'flags',
               'foodType', 'itemLevel', 'requiredLevel', 'ammoType', 'class', 'subClass', 'vendors',
               'relatedQuests', 'teachesSpell']
NPC_FIELDS = ['name', 'minLevelHealth', 'maxLevelHealth', 'minLevel', 'maxLevel', 'rank', 'spawns',
              'waypoints', 'zoneID', 'questStarts', 'questEnds', 'factionID', 'friendlyToFaction',
              'subName', 'npcFlags']
OBJECT_FIELDS = ['name', 'questStarts', 'questEnds', 'spawns', 'zoneID', 'factionID', 'waypoints']
# quests: only the fields the app reads (name, who starts it, the levels, the profession skill it asks for), so the
# 35,000 quests decode quickly; the others are skipped (2026-11-19: the Artisan Cooking and First Aid quests)
QUEST_FIELDS = ['name', 'startedBy', 'finishedBy', 'requiredLevel', 'questLevel'] + [None] * 12 + ['requiredSkill']

_LINE = re.compile(r'^## (X-[^:]+): ?(.*)$')


def _b64(value: str) -> bytes:
    return base64.b64decode(value + '=' * (-len(value) % 4))


def _decompress(data: bytes) -> bytes:
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 32):
        try:
            return zlib.decompress(data, wbits)
        except zlib.error:
            continue
    return data


def _lua_table(value):
    """CBOR maps keyed 1..n are Lua arrays; turn them into Python lists."""
    if isinstance(value, dict):
        keys = list(value.keys())
        if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
            return [_lua_table(value[k]) for k in range(1, len(keys) + 1)]
        return {k: _lua_table(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_lua_table(v) for v in value]
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value


@dataclass
class QuestieDB:
    items: dict[int, dict] = field(default_factory=dict)
    npcs: dict[int, dict] = field(default_factory=dict)
    objects: dict[int, dict] = field(default_factory=dict)
    quests: dict[int, dict] = field(default_factory=dict)       # name, startedBy, requiredLevel, requiredSkill


def _read_store(toc: Path) -> dict[str, str]:
    store: dict[str, str] = {}
    with open(toc, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('## X-'):
                continue
            m = _LINE.match(line.rstrip('\r\n'))
            if m:
                store[m.group(1)] = m.group(2)
    return store


def _get(store: dict[str, str], key: str) -> str | None:
    value = store.get(key)
    if value is None or not value.startswith('~'):
        return value
    m = re.fullmatch(r'~(\d+)~', value)
    if not m:
        return value
    return ''.join(store.get(f'{key}-{i}', '') for i in range(1, int(m.group(1)) + 1))


def _load_entities(store: dict[str, str], prefix: str, names: list[str]) -> dict[int, dict]:
    full = 'X-' + prefix
    by_id: dict[int, dict] = {}
    pat = re.compile(re.escape(full) + r'(\d+)-(S|\d+)$')
    for key in store:
        m = pat.match(key)
        if not m:
            continue
        ent_id, part = int(m.group(1)), m.group(2)
        if part != 'S' and not (int(part) <= len(names) and names[int(part) - 1]):
            continue                                   # a field the app doesn't read
        raw = _get(store, key)
        if not raw:
            continue
        try:
            decoded = _lua_table(cbor2.loads(_b64(raw)))
        except Exception:
            continue
        row = by_id.setdefault(ent_id, {'id': ent_id})
        if part == 'S':
            if isinstance(decoded, list):
                decoded = {i + 1: v for i, v in enumerate(decoded)}
            if isinstance(decoded, dict):
                for idx, val in decoded.items():
                    if isinstance(idx, int) and 1 <= idx <= len(names) and names[idx - 1]:
                        row.setdefault(names[idx - 1], val)
        else:
            idx = int(part)
            if 1 <= idx <= len(names):
                row[names[idx - 1]] = decoded
    return by_id


def load_questie(toc: Path) -> QuestieDB:
    store = _read_store(toc)
    return QuestieDB(
        items=_load_entities(store, 'Item-', ITEM_FIELDS),
        npcs=_load_entities(store, 'Npc-', NPC_FIELDS),
        objects=_load_entities(store, 'Object-', OBJECT_FIELDS),
        quests=_load_entities(store, 'Quest-', QUEST_FIELDS),
    )


def load_drop_rates(lua_file: Path) -> dict[int, dict[int, float]]:
    """Parse support/Forever/DropTables/classicItemDrops.lua -> {itemId: {npcId: percent}}."""
    rates: dict[int, dict[int, float]] = {}
    current = None
    item_re = re.compile(r'^\s*\[(\d+)\]\s*=\s*\{')
    rate_re = re.compile(r'^\s*\[(\d+)\]\s*=\s*([0-9.]+)\s*,?')
    with open(lua_file, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = item_re.match(line)
            if m:
                current = rates.setdefault(int(m.group(1)), {})
                continue
            m = rate_re.match(line)
            if m and current is not None:
                current[int(m.group(1))] = float(m.group(2))
    return rates
