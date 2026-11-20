"""What an item is worth to you: the best of every way to turn it into gold, at current prices.

Ways to turn an item into gold ("channels"):
- sell it on the AH (after the cut; a stray high listing with no sales behind it counts at the sale price),
- sell it to a vendor,
- use it in a recipe (the best craft it goes into),
- open it (trunks, clams, crates, lockboxes): the expected value of its contents, each valued the same way.
Disenchanting is shown beside them, never chosen as the best way: its results come from ForeverRecipes' WoW Classic
reference table (the user's yes to a labelled fallback, 2026-11-19), so it informs, it doesn't decide (flag
`disenchant_more` when the table says it may be worth more).

Why this exists: items whose worth comes from opening them have no AH price (they're often soulbound) and a
tiny vendor price, so judging by AH/vendor/crafting alone made a Mithril Bound Trunk "worth 2c" while it
holds Mageweave, Runecloth and leather. The client's own item flags say which items can be opened, so an
openable item without known contents is flagged (its value is only a floor) instead of silently undervalued.

Contents data is Forever only: your own opened containers (ForeverMoneyBridge) plus Wowhead Forever counts
read by hand. Values follow current prices, so they move with every TSM update.

Crafted worth holds only for as many units a day as the recipe can use (the user's decision, 2026-11-15): its
cooldown and what the product's market takes at your share. Every unit beyond that is worth the next best channel
(usually its sale price). Thorium Bar: 21g 65s through Transmute: Arcanite, for 1 every 2 days; the rest at 17s.
So a quantity is valued with `worth_for` (a bag of 20, an hour's loot), never as one unit's worth x the count.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .pricing import fmt_money, usual_sale

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
    crafted: int = 0                     # craft channel: what one unit is worth crafted (before the daily cap)
    craft_cap: float | None = None       # craft channel: units a day the recipe can use at that worth
    beyond: int = 0                      # craft channel: what each unit beyond the cap is worth (next best channel)
    cap_by: str = ''                     # 'cooldown' or 'market': what sets the cap
    disenchant: dict | None = None       # Engine.disenchant: a Classic-table estimate, shown, never the chosen channel


def capped_total(crafted: float, cap: float | None, beyond: float, qty: float) -> float:
    """qty units in a day: crafted worth for up to `cap` of them, `beyond` for the rest (cap None = no limit)."""
    if qty <= 0:
        return 0.0
    if cap is None:
        return crafted * qty
    made = min(qty, max(cap, 0.0))
    return crafted * made + beyond * (qty - made)


def per_day_text(n: float) -> str:
    """0.5 -> '1 every 2 days', 3.4 -> '3.4 a day'."""
    if n <= 0:
        return 'none a day'
    if n < 1:
        return f'1 every {1 / n:.0f} days' if 1 / n < 10 else f'1 every {1 / n:.0f} days (rarely)'
    return f'{n:.0f} a day' if n >= 10 else f'{n:.1f} a day'.replace('.0 a day', ' a day')


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
        """One unit's worth (a single unit of a capped craft counts at crafted worth only for its share of a day)."""
        return self.value(iid).value

    def worth_for(self, iid: int, qty: float) -> int:
        """What qty units are worth in a day: crafted worth only for as many as the recipe can use a day."""
        v = self.value(iid)
        if v.channel != 'craft':
            return int(v.value * qty)
        return int(capped_total(v.crafted, v.craft_cap, v.beyond, qty))

    def unit_worth(self, iid: int, qty: float) -> float:
        """Average worth of one unit when you get qty of them a day (an hour's loot: qty = per loot x loots an hour)."""
        v = self.value(iid)
        if v.channel != 'craft':
            return float(v.value)
        if qty <= 1e-9:
            return float(v.crafted if (v.craft_cap or 0) > 0 else v.beyond)
        return capped_total(v.crafted, v.craft_cap, v.beyond, qty) / qty

    def _value(self, iid: int, depth: int) -> Value:
        e = self.e
        item = e.gd.items.get(iid)
        channels, flags = {}, []
        sell, channel, q = e.sell_value(iid)
        if channel == 'AH' and q and {'no_sales_data', 'above_region'} & set(q.flags):
            # a lone listing far above the region (or no recorded sale at all) isn't a price you'd get: value
            # contents and catches at the actual sale price, or not on the AH at all if it never sold
            flags.append('ah_price_doubtful')
            sale = usual_sale(e.price(iid))
            sell = min(sell, int(sale * (1 - e.cut))) if sale else 0
        vendor = 0 if not item or 'sell_price' in getattr(item, 'untrusted', ()) else item.sell_price
        tradeable = not (item and (item.bonding == 1 or item.class_id == 12))     # soulbound or quest item
        if channel == 'AH' and sell > 0 and tradeable:
            channels['AH'] = sell
        if vendor:
            channels['vendor'] = vendor
        use = self.best_use.get(iid)
        if_skilled = None
        if use and use['value'] > max([0, use.get('doable_value') or 0] + list(channels.values())) and not use.get('doable'):
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
        crafted, cap, beyond, cap_by = 0, None, 0, ''
        if use and (use.get('doable_value') or 0) > 0:     # only recipes you can make now
            crafted, beyond = int(use['doable_value']), max([0] + list(channels.values()))
            cap = use.get('doable_units_per_day')
            cap_by = use.get('doable_cap_by') or 'market'
            # one unit: crafted worth for the share of it the recipe can use a day, the rest at the next best channel
            channels['craft'] = int(capped_total(crafted, cap, beyond, 1))
        de = e.disenchant(iid) if item and item.class_id in (2, 4) and item.quality >= 2 and hasattr(e, 'disenchant') else None
        if de and de['value'] > max([0] + list(channels.values())):
            flags.append('disenchant_more')
        if not channels:
            return Value(0, 'none', 'no known way to turn it into gold', tuple(flags + ['no_value']), {},
                         if_skilled=if_skilled, disenchant=de)
        best = max(channels, key=lambda k: channels[k])
        if best == 'open' and channels['open'] >= WORTH_OPENING * max(channels.get('AH', 0), vendor, 1):
            flags.append('open_it')
        if best == 'craft' and use and (use.get('doable_units_per_day') or 0) < CRAFT_DEMAND:
            flags.append('craft_limited_demand')    # beyond that many a day, it's worth its sale price
        how = {'AH': 'sell on the AH', 'vendor': 'sell to a vendor', 'open': 'open it',
               'craft': f"{use['doable_profession']}: {use['doable_recipe']}" if use else 'craft'}[best]
        if best == 'craft' and use and use.get('doable_capped'):
            # Engine.best_uses: never more than buying one costs; the craft's profit is on the craft's own row
            flags.append('crafted_at_buy_price')
            how += (f" (counted at what buying one costs on the AH, {fmt_money(use.get('buy_now') or crafted)}: one "
                    "you have only saves buying one; the craft's own profit is on its Crafting row)")
        if best == 'craft' and cap is not None and cap < CRAFT_DEMAND:
            why = "the recipe's cooldown" if cap_by == 'cooldown' else 'what its market takes at your share'
            how += (f' (worth {fmt_money(crafted)} crafted, for up to {per_day_text(cap)}: {why}; the rest at '
                    f'{fmt_money(beyond)} each)')
        if best != 'craft':
            crafted, cap, beyond, cap_by = 0, None, 0, ''
        return Value(channels[best], best, how, tuple(flags), channels, contents[:12], source, if_skilled,
                     crafted, cap, beyond, cap_by, de)
