"""Investments: items that may rise in value as WoW: Forever matures.

The candidate list and its theses are hand-curated (data/investments.json) from how these items went in WoW Classic
and from player progression. That part is speculation and is labelled so. Everything shown next to it is Forever
data: TSM prices, our own price history, vendor prices and Forever's recipe table.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from .paths import DATA
from .pricing import ah_buy, ah_sell, liquidity

LIST_FILE = DATA / 'investments.json'
DAY = 86400
SHORT_HISTORY = DAY      # under a day of snapshots: first vs latest, flagged as short
EDGE = DAY / 2           # with longer history, each end is the median of 12 hours of snapshots (one odd listing can't swing it)
WEEK = 7 * DAY
SLOW_SALE_RATE = 0.1     # under 10% of listings sell: you may wait a long time to sell
RISK_FACTOR = {'low': 1.0, 'medium': 0.75, 'high': 0.5}


def invest_score(buy: int | None, long_term: int | None, p: dict, risk: str) -> float:
    """Rank: cheap vs its long-term average (TSM historical) x how well it sells x risk. Unitless.

    A price 30% under its long-term average scores 1.3 before the other factors; 30% over scores 0.7.
    """
    value = 1.0
    if buy and long_term:
        value = 1 + max(-0.5, min(0.75, 1 - buy / long_term))
    liq = liquidity(p)['flags']
    sells = 0.3 if ('hard_to_sell' in liq or 'no_sales_data' in liq) else (0.7 if 'slow_to_sell' in liq else 1.0) * (
        0.8 if 'crowded' in liq else 1.0)
    return round(value * sells * RISK_FACTOR.get(risk, 0.75), 4)


def load_list(path: Path = LIST_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'items': [], 'progression_cloth': []}


def check_names(entries: list[dict], items: dict) -> tuple[list[dict], list[dict]]:
    """Keep entries whose id still has the expected name in the item database; drop (and report) the rest."""
    kept, dropped = [], []
    for e in entries:
        it = items.get(e.get('id'))
        if it and it.name == e.get('name'):
            kept.append(e)
        else:
            dropped.append({'id': e.get('id'), 'expected': e.get('name'), 'found': it.name if it else None})
    return kept, dropped


def _median_between(points, lo, hi):
    vals = [v for ts, v in points if lo <= ts <= hi]
    return statistics.median(vals) if vals else None


def trend(series: list[dict], field: str = 'min_buyout') -> dict | None:
    """How a price moved over our own history. Needs 2+ snapshots with a price.

    Under a day of history: first vs latest snapshot ('short'). Longer: each end is the median of 12 hours of
    snapshots. 'change_7d' only once there's a week of history.
    """
    points = sorted((s['ts'], s[field]) for s in series if s.get(field))
    if len(points) < 2:
        return None
    first, last = points[0][0], points[-1][0]
    span = last - first
    if span < SHORT_HISTORY:
        start, end = points[0][1], points[-1][1]
    else:
        start = _median_between(points, first, first + EDGE)
        end = _median_between(points, last - EDGE, last)
    out = {'from_ts': first, 'to_ts': last, 'scans': len(points), 'short': span < SHORT_HISTORY,
           'start': start, 'end': end, 'change': end / start - 1 if start else None, 'change_7d': None}
    if span >= WEEK:
        base = _median_between(points, last - WEEK - EDGE, last - WEEK + EDGE)
        if base:
            out['change_7d'] = end / base - 1
    return out


def downside(buy: int | None, vendor: int) -> float | None:
    """Worst case as a fraction of what you pay: the price falls to what a vendor pays (-1.0 = lose everything)."""
    if not buy:
        return None
    return min(0.0, vendor / buy - 1)


def break_even_rise(cut: float) -> float:
    """How much the price must rise before reselling on the AH (minus its cut) beats what you paid."""
    return 1 / (1 - cut) - 1


def progression(cloth: list[dict], prices: dict, first_snapshot: dict[int, float] | None = None) -> dict:
    """Server progression gauge: each cloth tier's share of the region's daily cloth sales.

    More Runecloth traded means more players near level 60, when endgame demand starts. It's a rough sign:
    sold/day mixes supply and demand.
    """
    total = sum((prices.get(c['id']) or {}).get('regionSoldPerDay', 0) for c in cloth)
    then_total = sum((first_snapshot or {}).get(c['id'], 0) for c in cloth)
    tiers = []
    for c in cloth:
        spd = (prices.get(c['id']) or {}).get('regionSoldPerDay', 0)
        then = (first_snapshot or {}).get(c['id'])
        tiers.append({'id': c['id'], 'name': c['name'], 'levels': c.get('levels', ''), 'sold_per_day': spd,
                      'share': spd / total if total else 0.0,
                      'share_then': then / then_total if then is not None and then_total else None})
    return {'tiers': tiers, 'total': total}


def build(curated: dict, items: dict, recipes: list, prices: dict, series_of, watchlist, cut: float,
          basis: str = 'min_buyout', now: float | None = None) -> dict:
    """Everything the Investments tab shows. series_of(item_id) returns our price history snapshots, oldest first."""
    now = now or time.time()
    entries, dropped = check_names(curated.get('items', []), items)
    used_in: dict[int, list[str]] = {}
    for r in recipes:
        for m, _ in r.reagents:
            used_in.setdefault(m, []).append(r.name)
    watch = set(watchlist or [])
    rows = []
    for e in entries:
        iid = e['id']
        it = items[iid]
        p = prices.get(iid) or {}
        buy = ah_buy(p)
        sell = ah_sell(p, basis)
        flags = list(buy.flags) if buy else ['no_sales_data']
        if sell:
            flags += [f for f in sell.flags if f not in flags]
        tr = trend(series_of(iid))
        if tr is None or tr['short']:
            flags.append('short_history')
        if p and p.get('regionSalePercent', 0) < SLOW_SALE_RATE:
            flags.append('slow_sale_rate')
        market = p.get('marketValue')
        names = sorted(set(used_in.get(iid, [])))
        long_term = p.get('historical') or p.get('regionHistorical')
        buy_v = buy.value if buy else None
        rows.append({
            'item_id': iid, 'name': it.name, 'quality': it.quality, 'category': e.get('category', ''),
            'thesis': e.get('thesis', ''), 'horizon': e.get('horizon', ''), 'risk': e.get('risk', ''),
            'risk_note': e.get('risk_note', ''),
            'buy': buy.value if buy else None, 'buy_source': buy.source if buy else None,
            'min_buyout': p.get('minBuyout'), 'listings': p.get('numAuctions', 0), 'market': market,
            'region_sale': p.get('regionSale'), 'sold_per_day': p.get('regionSoldPerDay'),
            'sale_rate': p.get('regionSalePercent'),
            'vs_market': (p['minBuyout'] / market - 1) if p.get('minBuyout') and p.get('numAuctions') and market else None,
            'vendor_sell': it.sell_price, 'downside': downside(buy.value if buy else None, it.sell_price),
            'trend': tr, 'used_in_count': len(names), 'used_in': names[:12],
            'watching': iid in watch, 'flags': flags, 'long_term': long_term,
            'vs_long_term': (buy_v / long_term - 1) if buy_v and long_term else None,
            'score': invest_score(buy_v, long_term, p, e.get('risk', '')),
        })
    rows.sort(key=lambda r: -r['score'])
    # the gauge then: every cloth tier at our oldest snapshot (one moment, so the shares are comparable)
    cloth = curated.get('progression_cloth', [])
    cloth_series = {c['id']: [x for x in series_of(c['id']) if x.get('sold_per_day') is not None] for c in cloth}
    stamps = [x['ts'] for s in cloth_series.values() for x in s]
    first_ts = min(stamps) if stamps else None
    first = {cid: x['sold_per_day'] for cid, s in cloth_series.items() for x in s if x['ts'] == first_ts}
    # region sold/day changes about once a day, so a comparison needs at least a day of history
    usable = cloth and len(first) == len(cloth) and first_ts is not None and now - first_ts >= SHORT_HISTORY
    prog = progression(cloth, prices, first if usable else None)
    prog['then_ts'] = first_ts if prog['tiers'] and prog['tiers'][0]['share_then'] is not None else None
    return {'items': rows, 'dropped': dropped, 'progression': prog, 'break_even': break_even_rise(cut),
            'history_from': first_ts, 'checked': curated.get('checked'), 'generated_at': int(now)}
