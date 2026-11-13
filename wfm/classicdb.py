"""Classic fishing tables from the open cMaNGOS classic-db (GPL-3.0), as a baseline for WoW: Forever.

The full dump (~13 MB .sql.gz) is downloaded once on request. Only the fishing tables are kept, in a small
JSON cache. Classic is not Forever: the engine blends this baseline with your own logged catches and flags
zones where they disagree.

Server rules (cMaNGOS mangos-classic, GameObject.cpp / LootMgr.cpp):
- loot comes from the subzone's table if it has one, else from the zone's;
- the zone skill comes from the subzone if listed, else the zone;
- a cast succeeds when skill >= zone skill and a 1-100 roll <= skill - zone skill + 5;
- ungrouped loot entries roll independently; in a group, explicitly-chanced entries are tried first and
  equal-chanced (chance 0) entries share what's left; negative mincount = reference to another table.

Usage:  python -m wfm.classicdb --update    (checks GitHub, downloads a newer dump if there is one, re-extracts)
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .paths import DATA

REPO = 'cmangos/classic-db'
LIST_URL = f'https://api.github.com/repos/{REPO}/contents/Full_DB'
RAW_URL = f'https://raw.githubusercontent.com/{REPO}/master/'
USER_AGENT = 'WoWForeverMoney/0.1 (personal gold tool)'
ROOT = DATA / 'classicdb'
CACHE = ROOT / 'fishing.json'
EXTRACTOR_VERSION = 3           # bump to re-extract cached data when this file's logic changes

LOOT_COLS = ['entry', 'item', 'chance', 'group', 'minref', 'maxcount', 'condition', 'comment']
COLUMNS = {
    'fishing_loot_template': LOOT_COLS,
    'reference_loot_template': LOOT_COLS,
    'gameobject_loot_template': LOOT_COLS,
    'skill_fishing_base_level': ['entry', 'skill'],
    'conditions': ['id', 'type', 'value1', 'value2', 'value3', 'value4', 'flags', 'comment'],
    'gameobject_template': ['entry', 'type', 'displayId', 'name', 'faction', 'flags', 'ExtraFlags', 'size']
                           + [f'data{i}' for i in range(24)] + ['CustomData1', 'mingold', 'maxgold', 'StringId', 'ScriptName'],
    'game_event': ['entry', 'schedule_type', 'occurence', 'length', 'holiday', 'linkedTo', 'description'],
    'game_event_time': ['entry', 'start_time', 'end_time'],
}
KEYS = {'skill_fishing_base_level': ('entry',), 'conditions': ('id',), 'gameobject_template': ('entry',),
        'game_event': ('entry',), 'game_event_time': ('entry',)}
CONDITION_EVENT = 12     # conditions.type: game event active (value1 = event id)
FISHING_HOLE = 25        # gameobject type: fishing pool / school; data1 = loot id, data2/data3 = catches per pool
SQL_NAMES = {'ChanceOrQuestChance': 'chance', 'groupid': 'group', 'mincountOrRef': 'minref', 'condition_id': 'condition',
             'comments': 'comment', 'condition_entry': 'id'}

_VAL = re.compile(r"\s*(?:'((?:[^'\\]|\\.)*)'|(NULL)|(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?))\s*")
_ESC = {'0': '\0', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a'}
_INSERT = re.compile(r'\s*(?:INSERT|REPLACE)\s+(?:IGNORE\s+)?INTO\s+`?(\w+)`?\s*(\(([^)]*)\))?\s*VALUES', re.I)
_DELETE = re.compile(r'\s*DELETE\s+FROM\s+`?(\w+)`?\s*(?:WHERE\s+(.*?))?;', re.I | re.S)


def _unescape(s: str) -> str:
    return re.sub(r'\\(.)', lambda m: _ESC.get(m.group(1), m.group(1)), s)


def parse_tuples(text: str, pos: int = 0):
    """Yield every (v1, v2, ...) tuple of a MySQL VALUES list starting at pos, until ';' or end of text."""
    i, n = pos, len(text)
    while i < n:
        c = text[i]
        if c == '(':
            row, i = [], i + 1
            while True:
                m = _VAL.match(text, i)
                if not m:
                    raise ValueError(f'unreadable SQL value near {text[i:i + 60]!r}')
                s, null, num = m.groups()
                row.append(_unescape(s) if s is not None else None if null else
                           (float(num) if any(ch in num for ch in '.eE') else int(num)))
                i = m.end()
                if i < n and text[i] == ',':
                    i += 1
                elif i < n and text[i] == ')':
                    i += 1
                    break
                else:
                    raise ValueError(f'unexpected SQL near {text[i:i + 60]!r}')
            yield row
        elif c == ';':
            return
        else:
            i += 1


def _statements(text: str):
    """Split SQL text into statements (outside quotes), dropping -- and /* */ comments."""
    out, buf, i, n, q = [], [], 0, len(text), None
    while i < n:
        c = text[i]
        if q:
            buf.append(c)
            if c == '\\' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c if c != '`' else None
            buf.append(c)
        elif text.startswith('--', i) or c == '#':
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        elif c == ';':
            buf.append(c)
            out.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    if ''.join(buf).strip():
        out.append(''.join(buf).strip())
    return out


@dataclass
class ClassicFishing:
    loot: dict[int, list[dict]] = field(default_factory=dict)        # area id -> fishing loot entries
    refs: dict[int, list[dict]] = field(default_factory=dict)        # reference id -> entries (only those fishing uses)
    skill: dict[int, int] = field(default_factory=dict)              # area id -> base skill
    conditions: dict[int, dict] = field(default_factory=dict)
    pools: dict[int, dict] = field(default_factory=dict)            # fishing pool object -> name, loot, restock
    events: dict[int, dict] = field(default_factory=dict)           # seasonal game events used by conditions
    source: dict = field(default_factory=dict)                       # file, sha, size, extracted_at, updates applied
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {'loot': self.loot, 'refs': self.refs, 'skill': self.skill, 'conditions': self.conditions,
                'pools': self.pools, 'events': self.events, 'source': self.source, 'warnings': self.warnings}

    @classmethod
    def from_json(cls, d: dict) -> 'ClassicFishing':
        ik = lambda m: {int(k): v for k, v in (m or {}).items()}
        return cls(loot=ik(d.get('loot')), refs=ik(d.get('refs')), skill=ik(d.get('skill')),
                   conditions=ik(d.get('conditions')), pools=ik(d.get('pools')), events=ik(d.get('events')),
                   source=d.get('source') or {}, warnings=d.get('warnings') or [])

    def event_status(self, event_id: int, now: float | None = None) -> tuple[bool | None, float]:
        """(active right now per the Classic schedule, share of the time it's active). None if unknown."""
        ev = self.events.get(event_id)
        if not ev or not ev.get('occurence'):
            return None, 0.5
        share = min(1.0, ev['length'] / ev['occurence'])
        try:
            start = time.mktime(time.strptime(str(ev['start']), '%Y-%m-%d %H:%M:%S'))
        except (TypeError, ValueError):
            return None, share
        now = time.time() if now is None else now
        minutes = (now - start) / 60
        return (minutes >= 0 and minutes % ev['occurence'] < ev['length']), share


def _row_dict(table: str, cols: list[str] | None, row: list) -> dict:
    names = [SQL_NAMES.get(c, c) for c in cols] if cols else COLUMNS[table]
    return dict(zip(names, row))


def extract(dump: Path, updates: list[Path] = ()) -> ClassicFishing:
    """Read the fishing tables out of a full dump (.sql or .sql.gz), then apply update scripts in order."""
    tables: dict[str, dict] = {t: {} for t in COLUMNS}

    def key(t, r):
        return tuple(r[k] for k in KEYS.get(t, ('entry', 'item')))

    opener = gzip.open if str(dump).endswith('.gz') else open
    with opener(dump, 'rt', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('INSERT'):
                continue
            m = _INSERT.match(line)
            if not m or m.group(1) not in COLUMNS:
                continue
            t, cols = m.group(1), [c.strip(' `') for c in m.group(3).split(',')] if m.group(2) else None
            for row in parse_tuples(line, m.end()):
                r = _row_dict(t, cols, row)
                if t == 'gameobject_template' and r.get('type') != FISHING_HOLE:
                    continue
                tables[t][key(t, r)] = r

    warnings, applied = [], []
    for up in updates:
        text = Path(up).read_text(encoding='utf-8', errors='replace')
        touched = False
        for st in _statements(text):
            low = st.lower()
            hit = next((t for t in COLUMNS if re.search(r'\b' + t + r'\b', low)), None)
            if not hit:
                continue
            touched = True
            m = _INSERT.match(st)
            if m and m.group(1) in COLUMNS:
                t = m.group(1)
                cols = [c.strip(' `') for c in m.group(3).split(',')] if m.group(2) else None
                for row in parse_tuples(st, m.end()):
                    r = _row_dict(t, cols, row)
                    tables[t][key(t, r)] = r
                continue
            d = _DELETE.match(st)
            if d and d.group(1) in COLUMNS and d.group(2):
                t, where = d.group(1), d.group(2)
                w = re.fullmatch(r"\s*`?(\w+)`?\s*(?:IN\s*\(([^)]*)\)|=\s*(-?\d+))\s*", where, re.I)
                if w:
                    col = SQL_NAMES.get(w.group(1), w.group(1))
                    vals = {int(v) for v in re.findall(r'-?\d+', w.group(2) or w.group(3))}
                    tables[t] = {k: r for k, r in tables[t].items() if r.get(col) not in vals}
                    continue
            warnings.append(f'{Path(up).name}: could not apply "{st[:80]}..."')
        if touched:
            applied.append(Path(up).name)

    cf = ClassicFishing(warnings=warnings)
    for r in tables['skill_fishing_base_level'].values():
        cf.skill[int(r['entry'])] = int(r['skill'])
    for r in tables['fishing_loot_template'].values():
        cf.loot.setdefault(int(r['entry']), []).append(_slim(r))
    go_loot: dict[int, list[dict]] = {}
    for r in tables['gameobject_loot_template'].values():
        go_loot.setdefault(int(r['entry']), []).append(_slim(r))
    for r in tables['gameobject_template'].values():
        loot_id = int(r['data1'] or 0)
        # TBC-only pools have no loot here; objects with no catches per pool (placeholders) are skipped too
        if loot_id and loot_id in go_loot and int(r['data3'] or 0) > 0:
            cf.pools[int(r['entry'])] = {'name': r['name'], 'loot_id': loot_id, 'loot': go_loot[loot_id],
                                         'restock': [int(r['data2'] or 0), int(r['data3'] or 0)]}
    all_refs: dict[int, list[dict]] = {}
    for r in tables['reference_loot_template'].values():
        all_refs.setdefault(int(r['entry']), []).append(_slim(r))
    # keep only the reference tables fishing reaches (directly or through other references)
    tables_used = list(cf.loot.values()) + [p['loot'] for p in cf.pools.values()]
    todo = [-e['minref'] for rows in tables_used for e in rows if e['minref'] < 0]
    while todo:
        ref = todo.pop()
        if ref in cf.refs or ref not in all_refs:
            continue
        cf.refs[ref] = all_refs[ref]
        todo += [-e['minref'] for e in all_refs[ref] if e['minref'] < 0]
    used = {e['condition'] for rows in tables_used + list(cf.refs.values()) for e in rows if e['condition']}
    for r in tables['conditions'].values():
        if int(r['id']) in used:
            cf.conditions[int(r['id'])] = {'type': r['type'], 'value1': r['value1'], 'comment': r.get('comment') or ''}
    starts = {int(r['entry']): r['start_time'] for r in tables['game_event_time'].values()}
    for c in cf.conditions.values():
        ev = tables['game_event'].get((c['value1'],)) if c['type'] == CONDITION_EVENT else None
        if ev:
            cf.events[int(ev['entry'])] = {'name': ev['description'] or '', 'occurence': int(ev['occurence']),
                                           'length': int(ev['length']), 'start': starts.get(int(ev['entry']))}
    cf.source = {'file': Path(dump).name, 'updates': applied, 'extracted_at': int(time.time()),
                 'extractor': EXTRACTOR_VERSION}
    return cf


def _slim(r: dict) -> dict:
    return {'item': int(r['item']), 'chance': float(r['chance']), 'group': int(r['group']), 'minref': int(r['minref']),
            'maxcount': int(r['maxcount']), 'condition': int(r['condition'] or 0), 'comment': r.get('comment') or ''}


# ---------- expected catch ----------
def expected_items(entries: list[dict], refs: dict[int, list[dict]], _depth: int = 0) -> dict[int, dict]:
    """Expected count of every item per successful loot roll of this table.

    Returns {item: {'count': expected count, 'quest': bool, 'conditions': set of condition ids}}.
    Quest-only items (negative chance) are returned with their chance but marked quest=True.
    """
    out: dict[int, dict] = {}
    if _depth > 8:
        return out

    def add(item, count, quest, conds):
        o = out.setdefault(item, {'count': 0.0, 'quest': False, 'conditions': set()})
        o['count'] += count
        o['quest'] = o['quest'] or quest
        o['conditions'] |= conds

    def take(e, p):
        if p <= 0:
            return
        own = {e['condition']} if e['condition'] else set()
        if e['minref'] < 0:
            sub = expected_items(refs.get(-e['minref'], []), refs, _depth + 1)
            for it, o in sub.items():
                add(it, o['count'] * p * max(1, e['maxcount']), o['quest'], o['conditions'] | own)
        else:
            lo = max(1, e['minref'])
            add(e['item'], p * (lo + max(lo, e['maxcount'])) / 2, e['chance'] < 0, own)

    groups: dict[int, list[dict]] = {}
    for e in entries:
        if e['group']:
            groups.setdefault(e['group'], []).append(e)
            continue
        ch = abs(e['chance'])
        take(e, 1.0 if ch >= 100 else ch / 100)
    for rows in groups.values():
        explicit = [e for e in rows if e['chance'] != 0]
        equal = [e for e in rows if e['chance'] == 0]
        total = sum(min(100.0, abs(e['chance'])) for e in explicit)
        scale = 100.0 / total if total > 100 else 1.0      # over-full groups: later entries get cut, spread it evenly
        for e in explicit:
            take(e, min(100.0, abs(e['chance'])) * scale / 100)
        left = max(0.0, 1 - total / 100)
        for e in equal:
            take(e, left / len(equal))
    return out


def success_chance(skill: int, zone_skill: int) -> float:
    """Classic: chance a cast catches something (the rest 'got away')."""
    if skill < zone_skill:
        return 0.0
    return max(0.0, min(100, skill - zone_skill + 5)) / 100


# ---------- cache, download, update ----------
def load_cached() -> ClassicFishing | None:
    if not CACHE.exists():
        return None
    data = json.loads(CACHE.read_text(encoding='utf-8'))
    cf = ClassicFishing.from_json(data)
    if cf.source.get('extractor') != EXTRACTOR_VERSION:
        dump = latest_dump()
        if dump:
            cf = rebuild(dump, cf.source)
    return cf


def latest_dump() -> Path | None:
    files = sorted((ROOT / 'download').glob('*.sql.gz'))
    return files[-1] if files else None


def update_files() -> list[Path]:
    return sorted((ROOT / 'updates').glob('*.sql'))


def rebuild(dump: Path, source: dict | None = None) -> ClassicFishing:
    cf = extract(dump, update_files())
    cf.source.update({k: v for k, v in (source or {}).items() if k in ('sha', 'size', 'downloaded_at')})
    cf.source['size'] = cf.source.get('size') or dump.stat().st_size
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix('.part')
    tmp.write_text(json.dumps(cf.to_json(), default=sorted), encoding='utf-8')
    tmp.replace(CACHE)
    return cf


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def remote_dump() -> dict | None:
    """The full-dump file currently on GitHub: {'name', 'sha', 'size', 'path'}."""
    for f in json.loads(_get(LIST_URL)):
        if f.get('name', '').endswith('.sql.gz'):
            return {k: f[k] for k in ('name', 'sha', 'size', 'path')}
    return None


CHECK_FILE = ROOT / 'check.json'


def last_check() -> dict:
    try:
        return json.loads(CHECK_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_check(remote: dict | None):
    ROOT.mkdir(parents=True, exist_ok=True)
    prev = last_check()
    CHECK_FILE.write_text(json.dumps({'checked': int(time.time()), 'remote': remote or prev.get('remote')}),
                          encoding='utf-8')


def update(log=print) -> ClassicFishing:
    """Download the dump if GitHub has a different one than we extracted, then re-extract."""
    remote = remote_dump()
    save_check(remote)
    cached = load_cached()
    if not remote:
        raise RuntimeError('No .sql.gz found in the classic-db Full_DB folder.')
    if cached and cached.source.get('sha') == remote['sha']:
        log(f'Already up to date: {remote["name"]}')
        return cached
    dest_dir = ROOT / 'download'
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / remote['name']
    if not dest.exists() or dest.stat().st_size != remote['size']:
        log(f'Downloading {remote["name"]} ({remote["size"] / 1e6:.1f} MB) from github.com/{REPO}')
        body = _get(RAW_URL + remote['path'], timeout=600)
        if len(body) != remote['size']:
            raise RuntimeError(f'Download size {len(body)} does not match GitHub ({remote["size"]}).')
        tmp = dest.with_suffix('.part')
        tmp.write_bytes(body)
        tmp.replace(dest)
    cf = rebuild(dest, {'sha': remote['sha'], 'size': remote['size'], 'downloaded_at': int(time.time())})
    log(f'Extracted {len(cf.loot)} fishing areas, {len(cf.refs)} reference tables, {len(cf.skill)} zone skill levels.')
    return cf


if __name__ == '__main__':
    if '--update' in sys.argv:
        update()
    else:
        print(__doc__)
