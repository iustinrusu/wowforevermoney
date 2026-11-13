"""What an item is worth to you: the best of every way to turn it into gold, at current prices.

Ways to turn an item into gold ("channels"):
- sell it on the AH (after the cut; a stray high listing with no sales behind it counts at the sale price),
- sell it to a vendor,
- use it in a recipe (the best craft it goes into),
- open it (trunks, clams, crates, lockboxes): the expected value of its contents, each valued the same way.

Why this exists: items whose worth comes from opening them have no AH price (they're often soulbound) and a
tiny vendor price, so judging by AH/vendor/crafting alone made a Mithril Bound Trunk "worth 2c" while it
holds Mageweave, Runecloth and leather. The client's own item flags say which items can be opened, so an
openable item without known contents is flagged (its value is only a floor) instead of silently undervalued.

Contents data is Forever only: your own opened containers (ForeverMoneyBridge) plus Wowhead Forever counts
read by hand. Values follow current prices, so they move with every TSM update.
"""
from __future__ import annotations

from dataclasses import dataclass, field

OPEN_DEPTH = 2              # a container inside a container is valued; deeper than that isn't
WORTH_OPENING = 1.2         # flag "open it" when opening beats selling by 20%+
CRAFT_DEMAND = 50           # flag a crafting value when its product's market absorbs fewer units/day than this


@dataclass
class Value:
    value: int
    channel: str                         # AH | vendor | craft | open | none
    how: str
    flags: tuple = ()
    channels: dict = field(default_factory=dict)    # every channel that applies -> copper
    contents: list = field(default_factory=list)    # for 'open': top contents [{item_id, per_open, value}]
    contents_source: str = ''
    if_skilled: dict | None = None      # a recipe you can't make yet that would be worth more


def merge_contents(wowhead: dict | None, own: dict | None) -> dict[int, dict]:
    """item id -> {'opened': n, 'qty': {content id: total quantity seen}, 'sources': [...]}

    wowhead: {"21228": {"opened": 608, "items": [[id, times, min, max], ...], "checked": ...}} (times x average stack)
    own:     ForeverMoneyBridge {21228: {"opened": 3, "items": {id: quantity}}}
    """
    out: dict[int, dict] = {}
    for iid, c in (wowhead or {}).items():
        opened = int(c.get('opened') or 0)
        if not opened:
            continue
        o = out.setdefault(int(iid), {'opened': 0, 'qty': {}, 'sources': []})
        o['opened'] += opened
        for row in c.get('items') or []:
            cid, times, lo, hi = int(row[0]), int(row[1]), int(row[2]), int(row[3])
            o['qty'][cid] = o['qty'].get(cid, 0) + times * (lo + hi) / 2
        o['sources'].append(f'Wowhead Forever ({opened:,} opened, {c.get("checked", "?")})')
    for iid, c in (own or {}).items():
        opened = int((c or {}).get('opened') or 0)
        if not opened:
            continue
        o = out.setdefault(int(iid), {'opened': 0, 'qty': {}, 'sources': []})
        o['opened'] += opened
        for cid, q in ((c or {}).get('items') or {}).items():
            o['qty'][int(cid)] = o['qty'].get(int(cid), 0) + int(q)
        o['sources'].append(f'you ({opened} opened)')
    return out


class Valuer:
    def __init__(self, engine, best_use: dict[int, dict], contents: dict[int, dict]):
        self.e = engine
        self.best_use = best_use or {}
        self.contents = contents or {}
        self._cache: dict[tuple, Value] = {}

    def value(self, iid: int, _depth: int = 0) -> Value:
        key = (iid, _depth)
        if key not in self._cache:
            self._cache[key] = self._value(iid, _depth)
        return self._cache[key]

    def worth(self, iid: int) -> int:
        return self.value(iid).value

    def _value(self, iid: int, depth: int) -> Value:
        e = self.e
        item = e.gd.items.get(iid)
        channels, flags = {}, []
        sell, channel, q = e.sell_value(iid)
        if channel == 'AH' and q and {'no_sales_data', 'above_region'} & set(q.flags):
            # ah_sell already caps at the average sale price; with no recorded sale at all, don't count on the AH
            flags.append('ah_price_doubtful')
            if not (e.price(iid) or {}).get('regionSale'):
                sell = 0
        vendor = item.sell_price if item else 0
        tradeable = not (item and (item.bonding == 1 or item.class_id == 12))     # soulbound or quest item
        if channel == 'AH' and sell > 0 and tradeable:
            channels['AH'] = sell
        if vendor:
            channels['vendor'] = vendor
        use = self.best_use.get(iid)
        if use and (use.get('doable_value') or 0) > 0:
            channels['craft'] = int(use['doable_value'])      # only recipes you can make now
        if_skilled = None
        if use and use['value'] > max([0] + list(channels.values())) and not use.get('doable'):
            if_skilled = {'value': int(use['value']), 'recipe': use['recipe'], 'profession': use['profession'],
                          'skill': use.get('skill')}
            flags.append('more_with_skill')
        contents, source = [], ''
        if item and item.openable:
            c = self.contents.get(iid)
            if c and depth < OPEN_DEPTH:
                total = 0.0
                for cid, qty in c['qty'].items():
                    per_open = qty / c['opened']
                    v = self.value(cid, depth + 1).value
                    total += per_open * v
                    contents.append({'item_id': cid, 'name': e.name(cid), 'per_open': round(per_open, 3), 'value': v})
                contents.sort(key=lambda r: -r['per_open'] * r['value'])
                channels['open'] = int(total)
                source = ' + '.join(c['sources'])
            elif not c:
                flags.append('contents_unknown')
            if item.locked:
                flags.append('locked')
        if not channels:
            return Value(0, 'none', 'no known way to turn it into gold', tuple(flags + ['no_value']), {},
                         if_skilled=if_skilled)
        best = max(channels, key=lambda k: channels[k])
        if best == 'open' and channels['open'] >= WORTH_OPENING * max(channels.get('AH', 0), vendor, 1):
            flags.append('open_it')
        if best == 'craft' and use and (use.get('doable_units_per_day') or 0) < CRAFT_DEMAND:
            flags.append('craft_limited_demand')    # beyond that many a day, it's worth its sale price
        how = {'AH': 'sell on the AH', 'vendor': 'sell to a vendor', 'open': 'open it',
               'craft': f"{use['doable_profession']}: {use['doable_recipe']}" if use else 'craft'}[best]
        return Value(channels[best], best, how, tuple(flags), channels, contents[:12], source, if_skilled)
