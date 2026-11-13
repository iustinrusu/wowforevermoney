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


SALE_BASES = ('min_buyout', 'actual_sales')
ODD_LISTINGS, ODD_LOW, ODD_HIGH = 3, 0.5, 2.0    # few listings outside half..double the recent average: looks off


def ah_sell(p: dict | None, basis: str = 'min_buyout') -> Quote | None:
    """The price you'd sell one unit for on your realm's AH (before the AH cut).

    basis 'min_buyout' (default, the user's choice): the current lowest buyout, which is what you'd list at.
    basis 'actual_sales' (more conservative): never above the realm's usual listing price or the region's
    average *sale* price, since listings can sit unsold (Raw Winter Squid: lowest 3.80s, sells for ~2.50s).

    Nothing listed: there's no lowest buyout to match, so the average sale price is used, never the realm's
    listing average alone (a Hand Axe "worth" 2.5g by listings really sells for ~6.65s).
    """
    if not p:
        return None
    flags = []
    sale = int(p.get('regionSale', 0) or 0)
    if listed(p):
        value, source = int(p['minBuyout']), 'lowest listing'
        mv = int(p.get('marketValue') or 0)
        if mv and p.get('numAuctions', 0) <= ODD_LISTINGS and not (ODD_LOW * mv <= value <= ODD_HIGH * mv):
            # one or two odd listings (a cheap dump that will be bought out, or a greedy price) aren't the market:
            # use the realm's recent average until more listings confirm the new price
            value, source = mv, 'realm market value (lowest listing looks off)'
            flags.append('price_looks_off')
        if basis == 'actual_sales' and mv and mv < value:
            value, source = mv, 'realm market value'
    else:
        flags.append('none_listed')
        options = [(int(v), s) for v, s in ((sale, 'average sale price (region, actual sales)'),
                                            (p.get('marketValue'), 'realm market value'),
                                            (p.get('regionMarketValue'), 'region market value')) if v]
        if not options:
            return None
        if not sale and not p.get('marketValue'):
            flags.append('no_realm_data')
        value, source = options[0] if sale else min(options)
    if sale and sale < 0.7 * value:
        flags.append('sells_lower')       # listed well above what it actually sells for: it may sit unsold
    if basis == 'actual_sales' and sale and sale < value:
        value, source = sale, 'average sale price (region, actual sales)'
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


# How easily something sells on the AH. TSM gives region-wide sales (all Forever EU realms), the share of listings
# that sell, and how many are listed on your realm. Your realm sells at most the region's volume, so
# "days of supply" = realm listings / region sold per day is a floor on how long the stock already listed takes to go.
HARD_SOLD_PER_DAY = 1.0     # under 1 sold a day in the whole region
HARD_SALE_RATE = 0.10       # under 1 in 10 listings sells (Poached Sunscale Salmon: 6%)
HARD_DAYS = 10.0            # over 10 days of the region's sales already listed on your realm (Turtle Scale Breastplate: 12)
SLOW_SALE_RATE = 0.25       # under 1 in 4 listings sells: expect to relist and pay deposits again
CROWDED_DAYS = 3.0          # over 3 days of the region's sales listed on your realm: expect undercutting and waiting


def liquidity(p: dict | None, min_sold_per_day: float = 0.0) -> dict:
    """How well an item sells: region sold/day, sale rate, realm listings, days of supply, and flags.

    'hard_to_sell' (kept out of suggestions), 'slow_to_sell' and 'crowded' (ranked lower), 'no_sales_data'.
    """
    p = p or {}
    spd = float(p.get('regionSoldPerDay') or 0)
    rate = p.get('regionSalePercent')
    listed_now = int(p.get('numAuctions') or 0)
    days = listed_now / spd if spd > 0 else None
    flags, why = [], []
    if spd <= 0:
        flags.append('no_sales_data')
        why.append('no recorded sales')
    else:
        if spd < max(HARD_SOLD_PER_DAY, min_sold_per_day):
            why.append(f'only {spd:.1f} sold a day in the whole region')
        if rate is not None and rate < HARD_SALE_RATE:
            why.append(f'only {rate:.0%} of listings sell')
        if days is not None and days > HARD_DAYS:
            why.append(f'{listed_now} listed on your realm, {days:.0f} days of the region\'s sales')
        if why:
            flags.append('hard_to_sell')
        else:
            if rate is not None and rate < SLOW_SALE_RATE:
                flags.append('slow_to_sell')
                why.append(f'{rate:.0%} of listings sell')
            if days is not None and days > CROWDED_DAYS:
                flags.append('crowded')
                why.append(f'{listed_now} listed on your realm, {days:.1f} days of the region\'s sales')
    return {'sold_per_day': spd, 'sale_rate': rate, 'listed': listed_now, 'days_of_supply': days,
            'flags': flags, 'why': '; '.join(why)}


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
