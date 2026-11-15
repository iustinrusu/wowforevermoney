"""GatherLite's Forever node positions (the addon, installed by the user through CurseForge): where herbs, ore,
chests and fishing pools spawn, per zone.

The addon's file plugins/database/data/forever.lua is generated from Wowhead's Forever map data
(`addon.predefined[objectID][uiMapID] = {x, y, x, y, ...}`, normalized map coordinates). Map ids become zones through
the game's UiMap and UiMapAssignment tables (wago.tools, same build as the client): a zone map has one area, the zone
id QuestieDB also uses. Points closer than MERGE on the map are one node recorded a few times (the file has clusters
such as 0.514/0.423, 0.514/0.425, 0.515/0.423), so they count once.

Used for: a per-zone comparison with QuestieDB's spawns on Data health, and where fishing pools spawn (QuestieDB has no
spawns for most pools). Re-read when the addon's file changes (it updates often).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

MERGE = 0.005            # points closer than this (normalized map units, ~1/200 of the map) are one node

_OBJ = re.compile(r'^(?: {4}|\t)\[(\d+)\] = \{\s*$', re.M)               # an object's block
_MAP = re.compile(r'^(?: {8}|\t\t)\[(\d+)\] = \{([^}]*)\}', re.M)        # a map's points inside it
_NUM = re.compile(r'-?\d+(?:\.\d+)?')


def data_file(addons_dir: Path | None) -> Path | None:
    p = addons_dir / 'GatherLite' / 'plugins' / 'database' / 'data' / 'forever.lua' if addons_dir else None
    return p if p and p.exists() else None


def parse(text: str) -> dict[int, dict[int, list[tuple[float, float]]]]:
    """object id -> map id -> [(x, y), ...] as the file lists them (object blocks at one indent, map blocks at two)."""
    out: dict[int, dict[int, list]] = {}
    starts = [(m.start(), int(m.group(1))) for m in _OBJ.finditer(text)]
    pos = 0
    for m in _MAP.finditer(text):
        while pos + 1 < len(starts) and starts[pos + 1][0] < m.start():
            pos += 1
        if not starts or starts[pos][0] > m.start():
            continue
        nums = [float(n) for n in _NUM.findall(m.group(2))]
        out.setdefault(starts[pos][1], {})[int(m.group(1))] = list(zip(nums[0::2], nums[1::2]))
    return out


def merge_points(points: list[tuple[float, float]], merge: float = MERGE) -> int:
    """How many distinct nodes: points within `merge` of one already counted are the same node."""
    kept: list[tuple[float, float]] = []
    cells: dict[tuple[int, int], list[int]] = {}
    for x, y in points:
        cx, cy = int(x / merge), int(y / merge)
        near = [k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in cells.get((cx + dx, cy + dy), ())]
        if any((kept[k][0] - x) ** 2 + (kept[k][1] - y) ** 2 <= merge * merge for k in near):
            continue
        cells.setdefault((cx, cy), []).append(len(kept))
        kept.append((x, y))
    return len(kept)


def map_zones(gamedata_dir: Path) -> dict[int, int]:
    """UiMap id -> zone (AreaTable id) from UiMapAssignment (the first assignment of each map)."""
    path = gamedata_dir / 'UiMapAssignment.csv'
    if not path.exists():
        return {}
    best: dict[int, tuple[int, int]] = {}
    with path.open(encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            try:
                um, order, area = int(r['UiMapID']), int(r['OrderIndex']), int(r['AreaID'])
            except (KeyError, ValueError):
                continue
            if area and (um not in best or order < best[um][0]):
                best[um] = (order, area)
    return {um: area for um, (_, area) in best.items()}


def nodes_by_zone(parsed: dict, zones: dict[int, int], merge: float = MERGE) -> dict[int, dict[int, int]]:
    """object id -> zone -> distinct nodes. Map ids without a zone are left out."""
    out: dict[int, dict[int, int]] = {}
    for obj, maps in parsed.items():
        for um, pts in maps.items():
            z = zones.get(um)
            if z:
                out.setdefault(obj, {})[z] = out.get(obj, {}).get(z, 0) + merge_points(pts, merge)
    return out


def load(addons_dir: Path | None, gamedata_dir: Path | None) -> dict:
    """{'nodes': object -> zone -> count, 'points': raw points, 'objects': n, 'file': path, 'unmapped': map ids}."""
    f = data_file(addons_dir)
    if not f or not gamedata_dir:
        return {}
    parsed = parse(f.read_text(encoding='utf-8', errors='replace'))
    zones = map_zones(gamedata_dir)
    unmapped = sorted({um for maps in parsed.values() for um in maps if um not in zones})
    return {'nodes': nodes_by_zone(parsed, zones), 'points': sum(len(p) for m in parsed.values() for p in m.values()),
            'objects': len(parsed), 'file': str(f), 'unmapped': unmapped}


def compare(gl: dict, questie_objects: dict, names=None) -> dict:
    """Per object: GatherLite's distinct nodes vs QuestieDB's spawns, in all and in zones only one of them has."""
    rows = []
    for obj, zones in (gl.get('nodes') or {}).items():
        ob = questie_objects.get(obj) or {}
        sp = ob.get('spawns') if isinstance(ob.get('spawns'), dict) else {}
        q = {int(z): len(c) for z, c in sp.items()}
        rows.append({'object': obj, 'name': ob.get('name') or (names(obj) if names else f'object {obj}'),
                     'gatherlite': sum(zones.values()), 'questie': sum(q.values()),
                     'zones_only_gatherlite': sorted(set(zones) - set(q)), 'zones_only_questie': sorted(set(q) - set(zones))})
    rows.sort(key=lambda r: -abs(r['gatherlite'] - r['questie']))
    return {'rows': rows, 'gatherlite': sum(r['gatherlite'] for r in rows), 'questie': sum(r['questie'] for r in rows),
            'only_gatherlite': [r for r in rows if not r['questie']]}
