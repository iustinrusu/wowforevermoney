"""Market tab: one item's price history (our own snapshots, one per TSM realm scan) plus market signals.

Signals are read from Forever data only: TSM's current realm and region numbers and this app's price history.
They summarise what the market is doing now; they are not a forecast.
"""
from __future__ import annotations

import statistics

from .investments import trend
from .pricing import liquidity

DAY = 86400
MOVE = 0.05          # a price change under 5% is noise
BELOW_AVG = -0.15    # lowest listing 15% under the 14-day realm average
ABOVE_AVG = 0.15
SUPPLY_MOVE = 0.30   # listings up or down 30%
CHEAP_VS_REGION = 0.8
DEAR_VS_REGION = 1.5


def _window(series: list[dict], since: float) -> list[dict]:
    return [s for s in series if s['ts'] >= since]


def _median_listings(series: list[dict]) -> float | None:
    vals = [s['num_auctions'] for s in series if s.get('num_auctions') is not None]
    return statistics.median(vals) if vals else None


def signals(p: dict | None, series: list[dict], now: float) -> list[dict]:
    """Each signal: name, score (-1 bearish, 0 neutral, +1 bullish, None = not enough data), reading."""
    p = p or {}
    out = []
    # 1. momentum: lowest listing over the last day (or the last week once we have one)
    week = trend(_window(series, now - 7 * DAY))
    day = trend(_window(series, now - DAY))
    tr = week if week and not week['short'] and week['to_ts'] - week['from_ts'] >= 3 * DAY else day
    if tr and tr['change'] is not None:
        c = tr['change']
        hours = (tr['to_ts'] - tr['from_ts']) / 3600
        span = f'{hours:.0f} hours' if hours < 48 else f'{hours / 24:.0f} days'
        out.append({'name': 'Price momentum', 'score': 1 if c > MOVE else (-1 if c < -MOVE else 0),
                    'reading': f'lowest listing {c:+.0%} over {span} ({tr["scans"]} snapshots)'})
    else:
        out.append({'name': 'Price momentum', 'score': None, 'reading': 'not enough price history yet'})
    # 2. now vs the realm's 14-day average (TSM market value)
    mb, mv = p.get('minBuyout'), p.get('marketValue')
    if mb and p.get('numAuctions') and mv:
        d = mb / mv - 1
        out.append({'name': 'Price vs 14-day average', 'score': 1 if d > ABOVE_AVG else (-1 if d < BELOW_AVG else 0),
                    'reading': f'lowest listing {d:+.0%} vs the realm\'s 14-day average'})
    else:
        out.append({'name': 'Price vs 14-day average', 'score': None, 'reading': 'nothing listed now'})
    # 3. supply: listings now vs a day ago (median of the snapshots 20-28 hours back)
    then = _median_listings([s for s in series if now - 28 * 3600 <= s['ts'] <= now - 20 * 3600])
    listed = p.get('numAuctions')
    if then and listed is not None:
        d = listed / then - 1
        out.append({'name': 'Supply', 'score': -1 if d > SUPPLY_MOVE else (1 if d < -SUPPLY_MOVE else 0),
                    'reading': f'{listed} listed now vs {then:.0f} a day ago ({d:+.0%})'})
    else:
        out.append({'name': 'Supply', 'score': None,
                    'reading': f'{listed if listed is not None else "?"} listed now; a comparison needs a day of history'})
    # 4. demand: does it sell?
    liq = liquidity(p)
    if 'no_sales_data' in liq['flags']:
        out.append({'name': 'Demand', 'score': None, 'reading': 'no recorded sales'})
    else:
        rate = liq['sale_rate']
        strong = liq['sold_per_day'] >= 10 and rate is not None and rate >= 0.5
        score = -1 if 'hard_to_sell' in liq['flags'] else (1 if strong else 0)
        rate_txt = f', {rate:.0%} of listings sell' if rate is not None else ''
        out.append({'name': 'Demand', 'score': score,
                    'reading': f'{liq["sold_per_day"]:.1f} sold a day in the region{rate_txt}'})
    # 5. your realm vs what it sells for across the region
    sale = p.get('regionSale')
    if mb and p.get('numAuctions') and sale:
        r = mb / sale
        out.append({'name': 'Realm vs region', 'score': 1 if r < CHEAP_VS_REGION else (-1 if r > DEAR_VS_REGION else 0),
                    'reading': f'lowest listing is {r:.0%} of the region\'s average sale price'
                               + (' (cheap here)' if r < CHEAP_VS_REGION else (' (dear here)' if r > DEAR_VS_REGION else ''))})
    else:
        out.append({'name': 'Realm vs region', 'score': None, 'reading': 'no listing or no region sales to compare'})
    return out


def sentiment(sigs: list[dict]) -> dict:
    """Overall reading: sum of the signals that have data."""
    scored = [s['score'] for s in sigs if s['score'] is not None]
    total = sum(scored)
    label = 'Bullish' if total >= 2 else ('Bearish' if total <= -2 else 'Neutral')
    return {'label': label, 'score': total, 'signals_with_data': len(scored), 'signals': len(sigs)}


def build(iid: int, item, p: dict | None, series: list[dict], now: float) -> dict:
    sigs = signals(p, series, now)
    return {'id': iid, 'name': item.name if item else f'Item {iid}', 'quality': item.quality if item else 1,
            'vendor_sell': item.sell_price if item else 0, 'prices': p or {}, 'series': series,
            'trend_24h': trend(_window(series, now - DAY)), 'trend_7d': trend(_window(series, now - 7 * DAY)),
            'trend_all': trend(series), 'signals': sigs, 'sentiment': sentiment(sigs),
            'liquidity': liquidity(p), 'generated_at': int(now)}
