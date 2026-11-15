"""Everloot (everloot.app): WoW: Forever drop rates from players' uploads, a second source to check ours against.

Data from Everloot (https://everloot.app), CC BY-SA 4.0. Saved by hand as data/everloot/drops_*.json, the pages of
its public API `/api/rollups/drops?limit=500&offset=N` (download approved by the user, 2026-11-15; data/ is never
committed). In a rate, `kills` counts loot windows of that mob or object (not kills) and `drops` the windows that
had the item, so rate = drops / kills, the same measure as a Wowhead row's count / outof.

Cross-check only (to-do 2c): each rate is compared with the Wowhead Forever counts read by hand for the same mob or
object and item, and the two are said to disagree only when both samples are big enough for the gap to mean
something. Everloot's rates are not used in any number yet: whether they may fill gaps where Wowhead has nothing
(Forever data, but player uploads with small samples) is the user's question once this shows how well they agree.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .paths import DATA

DIR = DATA / 'everloot'
CREDIT = 'Data from Everloot (https://everloot.app), CC BY-SA 4.0.'
MIN_LOOTS = 30        # each side needs this many loots for a comparison to count
GAP_Z = 3.0           # a gap at least this many standard errors wide ...
GAP_RATIO = 1.5       # ... with one rate at least 1.5 times the other: the two sources disagree
# Wowhead tabs that hold a mob's or object's loot for an item, in the order a comparison prefers them
NPC_TABS = ('dropped-by', 'pick-pocketed-from', 'skinned-from')
OBJECT_TABS = ('contained-in-object', 'mined-from-object', 'gathered-from-object')


def files(dirpath: Path | None = None) -> list[Path]:
    return sorted((dirpath or DIR).glob('drops_*.json'))


def _int(v) -> int | None:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def load(dirpath: Path | None = None) -> dict:
    """{'rates': {(kind, source id, item id): {looted, count, reporters, name}}, 'as_of', 'total', 'files', 'bad'}.

    kind is 'npc' or 'object'. A row missing a field or with odd numbers is skipped (counted in 'bad')."""
    rates, as_of, total, bad, used = {}, '', 0, 0, []
    for f in files(dirpath):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get('rates'), list):
            continue
        used.append(f.name)
        as_of = max(as_of, str(d.get('dataAsOf') or ''))
        total = max(total, _int(d.get('total')) or 0)
        for r in d['rates']:
            if not isinstance(r, dict):
                bad += 1
                continue
            kind = 'npc' if 'sourceNpcId' in r else 'object' if 'sourceObjectId' in r else None
            src = _int(r.get('sourceNpcId' if kind == 'npc' else 'sourceObjectId')) if kind else None
            item, looted, count = _int(r.get('itemId')), _int(r.get('kills')), _int(r.get('drops'))
            if not kind or not src or not item or not looted or count is None or count > looted:
                bad += 1
                continue
            rates[(kind, src, item)] = {'looted': looted, 'count': count, 'reporters': _int(r.get('reporters')) or 0,
                                        'name': str(r.get('sourceName') or '')[:80]}
    return {'rates': rates, 'as_of': as_of[:10], 'total': total, 'files': used, 'bad': bad}


def wowhead_counts(pages: dict) -> dict[tuple, dict]:
    """(kind, source id, item id) -> {count, outof, tab, read} from the Wowhead Forever pages read by hand: item pages'
    mob and object tabs, and mobs' and objects' own pages. Where two tabs give the same pair, the preferred tab wins
    (dropped-by before skinned-from: Everloot does not say which kind of loot a window was)."""
    out: dict[tuple, dict] = {}

    def put(key, r, tab, read, rank):
        cur = out.get(key)
        if cur is None or rank < cur['rank']:
            out[key] = {'count': int(r['count']), 'outof': int(r['outof']), 'tab': tab, 'read': read, 'rank': rank}

    for iid, page in ((pages or {}).get('items') or {}).items():
        for tid, tab in (page.get('tabs') or {}).items():
            kind = tab.get('kind')
            order = NPC_TABS if kind == 'npc' else OBJECT_TABS if kind == 'object' else ()
            if tid not in order:
                continue
            for r in tab.get('rows') or []:
                if r.get('outof'):
                    put((kind, int(r['id']), int(iid)), r, tid, page.get('read', ''), order.index(tid))
    for section, kind in (('npcs', 'npc'), ('objects', 'object')):
        for sid, page in ((pages or {}).get(section) or {}).items():
            for tid, tab in (page.get('tabs') or {}).items():
                if tab.get('kind') != 'item':
                    continue
                for r in tab.get('rows') or []:
                    if r.get('outof'):
                        put((kind, int(sid), int(r['id'])), r, f'{section[:-1]} page: {tid}', page.get('read', ''), -1)
    return out


def z_score(c1: int, n1: int, c2: int, n2: int) -> float:
    """How many standard errors apart two rates are (two-proportion test, pooled)."""
    if not n1 or not n2:
        return 0.0
    p = (c1 + c2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return abs(c1 / n1 - c2 / n2) / se if se > 0 else 0.0


def judge(ev: dict, wh: dict) -> str:
    """'small' (a side has under MIN_LOOTS loots), 'gap' (far apart and clearly so) or 'agree'."""
    if ev['looted'] < MIN_LOOTS or wh['outof'] < MIN_LOOTS:
        return 'small'
    a, b = ev['count'] / ev['looted'], wh['count'] / wh['outof']
    hi, lo = max(a, b), min(a, b)
    far = lo == 0 or hi / lo >= GAP_RATIO
    return 'gap' if far and z_score(ev['count'], ev['looted'], wh['count'], wh['outof']) >= GAP_Z else 'agree'


def compare(ev: dict, pages: dict) -> dict:
    """Every pair (mob or object, item) in both sources, judged; plus counts for the Data health entry."""
    wh = wowhead_counts(pages)
    pairs = []
    for key, e in (ev.get('rates') or {}).items():
        w = wh.get(key)
        if not w:
            continue
        pairs.append({'kind': key[0], 'source': key[1], 'item': key[2], 'everloot': e, 'wowhead': w,
                      'everloot_rate': e['count'] / e['looted'], 'wowhead_rate': w['count'] / w['outof'],
                      'z': round(z_score(e['count'], e['looted'], w['count'], w['outof']), 1),
                      'verdict': judge(e, w)})
    pairs.sort(key=lambda p: (p['verdict'] != 'gap', -p['z']))
    n = {v: sum(1 for p in pairs if p['verdict'] == v) for v in ('agree', 'gap', 'small')}
    return {'pairs': pairs, 'counts': n, 'everloot_rates': len(ev.get('rates') or {}), 'wowhead_pairs': len(wh),
            'as_of': ev.get('as_of', ''), 'files': ev.get('files') or []}


def describe(p: dict, name) -> str:
    """One pair in a sentence. name(kind, id) -> a mob's, object's or item's name."""
    src = name(p['kind'], p['source'])
    return (f"{name('item', p['item'])} from {src}: Wowhead Forever {p['wowhead_rate']:.1%} of {p['wowhead']['outof']:,} "
            f"loots ({p['wowhead']['tab']}), Everloot {p['everloot_rate']:.1%} of {p['everloot']['looted']:,} loot "
            f"windows ({p['everloot']['reporters']} players)"
            + (f": {p['z']} standard errors apart" if p['verdict'] == 'gap' else ''))
