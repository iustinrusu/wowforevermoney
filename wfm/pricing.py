"""Price helpers: what an item costs to buy and what it realistically sells for. All values in copper.

TSM field meanings (support.tradeskillmaster.com price-source docs):
  minBuyout          lowest listing on the realm at the last scan
  numAuctions        listings on the realm at the last scan (missing = none listed)
  marketValue        realm 14-day weighted average of *listings* (not sales)
  marketValueRecent  realm market value from the latest scan only
  historical         realm 60-day average of marketValue
  regionMarketValue  average of marketValue over every realm in the region
  regionHistorical   60-day average of regionMarketValue
  regionSale         average *sale* price in the region, from TSM users' accounting data
  regionSoldPerDay   units sold per day in the region, TSM-tracked (relative liquidity, not an exact count)
  regionSalePercent  share of listings that sell, 0..1
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Quote:
    value: int            # copper per unit
    source: str           # where the number came from
    flags: tuple = ()


def listed(p: dict | None) -> bool:
    return bool(p) and p.get('numAuctions', 0) > 0 and p.get('minBuyout', 0) > 0


def ah_buy(p: dict | None) -> Quote | None:
    """What buying one unit on your realm's AH costs."""
    if not p:
        return None
    if listed(p):
        return Quote(int(p['minBuyout']), 'lowest listing')
    if p.get('marketValue'):
        return Quote(int(p['marketValue']), 'market value (none listed now)', ('none_listed',))
    if p.get('regionMarketValue'):
        return Quote(int(p['regionMarketValue']), 'region market value', ('no_realm_data',))
    return None


def ah_sell(p: dict | None) -> Quote | None:
    """A conservative realistic sale price on your realm: you have to undercut the current lowest
    listing, and you shouldn't expect more than the realm's usual price."""
    if not p:
        return None
    flags = []
    candidates = []
    if listed(p):
        candidates.append((int(p['minBuyout']), 'lowest listing'))
    if p.get('marketValue'):
        candidates.append((int(p['marketValue']), 'realm market value'))
    if not candidates:
        if p.get('regionMarketValue'):
            candidates.append((int(p['regionMarketValue']), 'region market value'))
            flags.append('no_realm_data')
        else:
            return None
    if not listed(p):
        flags.append('none_listed')
    value, source = min(candidates)
    sale = p.get('regionSale', 0)
    if sale and sale < 0.7 * value:
        flags.append('sells_lower')   # actual recorded sales are well below listing prices
    if not p.get('regionSoldPerDay'):
        flags.append('no_sales_data')
    region = p.get('regionMarketValue', 0)
    if listed(p) and region and p['minBuyout'] > 2.5 * region:
        flags.append('above_region')
    return Quote(value, source, tuple(flags))


def proceeds(quote: Quote | None, ah_cut: float) -> int:
    return int(quote.value * (1 - ah_cut)) if quote else 0


def sold_per_day(p: dict | None) -> float:
    return float(p.get('regionSoldPerDay', 0)) if p else 0.0


def sale_rate(p: dict | None) -> float:
    return float(p.get('regionSalePercent', 0)) if p else 0.0


def fmt_money(copper: float) -> str:
    sign = '-' if copper < 0 else ''
    c = int(round(abs(copper)))
    g, s, c = c // 10000, (c // 100) % 100, c % 100
    parts = []
    if g:
        parts.append(f'{g}g')
    if s or g:
        parts.append(f'{s}s')
    parts.append(f'{c}c')
    return sign + ' '.join(parts)
