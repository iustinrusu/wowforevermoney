"""Wowhead Forever pages read by hand in the browser pane (data/wowhead_forever_items.json, tracked).

Three kinds of page, each a section of the file:

  items    An item page shows every way the item is obtained in WoW: Forever, one tab per way:
             Dropped by, Pick pocketed from, Skinned from (mobs)  count = loots that had the item, outof = times looted
             Mined from, Gathered from, Contained in (objects)    count = gathers/openings that gave it, outof = all
             Contained in (items)                                 outof = times that container was opened
             Fished in (zones)                                    Wowhead's own denominator: zone pages give catch rates
  objects  A node, chest or fishing pool: its Contains tab (rows = items, outof = times it was opened or gathered).
  npcs     A mob: its Drops / Skinning / Pickpocketing tabs (rows = items, outof = times it was looted). A vendor:
           its Sells tab (`sells`: every item it sells in Forever, the stock, -1 = unlimited, and the price; 2026-11-20,
           checklist A0). Once a vendor's page is read, what it sells comes from here, not QuestieDB: QuestieDB had
           Borya selling Pattern: Invoker's Cord (a Season of Discovery item) and Wizzle Brassbolts selling Copper
           Modulator, and neither does in Forever.

Rows Wowhead marks as Classic Era data are left out when a page is read (counted in `classic`), and so are rows
from fewer than MIN_LOOTED loots (counted in `small`): a handful of loots says nothing. Rates from fewer than SOLID
loots are flagged as a small sample wherever they are used. Coins are not on these pages.

The pages are read in the browser pane at the user's pace (docs/plans/material-coverage.md) and kept in that tab's
localStorage. The pane does not let a public site reach this PC (it blocks requests to 127.0.0.1), so a batch is
read out of the tab and saved with `python -m wfm.wowhead_items import <file.json>`, which checks every field.
Rows may come compact, as [id, count, outof, minlevel, maxlevel, zone, classification, stack].
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .paths import DATA

SNAPSHOT = DATA / 'wowhead_forever_items.json'
SECTIONS = ('items', 'objects', 'npcs')
PAGE_TYPE = {'item': 'items', 'object': 'objects', 'npc': 'npcs'}
MIN_LOOTED = 10          # rows from fewer loots than this are not kept
SOLID = 50               # a rate from fewer loots than this is a small sample
MAX_ROWS = 60            # rows kept per tab (most looted first)
# Wowhead's entity types (listview template.entityType) -> what a tab's rows are
ENTITY = {1: 'npc', 2: 'object', 3: 'item', 7: 'zone'}
# tab id -> kind of its rows, for item pages saved before the entity type was recorded
TAB_KIND = {'dropped-by': 'npc', 'skinned-from': 'npc', 'pick-pocketed-from': 'npc', 'contained-in-object': 'object',
            'mined-from-object': 'object', 'gathered-from-object': 'object', 'fished-in': 'zone',
            'contained-in-item': 'item', 'salvaged-from': 'item', 'disenchanted-from': 'item'}
ABOUT = ('Wowhead Forever pages read by hand in the browser pane. items: every source tab of an item (Dropped by, '
         'Skinned from, Mined/Gathered from, Contained in, Fished in, Pick pocketed from); objects: what a node, '
         'chest or pool contains; npcs: what a mob drops. Row: id (the mob, object, zone or item), count = loots that '
         'had the item, outof = times that source was looted or opened, stack = Wowhead\'s stack-size spread (%). '
         f'Classic Era rows and rows from fewer than {MIN_LOOTED} loots are left out (tab counts "classic" and '
         f'"small"); at most {MAX_ROWS} rows per tab, most looted first.')

_TAB_ID = re.compile(r'^[a-z][a-z-]{0,39}$')
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_KEY = re.compile(r'^(?:(item|object|npc)=)?(\d{1,8})$')
_ROW_INTS = ('id', 'count', 'outof', 'minlevel', 'maxlevel', 'classification')
_ROW_ORDER = ('id', 'count', 'outof', 'minlevel', 'maxlevel', 'location', 'classification', 'stack')


def load(path: Path | None = None) -> dict:
    try:
        path = path or SNAPSHOT
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _page_text(key: str, page: dict) -> str:
    tabs = []
    for tid, tab in sorted((page.get('tabs') or {}).items()):
        head = json.dumps({k: v for k, v in tab.items() if k != 'rows'}, ensure_ascii=False)[1:-1]
        rows = ',\n'.join('      ' + json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in tab['rows'])
        tabs.append(f'    {json.dumps(tid)}: {{{head}, "rows": [' + (f'\n{rows}\n    ]}}' if rows else ']}'))
    head = json.dumps({k: v for k, v in page.items() if k != 'tabs'}, ensure_ascii=False)[1:-1]
    return f'  {json.dumps(key)}: {{{head}, "tabs": {{\n' + ',\n'.join(tabs) + '\n  }}'


def save(data: dict, path: Path | None = None) -> None:
    """One page per block, rows one per line: readable diffs in git."""
    path = path or SNAPSHOT
    parts = ['"_about": ' + json.dumps(data.get('_about') or ABOUT, ensure_ascii=False)]
    for sec in SECTIONS:
        pages = data.get(sec) or {}
        body = ',\n'.join(_page_text(k, pages[k]) for k in sorted(pages, key=int))
        parts.append(f'"{sec}": {{' + (f'\n{body}\n}}' if body else '}'))
    text = '{\n' + ',\n'.join(parts) + '\n}\n'
    json.loads(text)                      # never write a file that does not parse
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def _int(v, lo=0, hi=10**9) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise ValueError(f'not a number: {v!r}')
    v = int(v)
    if not lo <= v <= hi:
        raise ValueError(f'out of range: {v}')
    return v


def _text(v, limit=200) -> str:
    if not isinstance(v, str):
        raise ValueError(f'not text: {v!r}')
    return v[:limit]


def clean_row(r) -> dict:
    if isinstance(r, list):                       # compact: [id, count, outof, minlevel, maxlevel, zone, class, stack]
        r = {k: v for k, v in zip(_ROW_ORDER, r[:len(_ROW_ORDER)]) if v is not None}
        if isinstance(r.get('location'), int):
            r['location'] = [r['location']]
    if not isinstance(r, dict):
        raise ValueError('a row must be an object or a list')
    out = {}
    for k in _ROW_INTS:
        if r.get(k) is not None:
            out[k] = _int(r[k], 0, 10**8)
    if 'id' not in out or 'count' not in out or 'outof' not in out:
        raise ValueError('a row needs id, count and outof')
    if r.get('name') is not None:
        out['name'] = _text(r['name'])
    loc = r.get('location')
    if loc:
        if not isinstance(loc, list):
            raise ValueError('location must be a list')
        out['location'] = [_int(z, -1000, 10**7) for z in loc[:20]]      # Wowhead: < 0 = several or special places
    st = r.get('stack')
    if st:
        if not isinstance(st, dict):
            raise ValueError('stack must be {size: percent}')
        stack = {}
        for s, p in list(st.items())[:30]:
            if str(s).isdigit() and 0 < int(s) <= 10**5 and isinstance(p, (int, float)) and not isinstance(p, bool) \
                    and 0 <= p <= 100:
                stack[str(int(s))] = round(float(p), 3)
        if stack:
            out['stack'] = stack
    return out


def _no_loots(r) -> bool:
    """A row with no loots behind it: outof 0, or a count below 0."""
    vals = r[1:3] if isinstance(r, list) else [r.get('count'), r.get('outof')] if isinstance(r, dict) else []
    nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return len(nums) == 2 and (nums[1] <= 0 or nums[0] < 0)


def clean_sell(r) -> dict:
    """A vendor's Sells row, compact [item, stock (-1 = unlimited, else how many a restock), price in copper, the
    reputation it needs, 1 if it also costs a currency or items, how many one purchase gives] or an object. A price of
    0 means not gold (Fizzlefuse's schematics cost Merchant's Favor, a currency). The price is for one purchase: Light
    Shot comes 200 at a time for 10c (2026-11-27, Jyn Stonehoof), so `stack` is kept when it is more than 1."""
    if isinstance(r, list):
        r = dict(zip(('id', 'stock', 'cost', 'standing', 'other_cost', 'stack'), r))
    if not isinstance(r, dict):
        raise ValueError('a sells row must be a list or an object')
    out = {'id': _int(r.get('id'), 1, 10**8)}
    if r.get('stock') is not None:
        out['stock'] = _int(r['stock'], -1, 10**6)
    if r.get('cost') is not None:
        out['cost'] = _int(r['cost'], 0, 10**10)
    if r.get('standing'):
        out['standing'] = _int(r['standing'], 0, 10)
    if r.get('other_cost'):
        out['other_cost'] = True
    if r.get('stack') is not None and _int(r['stack'], 1, 10**4) > 1:
        out['stack'] = int(r['stack'])
    return out


def clean_page(page: dict) -> dict:
    if not isinstance(page, dict) or not isinstance(page.get('tabs'), dict):
        raise ValueError('a page needs tabs')
    read = _text(page.get('read', ''), 10)
    if not _DATE.match(read):
        raise ValueError(f'bad read date {read!r}')
    url = _text(page.get('url', ''), 300)
    if url and not url.startswith('https://www.wowhead.com/forever/'):
        raise ValueError('not a Wowhead Forever page')
    out = {'name': _text(page.get('name', ''), 200), 'url': url, 'read': read, 'tabs': {}}
    for tid, tab in list(page['tabs'].items())[:40]:
        if not _TAB_ID.match(str(tid)) or not isinstance(tab, dict) or not isinstance(tab.get('rows'), list):
            raise ValueError(f'bad tab {tid!r}')
        kind = tab.get('kind') or TAB_KIND.get(tid)
        if kind not in ENTITY.values():
            continue                                   # comments, reagent-for, see-also...: not a source
        raw = tab['rows'][:500]
        # Wowhead's "no Forever loots recorded" marker: count -1 of 0 (Dark Iron Ore's Dropped by, 2026-11-27);
        # counted with the small samples, never a reason to throw the page away
        nodata = [r for r in raw if _no_loots(r)]
        rows = [clean_row(r) for r in raw if not _no_loots(r)]
        small = sum(1 for r in rows if r['outof'] < MIN_LOOTED) + len(nodata)
        rows = [r for r in rows if r['outof'] >= MIN_LOOTED]
        rows.sort(key=lambda r: (-r['outof'], -r['count'], r['id']))
        out['tabs'][tid] = {'kind': kind, 'total': _int(tab.get('total', len(tab['rows']))),
                            'classic': _int(tab.get('classic', 0)), 'small': _int(tab.get('small', 0)) + small,
                            'note': re.sub(r'<[^>]+>', '', _text(tab.get('note') or '', 300)),
                            'rows': rows[:MAX_ROWS]}
    if page.get('sells') is not None:
        if not isinstance(page['sells'], list):
            raise ValueError('sells must be a list')
        out['sells'] = [clean_sell(r) for r in page['sells'][:500]]
        out['sells_classic'] = _int(page.get('sells_classic') or 0)
    if page.get('facts') is not None:
        out['facts'] = clean_facts(page['facts'])
    return out


def clean_facts(f) -> dict:
    """An npc page's Quick Facts (2026-11-20, for kill speed): health and level as [low, high] numbers, the
    classification, and the box's text as read (short), so the numbers can be checked against it."""
    if not isinstance(f, dict):
        raise ValueError('facts must be an object')
    out = {}
    for k, top in (('health', 10**9), ('level', 100)):
        v = f.get(k)
        if v is None:
            continue
        if not isinstance(v, list) or not 1 <= len(v) <= 2:
            raise ValueError(f'{k} must be [low] or [low, high]')
        out[k] = [_int(x, 0, top) for x in v]
    if f.get('worth') is not None:
        out['worth'] = _int(f['worth'], 0, 10**8)        # Quick Facts "Worth": the coins a kill gives, in copper
    if f.get('classification') is not None:
        out['classification'] = _text(f['classification'], 40)
    if f.get('text') is not None:
        out['text'] = _text(f['text'], 600)
    return out


def merge(data: dict, pages: dict) -> tuple[dict, list[str], list[str]]:
    """Add pages to the snapshot. Keys: 'item=20520', 'object=1731', 'npc=448' (a bare number is an item page).
    A page replaces an older read of the same page, never a newer one; a page with any bad field is skipped whole.
    Returns (data, keys saved, problems)."""
    out = {'_about': (data or {}).get('_about') or ABOUT}
    for sec in SECTIONS:
        out[sec] = dict((data or {}).get(sec) or {})
    saved, problems = [], []
    if not isinstance(pages, dict):
        return out, [], ['expected {page key: page}']
    for key, page in list(pages.items())[:500]:
        m = _KEY.match(str(key))
        try:
            if not m:
                raise ValueError('bad page key')
            sec, pid = PAGE_TYPE[m.group(1) or 'item'], str(int(m.group(2)))
            clean = clean_page(page)
        except (ValueError, TypeError) as e:
            problems.append(f'{key}: {e}')
            continue
        old = out[sec].get(pid)
        if old and old.get('read', '') > clean['read']:
            problems.append(f'{key}: kept the newer read of {old["read"]}')
            continue
        out[sec][pid] = clean
        saved.append(f'{sec[:-1]}={pid}')
    return out, saved, problems


def vendor_lists(data: dict) -> dict[int, dict[int, dict]]:
    """npc id -> {item id: {'stock': -1 or how many, 'cost': copper}} for every vendor whose Forever page was read:
    what it sells in Forever, the whole list."""
    out = {}
    for nid, page in ((data or {}).get('npcs') or {}).items():
        if isinstance(page.get('sells'), list):
            out[int(nid)] = {int(r['id']): r for r in page['sells']}
    return out


def page_ids(data: dict, section: str = 'items') -> set[int]:
    return {int(i) for i in ((data or {}).get(section) or {})}


def avg_stack(row: dict) -> float:
    """Average stack size from Wowhead's spread {size: percent}; 1 when it is not given."""
    st = row.get('stack') or {}
    total = sum(st.values())
    return sum(int(s) * p for s, p in st.items()) / total if total > 0 else 1.0


def _add(out: dict, sid: int, item: int, r: dict, info: dict, read: str) -> None:
    s = out.setdefault(sid, {'id': sid, 'name': info.get('name', ''), 'min_level': info.get('minlevel'),
                             'max_level': info.get('maxlevel'), 'zones': info.get('location') or [],
                             'classification': info.get('classification'), 'looted': 0, 'items': {}, 'counts': {},
                             'read': read, 'complete': False})
    s['looted'] = max(s['looted'], r['outof'])
    s['items'][item] = r['count'] / r['outof'] * avg_stack(r)
    s['counts'][item] = (r['count'], r['outof'])
    s['read'] = min(s['read'], read)                 # the oldest page behind this source


def _sources(data: dict, item_tabs: tuple[str, ...] | None, kind: str, own_section: str,
             own_tabs: tuple[str, ...]) -> dict[int, dict]:
    """source id -> what it gives per loot, from item pages' tabs of this kind, then the source's own page (complete:
    it replaces what the item pages said)."""
    out: dict[int, dict] = {}
    for iid, page in ((data or {}).get('items') or {}).items():
        for tid, tab in (page.get('tabs') or {}).items():
            if tab.get('kind') != kind or (item_tabs is not None and tid not in item_tabs):
                continue
            for r in tab['rows']:
                if r['outof'] > 0:
                    _add(out, r['id'], int(iid), r, r, page.get('read', ''))
    for sid, page in ((data or {}).get(own_section) or {}).items():
        sid = int(sid)
        tabs = [t for tid, t in (page.get('tabs') or {}).items() if tid in own_tabs and t.get('kind') == 'item']
        if not tabs:
            continue
        old = out.pop(sid, {})
        info = {'name': page.get('name') or old.get('name', ''), 'minlevel': old.get('min_level'),
                'maxlevel': old.get('max_level'), 'location': old.get('zones'), 'classification': old.get('classification')}
        for tab in tabs:
            for r in tab['rows']:
                if r['outof'] > 0:
                    _add(out, sid, r['id'], r, info, page.get('read', ''))
        if sid in out:
            out[sid]['complete'] = True
    for s in out.values():
        s['small_sample'] = s['looted'] < SOLID
    return out


def mob_drops(data: dict) -> dict[int, dict]:
    """npc id -> {name, levels, zones, looted, items: {item id: expected quantity per kill}, complete}. From item pages'
    "Dropped by" tabs (only the items read: a floor) or the mob's own page (complete: every drop it has)."""
    return _sources(data, ('dropped-by',), 'npc', 'npcs', ('drops',))


def object_yields(data: dict) -> dict[int, dict]:
    """object id -> {name, looted, items: {item id: expected quantity per gather or opening}, complete}: herb and ore
    nodes, chests, fishing pools. From item pages' object tabs, or the object's own page (complete)."""
    return _sources(data, None, 'object', 'objects', ('contains', 'mining', 'herbalism', 'fishing'))


def as_skinning(data: dict) -> dict:
    """Item pages' "Skinned from" tabs in the skinning snapshot's shape (skinning.py), so they feed skinning spots."""
    items = {}
    for iid, page in ((data or {}).get('items') or {}).items():
        tab = (page.get('tabs') or {}).get('skinned-from')
        if not tab:
            continue
        items[str(iid)] = {'name': page.get('name', ''), 'url': page.get('url', ''), 'checked': page.get('read', ''),
                           'npcs': [{'npc': r['id'], 'name': r.get('name', ''), 'count': r['count'], 'outof': r['outof'],
                                     'min_level': r.get('minlevel') or 0, 'max_level': r.get('maxlevel') or 0,
                                     'zones': r.get('location') or []} for r in tab['rows']]}
    return {'items': items}


def mob_skins(data: dict) -> dict[int, dict]:
    """npc id -> what skinning it gives, from the mob's own page (its Skinning tab: complete, every item a skin gave),
    in skinning.mobs' shape. A leather's page lists only the 30-40 mobs skinned most, so a mob outside those lists
    had no skin in the app (2026-11-26: Ridge Stalker, skinned 1,221 times in Forever). Levels from the page's Quick
    Facts, else the item pages' rows; zones from the item pages' rows. Items per skin count their stack (Pristine Hide:
    2 or 3)."""
    out, drops = {}, None
    for nid, page in ((data or {}).get('npcs') or {}).items():
        tab = (page.get('tabs') or {}).get('skinning')
        rows = [r for r in ((tab or {}).get('rows') or []) if r['outof'] > 0]
        if not tab or tab.get('kind') != 'item' or not rows:
            continue
        if drops is None:
            drops = mob_drops(data)
        info = drops.get(int(nid)) or {}
        level = (page.get('facts') or {}).get('level') or []
        out[int(nid)] = {'npc': int(nid), 'name': page.get('name') or info.get('name', ''),
                         'min_level': (level[0] if level else 0) or info.get('min_level') or 0,
                         'max_level': (level[-1] if level else 0) or info.get('max_level') or 0,
                         'zones': info.get('zones') or [], 'skinned': max(r['outof'] for r in rows),
                         'items': {r['id']: r['count'] / r['outof'] * avg_stack(r) for r in rows},
                         'read': page.get('read', ''), 'own_page': True}
    return out


def merge_skinning(snapshot: dict, pages: dict) -> dict:
    """The skinning snapshot with every item page's "Skinned from" rows added, mob by mob: the two keep different
    rows (the snapshot the 40 most skinned for the item, a page the 30 mobs skinned most), and for a mob in both
    the newer read wins. Mobs whose own page was read go under 'mob_pages' (mob_skins): skinning.mobs lets them
    replace what the item lists say, and the item lists stay what the leather pages show (coverage counts those)."""
    extra = as_skinning(pages).get('items') or {}
    own = mob_skins(pages)
    if not extra and not own:
        return snapshot or {}
    out = dict(snapshot or {})
    if own:
        out['mob_pages'] = own
    if not extra:
        return out
    items = dict((snapshot or {}).get('items') or {})
    for iid, page_item in extra.items():
        old = items.get(iid)
        if not old:
            items[iid] = page_item
            continue
        newer = page_item.get('checked', '') >= old.get('checked', '')
        rows = {r['npc']: r for r in (old.get('npcs') or [])}
        for r in page_item['npcs']:
            if newer or r['npc'] not in rows:
                rows[r['npc']] = r
        items[iid] = {**old, 'npcs': sorted(rows.values(), key=lambda r: (-r['outof'], r['npc']))}
    out['items'] = items
    nr = out.get('not_read') or {}
    out['not_read'] = ({k: v for k, v in nr.items() if str(k) not in extra} if isinstance(nr, dict)
                       else [i for i in nr if str(i) not in extra])
    return out


def import_file(path: Path, target: Path | None = None) -> tuple[list[str], list[str], dict]:
    """Merge a file of pages ({key: page}) read out of the Wowhead tab into the snapshot and save it."""
    pages = json.loads(Path(path).read_text(encoding='utf-8'))
    data, saved, problems = merge(load(target), pages)
    if saved:
        save(data, target)
    return saved, problems, {sec: len(data.get(sec) or {}) for sec in SECTIONS}


# item page tab -> the way of getting the item it gives Forever data for (coverage.py's kinds)
TAB_TO_KIND = {'dropped-by': 'drops', 'pick-pocketed-from': 'drops', 'skinned-from': 'skinning',
               'mined-from-object': 'mining', 'gathered-from-object': 'herbalism', 'contained-in-object': 'objects',
               'fished-in': 'fishing'}


def page_kinds(data: dict) -> dict[int, set[str]]:
    """item id -> the ways of getting it that its page has Forever rows for. A page read with a tab of only Classic
    Era rows (or none at all) gives no Forever data for that way: Wowhead hasn't recorded it yet."""
    out = {}
    for iid, page in ((data or {}).get('items') or {}).items():
        out[int(iid)] = {TAB_TO_KIND[t] for t, tab in (page.get('tabs') or {}).items()
                         if t in TAB_TO_KIND and tab.get('rows')}
    return out


def no_sources(data: dict) -> set[int]:
    """Items whose page was read and lists no way at all to loot them (no source tab, not even Classic rows)."""
    return {int(iid) for iid, page in ((data or {}).get('items') or {}).items() if not page.get('tabs')}


def covered_by_objects(data: dict) -> set[int]:
    """Items listed on any object page read in full (nodes, chests, pools)."""
    return {r['id'] for page in ((data or {}).get('objects') or {}).values()
            for tab in (page.get('tabs') or {}).values() if tab.get('kind') == 'item' for r in tab['rows']}


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != 'import':
        raise SystemExit('usage: python -m wfm.wowhead_items import <pages.json>')
    saved, problems, total = import_file(Path(sys.argv[2]))
    print(f'saved {len(saved)}: {", ".join(saved)}')
    for p in problems:
        print('problem:', p)
    print('pages now:', ', '.join(f'{n} {sec}' for sec, n in total.items()))
