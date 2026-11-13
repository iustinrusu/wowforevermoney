"""The money-making engine: turns items, recipes, vendors and prices into ranked opportunities.

Every opportunity carries a profit per unit, an estimate of units per day you can realistically move,
whether you can do it right now, and flags that explain any uncertainty. Money is in copper.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass, field

from . import fishing, pricing, skinning, valuation
from .pricing import Quote, ah_buy, ah_sell, liquidity, proceeds, sold_per_day

# Real professions a player can learn (excludes racials, riding, poisons, test lines).
PROFESSIONS = {'Alchemy', 'Blacksmithing', 'Cooking', 'Enchanting', 'Engineering', 'First Aid', 'Fishing',
               'Herbalism', 'Leatherworking', 'Mining', 'Skinning', 'Tailoring'}
GATHER_SOURCE = {5: 'Mobs (cloth)', 6: 'Skinning', 7: 'Mining', 8: 'Mobs (meat)', 9: 'Herbalism', 10: 'Mobs / gathering',
                 12: 'Enchanting'}
GATHER_PROFESSION = {6: 'Skinning', 7: 'Mining', 9: 'Herbalism'}
FISH_WORDS = re.compile(r'\b(Fish|Snapper|Lobster|Eel|Squid|Salmon|Sagefish|Yellowtail|Catfish|Mackerel|Grouper|'
                        r'Bass|Redgill|Mudfish|Albacore|Loach|Darter|Mightfish|Clam|Mullet|Smallfish|Whisker|'
                        r'Longjaw|Firefin|Blackmouth|Stonescale|Sunscale|Nightfin|Bristle|Trout|Perch|Bluegill|'
                        r'Mud Snapper|Raw .*Fin)\b')
EVENT_WORDS = ('holiday', 'festival', 'darkmoon', 'fireworks vendor', 'lunar', 'midsummer', 'winter veil',
               'hallow', 'brewfest', 'love is in the air', 'noblegarden', "children's week")
DARKMOON_ZONES = {12, 215}       # Elwynn Forest + Mulgore: where the Darkmoon Faire alternates
# How sure we are of an opportunity's numbers, from its flags (1 = no doubts). Used to rank picks, not to change
# the numbers shown: a pick with doubtful prices ranks below an equally good one with solid prices.
DOUBT = {'listed_far_above_sales': 0.8, 'slow_to_sell': 0.7, 'crowded': 0.7, 'sells_lower': 0.6, 'price_looks_off': 0.6, 'none_listed': 0.8, 'mat_not_listed': 0.8, 'small_sample': 0.8,
         'limited_mat': 0.9, 'limited_stock': 0.9, 'seasonal': 0.9, 'vendor_price_unconfirmed': 0.95,
         'skill_estimated': 0.95, 'assumed_rate': 0.95, 'assumed_kill_rate': 0.9, 'skins_partial': 0.95, 'snapshot': 0.9, 'craft_limited_demand': 0.8}


def vendor_sell(item) -> int:
    """What a vendor pays for one, or 0 if unknown or from a source the game showed is often wrong."""
    return 0 if not item or 'sell_price' in getattr(item, 'untrusted', ()) else item.sell_price


def confidence(flags) -> float:
    c = 1.0
    for f in set(flags):
        c *= DOUBT.get(f, 1.0)
    return round(c, 3)


# Ranking (Engine.rank). Score = expected profit x how sure we are x risk x can-do-now x problems x preference.
HOURLY_KINDS = ('fishing_spot', 'fishing_zone', 'farm_zone', 'skin_spot')
ONE_OFF_KINDS = ('realm_dip', 'ah_to_vendor')
PROBLEM_FLAGS = {'hard_to_sell', 'slow_seller', 'no_sales_data', 'unverified_recipe', 'above_region', 'black_market',
                 'event_vendor', 'classic_unconfirmed'}
PROBLEM_FACTOR = 0.2        # a flagged problem sinks a row below every clean one of similar profit
SKILL_GAP_FACTOR = 0.5      # your profession, but more skill needed
OTHER_PROFESSION_FACTOR = 0.25   # a profession you don't have
UNAFFORDABLE_SHARE = 0.1    # what more gold would add counts 10%: what you can afford now ranks first
RISK_WEIGHT = 0.05          # risking 20x the profit (if it doesn't sell) halves the score
PREFERRED_BONUS = 1.1

MAX_UNITS_PER_DAY = 200          # sanity cap when demand is effectively unlimited (e.g. selling to vendors)
COPPER_PER_GOLD = 10000


@dataclass
class Opportunity:
    kind: str                 # craft | vendor_flip | ah_to_vendor | realm_dip | gather | farm_zone | fishing_spot
    key: str                  # stable id for change tracking
    item_id: int
    title: str
    profit_unit: int          # copper profit per unit (or per craft / per cast)
    cost_unit: int            # copper needed up front per unit
    units_day: float          # estimated units/crafts you can move per day
    daily: int                # estimated copper profit per day
    gph: int | None = None    # copper per hour, when we know a rate
    doable: bool = True
    needs: str = ''
    profession: str | None = None
    preferred: bool = False
    flags: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    score: float = 0.0        # ranking score (Engine.rank): higher = do it first

    def to_dict(self) -> dict:
        return asdict(self)


class Engine:
    def __init__(self, world, settings: dict):
        self.w = world
        self.s = settings
        self.gd = world.gamedata
        self.prices = world.prices
        self.q = world.questie
        self.su = world.skillup
        self.cut = float(settings.get('ah_cut', 0.05))
        self.sale_basis = settings.get('sale_price_basis', 'min_buyout')   # see pricing.ah_sell
        self.share = float(settings.get('market_share', 0.2))
        self.gold = float(settings.get('gold', 0)) * COPPER_PER_GOLD
        self.profs = {k: int(v) for k, v in (settings.get('professions') or {}).items()}
        self.preferred = list(settings.get('preferred') or [])
        self.faction = settings.get('faction', 'H')
        self._vendor_cache: dict[int, tuple[int, list] | None] = {}
        self._vendor_flags: dict[int, tuple] = {}
        self._spell_to_recipe_items = self._index_recipe_items()
        self._valuer: valuation.Valuer | None = None

    # ---------- shared helpers ----------
    def name(self, iid: int) -> str:
        it = self.gd.items.get(iid)
        if it and it.name:
            return it.name
        qi = self.q.items.get(iid) if self.q else None
        return (qi or {}).get('name') or f'Item {iid}'

    def price(self, iid: int) -> dict | None:
        return self.prices.get(iid)

    def vendors_for(self, iid: int) -> list[dict]:
        out = []
        qi = self.q.items.get(iid) if self.q else None
        for npc_id in (qi or {}).get('vendors') or []:
            npc = self.q.npcs.get(npc_id, {})
            friendly = npc.get('friendlyToFaction') or ''
            if friendly and self.faction not in friendly:
                continue
            zone_id = npc.get('zoneID')
            spawn = None
            spawns = npc.get('spawns')
            spawn_zones = set(spawns) if isinstance(spawns, dict) else set()
            if isinstance(spawns, dict) and spawns:
                z, pts = next(iter(spawns.items()))
                zone_id = zone_id or z
                if pts:
                    spawn = pts[0]
            sub = str(npc.get('subName') or '').lower()
            # Event-only vendors: holiday vendors, and the Darkmoon Faire (its NPCs spawn in both Elwynn Forest
            # and Mulgore, where the Faire alternates). Vendors with no known spawn may not be reachable at all.
            event = any(w in sub for w in EVENT_WORDS) or DARKMOON_ZONES <= spawn_zones
            out.append({'npc': npc_id, 'name': npc.get('name', f'NPC {npc_id}'), 'zone': self.gd.zones.get(zone_id, ''),
                        'coords': spawn, 'friendly': friendly, 'stock': (self.su.limited_stock.get(iid) or {}).get(npc_id),
                        'event': event, 'located': bool(spawn_zones or zone_id)})
        return out

    def vendor_price(self, iid: int) -> tuple[int, list] | None:
        """(copper per unit, vendor list) if a vendor you can use sells this item.

        Questie's Forever database decides *whether* a vendor sells it (an old Classic list in SkillUpForever
        wrongly includes e.g. Refined Deeprock Salt). The price is ItemSparse BuyPrice / VendorStackCount.
        """
        if iid in self._vendor_cache:
            return self._vendor_cache[iid]
        result = None
        item = self.gd.items.get(iid)
        vendors = self.vendors_for(iid)
        seen = self.observed_vendor_price(iid, vendors)
        if seen is not None:
            result = (seen, vendors)
            self._vendor_flags[iid] = ('vendor_price_seen',)
        else:
            price = item.buy_price if item and item.buy_price > 0 else int(self.su.vendor_prices.get(iid, 0))
            if vendors and price > 0:
                # Game files hold a base price; Black Market agents charge far more (Frilled Lichen: 4g 50s, not
                # the file's 1s 20c, seen in game 2026-11-13). If only they sell it, the real price is unknown until
                # ForeverMoneyBridge sees it, so this vendor isn't used for flips or ingredient costs at all.
                black = ['black market' in str((self.q.npcs.get(v['npc']) or {}).get('subName', '')).lower()
                         for v in vendors]
                if all(black):
                    self._vendor_flags[iid] = ('black_market',)
                else:
                    result = (price, vendors)
                    self._vendor_flags[iid] = ('black_market',) if any(black) else ('vendor_price_unconfirmed',)
        if result and not any(v.get('located', True) and not v.get('event') for v in result[1]):
            # every vendor is event-only (Darkmoon Faire, holidays) or has no known location
            self._vendor_flags[iid] = self._vendor_flags.get(iid, ()) + ('event_vendor',)
        self._vendor_cache[iid] = result
        return result

    def observed_vendor_price(self, iid: int, vendors: list) -> int | None:
        """Cheapest per-unit price ForeverMoneyBridge actually saw at a vendor (money only, no token costs)."""
        seen = (getattr(self.w, 'profile', None) or {}).get('vendors') or {}
        prices = []
        for npc_id, v in seen.items():
            it = (v.get('items') or {}).get(iid)
            if it and it.get('price') and not it.get('ext'):
                prices.append(int(it['price']) / max(1, int(it.get('qty') or 1)))
        return int(round(min(prices))) if prices else None

    def vendor_flags(self, iid: int) -> tuple:
        self.vendor_price(iid)
        return self._vendor_flags.get(iid, ())

    def vendor_stock_cap(self, iid: int) -> int | None:
        """If every vendor you can use has limited stock, the most you can buy per restock."""
        vp = self.vendor_price(iid)
        if not vp:
            return None
        stocks = [v.get('stock') for v in vp[1]]
        if stocks and all(stocks):
            return max(stocks)
        return None

    def cheapest(self, iid: int) -> Quote | None:
        options = []
        vp = self.vendor_price(iid)
        if vp:
            cap = self.vendor_stock_cap(iid)
            flags = (('limited_stock',) if cap else ()) + tuple(f for f in self.vendor_flags(iid) if f == 'event_vendor')
            options.append(Quote(vp[0], 'vendor', flags))
        q = ah_buy(self.price(iid))
        if q:
            options.append(q)
        return min(options, key=lambda o: o.value) if options else None

    def sell_value(self, iid: int) -> tuple[int, str, Quote | None]:
        """Best of AH (after cut) and vendor, per unit. Returns (copper, channel, ah quote)."""
        item = self.gd.items.get(iid)
        q = ah_sell(self.price(iid), self.sale_basis)
        if item and (item.bonding == 1 or item.class_id == 12):
            q = None          # soulbound or quest item: it can't be sold on the AH, whatever TSM lists
        ah_val = proceeds(q, self.cut)
        vendor_val = vendor_sell(item)
        if ah_val >= vendor_val and ah_val > 0:
            return ah_val, 'AH', q
        return vendor_val, 'vendor', q

    def demand_per_day(self, iid: int, channel: str) -> float:
        if channel == 'vendor':
            return MAX_UNITS_PER_DAY
        return sold_per_day(self.price(iid)) * self.share

    def affordable(self, cost: int) -> float:
        if cost <= 0:
            return MAX_UNITS_PER_DAY
        return math.floor(self.gold / cost)

    def required_skill(self, recipe) -> tuple[int, bool]:
        th = self.su.thresholds.get(recipe.spell_id)
        if th and th[0] and th[0] > 1:
            return int(th[0]), True
        if recipe.trivial_low:
            return max(1, recipe.trivial_low - 40), False   # classic pattern: orange = yellow - 40
        return 1, False

    def _index_recipe_items(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for iid, qi in (self.q.items.items() if self.q else []):
            spell = qi.get('teachesSpell')
            if spell:
                out.setdefault(int(spell), []).append(iid)
        for scroll, spell in (self.su.recipe_scrolls or {}).items():
            if isinstance(spell, int):
                out.setdefault(spell, [])
                if scroll not in out[spell]:
                    out[spell].append(scroll)
        return out

    def learn_cost(self, recipe) -> dict | None:
        fee = self.su.trainer_fees.get(recipe.spell_id)
        if fee:
            return {'how': 'trainer', 'cost': int(fee[0]), 'skill': int(fee[1]) if len(fee) > 1 else None}
        best = None
        for scroll in self._spell_to_recipe_items.get(recipe.spell_id, []):
            q = self.cheapest(scroll)
            if q and (best is None or q.value < best['cost']):
                best = {'how': 'recipe item', 'item_id': scroll, 'name': self.name(scroll), 'cost': q.value,
                        'source': q.source}
            elif best is None:
                best = {'how': 'recipe item', 'item_id': scroll, 'name': self.name(scroll), 'cost': None,
                        'source': 'drop / not on AH'}
        return best

    # ---------- opportunity builders ----------
    def crafts(self) -> list[Opportunity]:
        out = []
        # Without SkillUpForever nothing can be verified: show every craft flagged "unverified recipe" (kept out of
        # Top picks) rather than an empty Crafting tab (a friend's install showed nothing at all, 2026-11-13).
        include_unverified = self.s.get('include_unverified_recipes', False) or not self.su.thresholds
        for r in self.gd.recipes:
            if r.profession not in PROFESSIONS or not r.reagents:
                continue
            verified = r.spell_id in self.su.thresholds
            if not verified and not include_unverified:
                continue
            mats, cost, unpriced = [], 0, []
            for mid, cnt in r.reagents:
                q = self.cheapest(mid)
                if not q:
                    unpriced.append(self.name(mid))
                    continue
                cost += q.value * cnt
                mats.append({'item_id': mid, 'name': self.name(mid), 'count': cnt, 'unit': q.value, 'source': q.source,
                             'flags': list(q.flags)})
            if unpriced:
                continue
            unit_val, channel, q = self.sell_value(r.product_id)
            revenue = int(unit_val * r.product_count)
            profit = revenue - cost
            if profit <= 0:
                continue
            crafts_demand = self.demand_per_day(r.product_id, channel) / max(r.product_count, 1)
            crafts_uncapped = min(crafts_demand, MAX_UNITS_PER_DAY)          # as if you had the gold for it
            mat_limit = None
            for m in mats:
                if m['source'] == 'vendor' and 'limited_stock' in m['flags']:
                    cap = self.vendor_stock_cap(m['item_id']) or 0
                    crafts_uncapped = min(crafts_uncapped, cap / m['count'])
                elif m['source'] != 'vendor':
                    # you can't buy more of an AH ingredient a day than its market trades at your share
                    cap = sold_per_day(self.price(m['item_id'])) * self.share / m['count']
                    if cap < crafts_uncapped:
                        crafts_uncapped, mat_limit = cap, m['name']
            crafts_day = min(crafts_uncapped, self.affordable(cost))
            req, exact = self.required_skill(r)
            have = self.profs.get(r.profession)
            flags = list(q.flags) if (q and channel == 'AH') else []
            if not verified:
                flags.append('unverified_recipe')
            if not exact:
                flags.append('skill_estimated')
            if channel == 'vendor':
                flags.append('sell_to_vendor')
            if any('none_listed' in m['flags'] for m in mats):
                flags.append('mat_not_listed')
            if any('limited_stock' in m['flags'] for m in mats):
                flags.append('limited_mat')
            if any('event_vendor' in m['flags'] for m in mats):
                flags.append('event_vendor')      # an ingredient is only sold during events
            if self.affordable(cost) < 1:
                flags.append('cant_afford')
            if have is None:
                needs, doable = f'Learn {r.profession}', False
                flags.append('other_profession')
            elif have < req:
                needs, doable = f'{r.profession} {req}{"" if exact else "~"} (you have {have})', False
            else:
                needs, doable = '', True
            product = self.gd.items.get(r.product_id)
            out.append(Opportunity(
                kind='craft', key=f'craft:{r.spell_id}', item_id=r.product_id,
                title=f'Craft {self.name(r.product_id)}' + (f' x{r.product_count:g}' if r.product_count != 1 else ''),
                profit_unit=profit, cost_unit=cost, units_day=round(crafts_day, 2), daily=int(profit * crafts_day),
                doable=doable, needs=needs, profession=r.profession, preferred=r.profession in self.preferred,
                flags=flags,
                detail={'recipe_spell': r.spell_id, 'recipe': r.name, 'mats': mats, 'revenue': revenue,
                        'sell_channel': channel, 'sell_source': q.source if q else 'vendor',
                        'product_count': r.product_count, 'skill_required': req, 'skill_exact': exact,
                        'thresholds': self.su.thresholds.get(r.spell_id), 'learn': self.learn_cost(r),
                        'req_level': product.req_level if product else 0,
                        'sold_per_day': sold_per_day(self.price(r.product_id)),
                        'daily_if_affordable': int(profit * crafts_uncapped), 'limited_by_mat': mat_limit}))
        return out

    def vendor_flips(self) -> list[Opportunity]:
        out = []
        candidates = set(self.su.vendor_prices) | {iid for iid, qi in (self.q.items.items() if self.q else [])
                                                   if qi.get('vendors')}
        for iid in candidates:
            vp = self.vendor_price(iid)
            if not vp:
                continue
            cost, vendors = vp
            if cost <= 0 or not vendors:
                continue
            q = ah_sell(self.price(iid), self.sale_basis)
            if not q:
                continue
            value = proceeds(q, self.cut)
            profit = value - cost
            if profit <= max(25, cost * 0.1):
                continue
            stock = [v['stock'] for v in vendors if v.get('stock')]
            demand = sold_per_day(self.price(iid)) * self.share
            units_uncapped = min(demand, MAX_UNITS_PER_DAY, max(stock) if stock else MAX_UNITS_PER_DAY)
            units = min(demand, self.affordable(cost), MAX_UNITS_PER_DAY)
            flags = list(q.flags) + [f for f in self.vendor_flags(iid) if f != 'vendor_price_seen']
            if stock:
                flags.append('limited_stock')
                units = min(units, max(stock))
            if self.affordable(cost) < 1:
                flags.append('cant_afford')
            item = self.gd.items.get(iid)
            out.append(Opportunity(
                kind='vendor_flip', key=f'vflip:{iid}', item_id=iid, title=f'Buy {self.name(iid)} from vendor, sell on AH',
                profit_unit=profit, cost_unit=cost, units_day=round(units, 2), daily=int(profit * units),
                doable=True, flags=flags,
                detail={'vendor_price': cost, 'ah_sell': q.value, 'ah_source': q.source, 'vendors': vendors[:8],
                        'vendor_count': len(vendors), 'limited_stock': max(stock) if stock else None,
                        'is_recipe': bool(item and item.class_id == 9),
                        'sold_per_day': sold_per_day(self.price(iid)),
                        'daily_if_affordable': int(profit * units_uncapped)}))
        return out

    def ah_to_vendor(self) -> list[Opportunity]:
        out = []
        for iid, p in self.prices.items():
            item = self.gd.items.get(iid)
            if not item or vendor_sell(item) <= 0 or not pricing.listed(p):     # unconfirmed vendor prices: no flip
                continue
            mb = int(p['minBuyout'])
            if mb >= item.sell_price:
                continue
            profit = item.sell_price - mb
            flags = ['snapshot'] + (['cant_afford'] if self.affordable(mb) < 1 else [])
            if p.get('marketValue') and p['marketValue'] < item.sell_price:
                flags.append('often_below_vendor')
            out.append(Opportunity(
                kind='ah_to_vendor', key=f'ah2v:{iid}', item_id=iid,
                title=f'Buy {self.name(iid)} on AH, sell to vendor',
                profit_unit=profit, cost_unit=mb, units_day=1, daily=profit, doable=True, flags=flags,
                detail={'min_buyout': mb, 'vendor_sell': item.sell_price, 'listings': p.get('numAuctions', 0)}))
        return out

    def realm_dips(self) -> list[Opportunity]:
        """A listing far below what the item has *recently* sold and listed for.

        The game launched in November 2026 and prices are still falling, so 60-day averages
        (historical) mostly reflect launch prices. The relist target is the lowest of: the realm's
        14-day market value, the region's market value, and the region's recorded average sale price.
        """
        out = []
        for iid, p in self.prices.items():
            if not pricing.listed(p):
                continue
            mb = int(p['minBuyout'])
            refs = [v for v in (p.get('marketValue', 0), p.get('regionMarketValue', 0), p.get('regionSale', 0)) if v]
            if len(refs) < 3 or p.get('regionSoldPerDay', 0) < 2 or p.get('regionSalePercent', 0) < 0.15:
                continue
            target = min(refs)
            if mb >= 0.6 * target:
                continue
            profit = int(target * (1 - self.cut)) - mb
            if profit <= max(100, mb * 0.3):
                continue
            out.append(Opportunity(
                kind='realm_dip', key=f'dip:{iid}', item_id=iid,
                title=f'Buy cheap {self.name(iid)} and relist',
                profit_unit=profit, cost_unit=mb, units_day=1, daily=profit, doable=True,
                flags=['risky', 'snapshot'] + (['cant_afford'] if self.affordable(mb) < 1 else []),
                detail={'min_buyout': mb, 'realm_market': p.get('marketValue', 0),
                        'region_market': p.get('regionMarketValue', 0), 'region_sale': p.get('regionSale', 0),
                        'relist_at': target, 'listings': p.get('numAuctions', 0),
                        'sold_per_day': p.get('regionSoldPerDay', 0), 'sale_rate': p.get('regionSalePercent', 0)}))
        return out

    def best_uses(self) -> dict[int, dict]:
        """For every reagent: the most a unit is worth when crafted into something (value per unit of it).

        'value'/'recipe' is the best recipe overall; 'doable_value'/'doable_recipe' the best one you can make
        now. What something is worth to you today uses the doable one (a recipe needing more skill would
        overstate it); the other shows what levelling would add."""
        best: dict[int, dict] = {}
        for r in self.gd.recipes:
            if r.profession not in PROFESSIONS or r.spell_id not in self.su.thresholds:
                continue
            unit_val, channel, _ = self.sell_value(r.product_id)
            revenue = unit_val * r.product_count
            costs = {}
            ok = True
            for mid, cnt in r.reagents:
                q = self.cheapest(mid)
                if not q:
                    ok = False
                    break
                costs[mid] = q.value * cnt
            if not ok:
                continue
            req, _ = self.required_skill(r)
            have = self.profs.get(r.profession)
            can = have is not None and have >= req
            for mid, cnt in r.reagents:
                if self.vendor_price(mid):
                    continue   # vendor mats aren't "your" materials
                val = (revenue - (sum(costs.values()) - costs[mid])) / cnt
                entry = {'value': int(val), 'recipe': r.name, 'product': self.name(r.product_id),
                         'profession': r.profession, 'doable': can, 'skill': req}
                cur = best.get(mid)
                if cur is None:
                    cur = best[mid] = dict(entry, doable_value=None, doable_recipe=None, doable_profession=None)
                elif val > cur['value']:
                    cur.update(entry)
                if can and (cur['doable_value'] is None or val > cur['doable_value']):
                    cur['doable_value'], cur['doable_recipe'], cur['doable_profession'] = int(val), r.name, r.profession
                    # how many units of this material a day the product's market can absorb at your share
                    cur['doable_units_per_day'] = round(sold_per_day(self.price(r.product_id)) * self.share * cnt
                                                        / max(r.product_count, 1), 1)
        return best

    def gathering(self, best_use: dict[int, dict]) -> list[Opportunity]:
        out = []
        rates = {int(k): float(v) for k, v in (self.s.get('farm_rates') or {}).items()}
        made = {r.product_id for r in self.gd.recipes}
        for iid, item in self.gd.items.items():
            # processed goods are crafted, not farmed: cooked food/potions, cured hides, cloth bolts. (Some crafted
            # items are also gathered, e.g. Heavy Leather is skinned too, so being craftable alone isn't enough.)
            if iid in made and (item.class_id == 0 or item.name.startswith(('Cured ', 'Bolt of '))):
                continue
            is_fish = bool(FISH_WORDS.search(item.name)) and item.class_id in (0, 7, 15) and item.quality <= 2
            if not is_fish and not (item.class_id == 7 and item.subclass_id in GATHER_SOURCE):
                continue
            p = self.price(iid)
            if not p:
                continue
            sell, channel, q = self.sell_value(iid)
            use = best_use.get(iid)
            value, how = sell, f'Sell ({channel})'
            if use and (use.get('doable_value') or 0) > value:
                value, how = use['doable_value'], f"{use['doable_profession']}: {use['doable_recipe']}"
            if value <= 0:
                continue
            source = 'Fishing' if is_fish else GATHER_SOURCE.get(item.subclass_id, 'Gathering')
            prof = 'Fishing' if is_fish else GATHER_PROFESSION.get(item.subclass_id)
            doable = prof is None or prof in self.profs
            demand = sold_per_day(p) * self.share
            rate = rates.get(iid)
            out.append(Opportunity(
                kind='gather', key=f'gather:{iid}', item_id=iid, title=f'Farm {item.name}',
                profit_unit=value, cost_unit=0, units_day=round(demand, 2), daily=int(value * demand),
                gph=int(value * rate) if rate else None, doable=doable,
                needs='' if doable else f'Learn {prof}', profession=prof, preferred=prof in self.preferred,
                flags=list(q.flags) if q else [],
                detail={'source': source, 'best_use': how, 'sell_value': sell, 'craft_use': use,
                        'sell_channel': channel if value == sell else 'craft',
                        'sold_per_day': sold_per_day(p), 'your_rate_per_hour': rate,
                        'drops_from': len((self.q.items.get(iid) or {}).get('npcDrops') or []) if self.q else 0}))
        return out

    def activity_zones(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Measured gold/hour per zone and activity, from ForeverMoneyBridge's loot log (real active time)."""
        out = []
        activity = (getattr(self.w, 'profile', None) or {}).get('activity') or {}
        label = {'fishing': 'Fish', 'skinning': 'Skin', 'herbalism': 'Gather herbs', 'mining': 'Mine', 'mobs': 'Kill mobs'}
        prof = {'fishing': 'Fishing', 'skinning': 'Skinning', 'herbalism': 'Herbalism', 'mining': 'Mining'}
        for zone, acts in activity.items():
            for act, a in (acts or {}).items():
                seconds = float(a.get('seconds') or 0)
                loots = int(a.get('loots') or 0)
                if loots <= 0:
                    continue
                total, rows = 0, []
                for iid, count in (a.get('items') or {}).items():
                    iid = int(iid)
                    val = self.fish_value(iid, best_use)
                    total += val * int(count)
                    rows.append({'item_id': iid, 'name': self.name(iid), 'count': int(count), 'value': val,
                                 'share': round(int(count) / loots, 3)})
                rows.sort(key=lambda r: -r['value'] * r['count'])
                gph = int(total / seconds * 3600) if seconds >= 300 else None
                flags = ['measured'] if gph else ['not_enough_time']
                if loots < 30:
                    flags.append('small_sample')
                out.append(Opportunity(
                    kind='fishing_zone' if act == 'fishing' else 'farm_zone', key=f'zone:{act}:{zone}',
                    item_id=rows[0]['item_id'] if rows else 0, title=f'{label.get(act, act)} in {zone}',
                    profit_unit=int(total / loots), cost_unit=0, units_day=0, daily=0, gph=gph,
                    doable=act not in prof or prof[act] in self.profs, profession=prof.get(act),
                    preferred=prof.get(act) in self.preferred, flags=flags,
                    detail={'zone': zone, 'activity': act, 'loots': loots, 'minutes': round(seconds / 60, 1),
                            'fish': rows, 'casts': loots, 'caught': loots, 'got_away': 0, 'source': 'ForeverMoneyBridge'}))
        return out

    def skinning_spots(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Skinning spots per zone from Wowhead Forever "Skinned from" counts (see skinning.py)."""
        table = skinning.mobs(getattr(self.w, 'forever_skinning', None) or {})
        if not table:
            return []
        level = int(self.s.get('level', 1) or 1)
        skill = self.profs.get('Skinning')
        pace, minutes = skinning.measured_pace((getattr(self.w, 'profile', None) or {}).get('activity'))
        per_hour = pace or float(self.s.get('kills_per_hour', 60) or 60)
        value_of = lambda iid: self.fish_value(iid, best_use)
        out = []
        for sp in skinning.spots(table, value_of, lambda z: self.gd.zones.get(z, f'zone {z}'), skill, level):
            if sp['value'] <= 0:
                continue
            usable = [m for m in sp['mobs'] if m['can_skin'] and m['can_kill']]
            top = (usable or sp['mobs'])[:3]
            flags = ['wowhead_forever', 'skins_partial', 'skill_classic_rule',
                     'measured_pace' if pace else 'assumed_kill_rate']
            if sp['skins'] < skinning.SOLID_SAMPLE:
                flags.append('small_sample')
            needs = ''
            if not sp['doable']:
                if skill is None:
                    needs = 'Learn Skinning'
                elif skill < sp['skill_needed']:
                    needs = f'Skinning {sp["skill_needed"]} (you have {skill}; Classic rule)'
                else:
                    needs = f'level {max(1, sp["min_level"] - skinning.LEVEL_REACH)}+ (you are {level})'
            best_item = max(top[0]['items'], key=lambda i: top[0]['items'][i] * value_of(i)) if top else 0
            mobs = [{'npc': m['npc'], 'name': m['name'], 'levels': f"{m['min_level']}-{m['max_level']}",
                     'skinned': m['skinned'], 'value': m['value'], 'skill_needed': m['skill_needed'],
                     'can_skin': m['can_skin'], 'can_kill': m['can_kill'],
                     'items': sorted(({'item_id': i, 'name': self.name(i), 'share': round(s, 3), 'value': value_of(i)}
                                      for i, s in m['items'].items()), key=lambda x: -x['share'] * x['value'])}
                    for m in sp['mobs'][:12]]
            out.append(Opportunity(
                kind='skin_spot', key=f'skin:{sp["zone_id"]}', item_id=best_item,
                title=f'Skin in {sp["zone"]}: ' + ', '.join(m['name'] for m in top),
                profit_unit=sp['value'], cost_unit=0, units_day=0, daily=0, gph=int(sp['value'] * per_hour),
                doable=sp['doable'], needs=needs, profession='Skinning', preferred='Skinning' in self.preferred,
                flags=flags,
                detail={'zone': sp['zone'], 'zone_id': sp['zone_id'], 'mobs': mobs, 'skins': sp['skins'],
                        'levels': f"{sp['min_level']}-{sp['max_level']}", 'skins_per_hour': round(per_hour, 1),
                        'pace_source': f'measured ({minutes:.0f} min of your skinning)' if pace else 'your skins-per-hour setting',
                        'source': 'Wowhead Forever "Skinned from" counts'}))
        return out

    def valuer(self, best_use: dict[int, dict] | None = None) -> valuation.Valuer:
        """Item values through every channel (AH, vendor, crafting, opening it), built once per run."""
        if self._valuer is None or (best_use is not None and self._valuer.best_use is not best_use):
            contents = valuation.merge_contents(getattr(self.w, 'forever_containers', None),
                                                (getattr(self.w, 'profile', None) or {}).get('containers'))
            self._valuer = valuation.Valuer(self, best_use if best_use is not None else {}, contents)
        return self._valuer

    def fish_value(self, iid: int, best_use: dict[int, dict]) -> int:
        """What one looted item is worth: the best of selling, crafting and opening it (see valuation.py)."""
        return self.valuer(best_use).worth(iid)

    def fishing_spots(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Fishing, zone by zone, Forever data first.

        Every zone with Forever data (your catches, Wowhead Forever counts) gets one row from that data. While
        the Forever sample is small it's blended with the zone's Classic table that matches it. Every other
        Classic table becomes a "Classic table: ..." row, marked unconfirmed for Forever.
        """
        cf = getattr(self.w, 'classic_fishing', None)
        obs = fishing.observations(self.w.angler, (getattr(self.w, 'profile', None) or {}).get('activity'))
        fishing.add_wowhead(obs, getattr(self.w, 'forever_fishing', None))
        skill = int(self.profs.get('Fishing') or 0)
        seasons = fishing.forever_seasons(cf, getattr(self.w, 'forever_fishing', None)) if cf else {}
        spots = fishing.build_spots(cf, self.gd, seasons=seasons) if cf else {}
        # fish whose season is over (by Forever catches, else the Classic calendar) don't count in Forever data
        out_of_season = set()
        if cf:
            for eid, items in fishing.seasonal_items(cf).items():
                active = seasons.get(eid) if eid in seasons else cf.event_status(eid)[0]
                if active is False:
                    out_of_season |= items
        pools = fishing.pool_items(cf) if cf else {}
        zone_by_name: dict[str, int] = {}
        for zid, rows in spots.items():
            zone_by_name.setdefault(rows[0].zone, zid)
        table_items = {i for rows in spots.values() for s in rows for i in s.shares}
        pool_only = set(pools) - table_items
        use_own = bool(self.s.get('own_logs_for_rates', False))
        with_pools = bool(self.s.get('fishing_pools', False))

        def counts(o) -> dict:
            """Forever catches used for drop rates: Wowhead Forever, plus your own logs only if you opted in.
            Pool-only loot (trunks, Stranglekelp, Rumsey Rum) is set aside unless you count pools: pools have to
            be found first, so open water is the honest default. Each pool-only item ~ one pool catch."""
            items = dict(o.items) if use_own else {}
            for i, c in o.wh_items.items():
                items[i] = items.get(i, 0) + c
            n_all = (o.caught if use_own else 0) + o.wh_fished
            for i in out_of_season & set(items):         # caught last season: not catchable now
                n_all -= items.pop(i)
            pool = {i: c for i, c in items.items() if i in pool_only}
            if with_pools:
                return {'n': n_all, 'items': items, 'n_all': n_all, 'items_all': items, 'pool': pool}
            n = max(0, n_all - sum(pool.values()))
            return {'n': n, 'items': {i: c for i, c in items.items() if i not in pool}, 'n_all': n_all,
                    'items_all': items, 'pool': pool}

        fc = {name: counts(o) for name, o in obs.items()}

        def match(zid, o):
            """The zone's Classic table explaining at least half of the Forever catches (pool-only loot such as
            trunks doesn't count either way), among the tables your skill can fish."""
            relevant = {i: c for i, c in fc[o.zone]['items'].items() if i not in pool_only}
            total = sum(relevant.values())

            def explained(s):
                return sum(c for i, c in relevant.items() if i in s.shares and not s.shares[i]['quest'])

            cands = [s for s in spots.get(zid, []) if s.coverage >= 0.5 and (s.skill is None or s.skill <= skill)]
            best = max(cands, key=lambda s: (explained(s), not s.names), default=None)
            return best if best and total and explained(best) / total >= fishing.MATCH_MIN else None

        matched = {name: match(zone_by_name.get(name), o) for name, o in obs.items() if fc[name]['n']}

        def zone_skill_of(name):
            zid = zone_by_name.get(name)
            return (matched.get(name) or spots[zid][0]).skill if zid is not None else None

        model = fishing.catch_model(obs, zone_skill_of, float(self.s.get('casts_per_hour', 240)))
        values: dict[int, int] = {}

        def val(iid):
            if iid not in values:
                values[iid] = self.fish_value(iid, best_use)
            return values[iid]

        out = []
        for name, o in obs.items():
            if fc[name]['n']:
                zid = zone_by_name.get(name)
                out.append(self._fishing_row(name, zid, matched.get(name), o, model, skill, val, spots.get(zid, []),
                                             pools, zone_skill_of(name), fc[name], use_own, with_pools))
        for zid, zone_spots in spots.items():
            name = zone_spots[0].zone
            for spot in zone_spots:
                if spot is not matched.get(name):
                    out.append(self._fishing_row(name, zid, spot, None, model, skill, val, zone_spots, pools, spot.skill,
                                                 None, use_own, with_pools))
        return out

    def _fishing_row(self, zone, zid, spot, o, model, skill, val, zone_spots, pools, zone_skill, fc=None,
                     use_own=False, with_pools=False) -> Opportunity:
        """One row. o = Forever data for the zone (a Forever row), or None (a Classic-only row for spot)."""
        forever = o is not None
        n = fc['n'] if forever else 0
        w = (1.0 if spot is None else n / (n + fishing.PRIOR_CATCHES)) if forever else 0.0
        classic = {i: s['share'] for i, s in (spot.shares.items() if spot else ())}
        quest = {i for i, s in (spot.shares.items() if spot else ()) if s['quest']}
        items = fc['items'] if forever else {}
        observed = {i: c / n for i, c in items.items()} if n else {}
        rows, value, classic_value, observed_value, seasonal_value = [], 0.0, 0.0, 0.0, 0.0
        for iid in set(classic) | set(observed):
            v = 0 if iid in quest else val(iid)
            share = w * observed.get(iid, 0.0) + (1 - w) * classic.get(iid, 0.0)
            value += share * v
            classic_value += classic.get(iid, 0.0) * v
            observed_value += observed.get(iid, 0.0) * v
            info = spot.shares.get(iid, {}) if spot else {}
            if info.get('seasonal'):
                seasonal_value += share * v
            rows.append({'item_id': iid, 'name': self.name(iid), 'value': v, 'share': round(share, 4),
                         'classic_share': round(classic[iid], 4) if iid in classic else None,
                         'observed_share': round(observed[iid], 4) if iid in observed else None,
                         'count': o.items.get(iid, 0) if forever and use_own else 0,
                         'wowhead_count': o.wh_items.get(iid, 0) if forever else 0, 'quest': iid in quest,
                         'seasonal': info.get('seasonal'), 'in_season': info.get('in_season'),
                         'pools': pools.get(iid, []) if iid not in classic else [],
                         'how': self.valuer().value(iid).how, 'value_flags': list(self.valuer().value(iid).flags)})
        rows.sort(key=lambda r: -(r['share'] * r['value']))
        unknown_containers = [r for r in rows if 'contents_unknown' in r['value_flags'] and r['share'] >= 0.005]

        keep, keep_src = model.keep(zone, zone_skill, skill, use_zone=forever)
        cph, pace = model.catches_per_hour(keep), model.pace_source
        if forever and o.timed_catches and o.seconds >= 300:
            cph, pace = o.timed_catches / o.seconds * 3600, 'measured here'
        doable = keep > 0
        classic_items = {i for s in zone_spots for i in s.shares}
        new_fish = [{'item_id': i, 'name': self.name(i), 'count': c, 'share': round(c / n, 4)}
                    for i, c in items.items() if zid is not None and c >= fishing.NEW_FISH_MIN
                    and c / n >= fishing.NEW_FISH_SHARE and i not in classic_items and i not in pools]
        new_fish.sort(key=lambda f: -f['count'])
        missing = [{'item_id': i, 'name': self.name(i), 'classic_share': round(s['share'], 3)}
                   for i, s in (spot.shares.items() if forever and spot and n >= fishing.MISSING_N else ())
                   if s['share'] >= fishing.MISSING_SHARE and not s['quest'] and not items.get(i)]
        top = rows[0]['item_id'] if rows else 0
        confirmed_by = []
        if forever and use_own and o.caught >= 10:
            confirmed_by.append('your catches')
        # pool loot: what the Forever data says it adds per catch, kept out of the headline unless counted
        pool_rows, pool_value, value_with_pools = [], 0.0, None
        if forever and fc['pool'] and fc['n_all']:
            for i, c in sorted(fc['pool'].items(), key=lambda kv: -kv[1] * val(kv[0])):
                pool_rows.append({'item_id': i, 'name': self.name(i), 'count': c, 'share': round(c / fc['n_all'], 4),
                                  'value': val(i)})
                pool_value += c / fc['n_all'] * val(i)
            open_part = sum(c / fc['n_all'] * val(i) for i, c in fc['items_all'].items() if i not in fc['pool'])
            value_with_pools = int(open_part + pool_value)
        if forever and o.wh_fished >= fishing.WOWHEAD_CONFIRM:
            confirmed_by.append('Wowhead Forever')

        flags = []
        if not forever:
            flags.append('classic_unconfirmed')
        elif zid is None:
            flags.append('forever_only')
        if forever and o.wh_fished:
            flags.append('wowhead_forever')
        if forever and fc['pool'] and not with_pools:
            flags.append('pools_extra')
        if forever and o.wh_checked:
            try:
                age_days = (time.time() - time.mktime(time.strptime(o.wh_checked, '%Y-%m-%d'))) / 86400
            except ValueError:
                age_days = 0
            if age_days > fishing.SNAPSHOT_MAX_DAYS:
                flags.append('old_snapshot')
        if spot and spot.coverage < fishing.INCOMPLETE and w < 0.5:
            flags.append('classic_incomplete')
        if forever and 0 < n < fishing.PRIOR_CATCHES:
            flags.append('small_sample')
        if value and seasonal_value / value >= 0.1:
            flags.append('seasonal')
        if new_fish or missing:
            flags.append('forever_change')
        if keep_src.startswith('Classic') and keep < 1:
            flags.append('classic_getaway')
        flags.append('measured' if pace == 'measured here' else ('assumed_rate' if pace == 'setting' else 'measured_pace'))
        if spot and spot.dungeon:
            flags.append('dungeon')
        if unknown_containers:
            flags.append('contents_unknown')

        several = len(zone_spots) > 1
        if forever:
            title, key = f'Fish in {zone}', (f'fish:zone:{zid}' if zid is not None else f'fish:log:{zone}')
        else:
            title, key = f'Classic table: {spot.label(several)}', f'fish:{zid}:{spot.areas[0]}'
        return Opportunity(
            kind='fishing_spot', key=key, item_id=top, title=title, profit_unit=int(value), cost_unit=0,
            units_day=0, daily=0, gph=round(value * cph) if doable else None, doable=doable,
            needs='' if doable else f'Fishing {zone_skill} (Classic zone skill)', profession='Fishing', preferred=True,
            flags=flags,
            detail={'zone': zone, 'zone_id': zid, 'forever': forever,
                    'classic_spot': spot.label(several) if spot else None,
                    'subzones': spot.names if spot else [], 'areas': spot.areas if spot else [],
                    'zone_skill': zone_skill, 'your_skill': skill, 'keep': round(keep, 3), 'keep_source': keep_src,
                    'landed_share': model.landed_share, 'casts_per_hour': round(model.casts_per_hour),
                    'catches_per_hour': round(cph), 'pace_source': pace,
                    'coverage': round(spot.coverage, 3) if spot else None,
                    'weight': round(w, 3), 'value_per_catch': int(value),
                    'classic_value': int(classic_value) if spot else None,
                    'observed_value': int(observed_value) if n else None,
                    'gph_if_skilled': int(value * model.catches_per_hour(1.0)),
                    'fish': rows[:40], 'casts': o.casts if forever else 0, 'caught': o.caught if forever else 0,
                    'got_away': o.escaped if forever else 0, 'forever_catches': n,
                    'wowhead_fished': o.wh_fished if forever else 0, 'wowhead_checked': o.wh_checked if forever else '',
                    'wowhead_url': o.wh_url if forever else '',
                    'own_logs_used': use_own, 'pools_counted': with_pools,
                    'pool_loot': pool_rows[:8], 'pool_share': round(sum(fc['pool'].values()) / fc['n_all'], 4)
                    if forever and fc['n_all'] else 0,
                    'value_with_pools': value_with_pools,
                    'gph_with_pools': round(value_with_pools * cph) if value_with_pools and doable else None,
                    'sources': (o.sources if forever else []) + (['Classic (cMaNGOS classic-db)'] if spot else []),
                    'new_in_forever': new_fish, 'classic_missing': missing, 'confirmed_by': confirmed_by,
                    'dungeon': bool(spot and spot.dungeon)})

    # ---------- undervaluation watch ----------
    WATCH_ORDER = {'contents_unknown': 0, 'no_value': 1, 'open_it': 2, 'ah_price_doubtful': 3}

    def undervaluation_watch(self) -> list[dict]:
        """Items you loot, carry or catch whose value may be wrong: openable with unknown contents, no way to turn
        them into gold, or an AH price with no sales behind it; plus items worth more opened than sold."""
        v = self.valuer()
        seen: dict[int, set] = {}

        def add(iid, where):
            seen.setdefault(int(iid), set()).add(where)

        for acts in ((getattr(self.w, 'profile', None) or {}).get('activity') or {}).values():
            for act, a in (acts or {}).items():
                for iid in (a or {}).get('items') or {}:
                    add(iid, f'your {act} loot')
        for z in ((getattr(self.w, 'angler', None) or {}).get('zones') or {}).values():
            for iid in (z.get('fish') if isinstance(z, dict) and isinstance(z.get('fish'), dict) else {}):
                add(iid, 'your catches')
        for z in (getattr(self.w, 'forever_fishing', None) or {}).values():
            for iid in z.get('items') or {}:
                add(iid, 'fishing (Wowhead Forever)')
        for inv in (getattr(self.w, 'inventory', None) or {}).values():
            for iid in inv:
                add(iid, 'your bags')
        out = []
        for iid, where in seen.items():
            val = v.value(iid)
            issue = next((f for f in self.WATCH_ORDER if f in val.flags), None)
            it = self.gd.items.get(iid)
            if issue == 'no_value' and it and (it.class_id == 12 or it.bonding == 1):
                continue      # quest items and soulbound items with no vendor price really are worth 0 in gold
            if issue:
                out.append({'item_id': iid, 'name': self.name(iid), 'issue': issue, 'value': val.value, 'how': val.how,
                            'channels': val.channels, 'where': sorted(where), 'contents_source': val.contents_source})
        out.sort(key=lambda u: (self.WATCH_ORDER[u['issue']], -u['value']))
        return out

    def rank(self, o: Opportunity, later: bool = False) -> tuple[float, dict]:
        """Ranking score and its parts (shown in the row's details).

        later=True ranks by what a pick earns once you have the gold and skill (the "unlock" sections).
        """
        conf = confidence(o.flags)
        if o.kind in HOURLY_KINDS:
            base, basis = (o.gph or 0), 'gold per hour'
        elif o.kind in ONE_OFF_KINDS:
            base, basis = o.profit_unit, 'profit on the purchase'
        else:
            potential = max(o.daily, o.detail.get('daily_if_affordable', o.daily))
            if later:
                base, basis = potential, 'profit per day once you have the gold'
            else:
                base = o.daily + UNAFFORDABLE_SHARE * (potential - o.daily)
                basis = 'profit per day' + (' (+ 10% of what more gold would add)' if potential > o.daily else '')
        item = self.gd.items.get(o.item_id)
        salvage = vendor_sell(item) * (o.detail.get('product_count') or 1)
        downside = max(0, o.cost_unit - salvage) if o.kind not in HOURLY_KINDS else 0
        risk = 1 / (1 + RISK_WEIGHT * downside / max(o.profit_unit, 1)) if downside else 1.0
        doable = 1.0 if (o.doable or later) else (
            OTHER_PROFESSION_FACTOR if 'other_profession' in o.flags else SKILL_GAP_FACTOR)
        problems = sorted(set(o.flags) & PROBLEM_FLAGS)
        problem = PROBLEM_FACTOR if problems else 1.0
        pref = PREFERRED_BONUS if o.preferred else 1.0
        score = max(0.0, base) * conf * risk * doable * problem * pref
        return score, {'basis': basis, 'base': int(base), 'confidence': conf, 'risk': round(risk, 3),
                       'downside': downside, 'doable': doable, 'problems': problems, 'preferred': pref,
                       'score': round(score, 1)}

    # ---------- everything ----------
    def run(self) -> dict:
        best_use = self.best_uses()
        # fishing logs (with time) feed the fishing spots below; other activities get their own measured rows
        measured = [o for o in self.activity_zones(best_use) if o.kind != 'fishing_zone']
        all_opps = (self.crafts() + self.vendor_flips() + self.ah_to_vendor() + self.realm_dips()
                    + self.gathering(best_use) + measured + self.fishing_spots(best_use)
                    + self.skinning_spots(best_use))
        min_spd = float(self.s.get('min_sold_per_day', 0.5))
        for o in all_opps:
            # anything you'd sell on the AH: does it actually sell? (hard to sell: never suggested)
            if (o.kind in ('craft', 'vendor_flip', 'gather', 'realm_dip')
                    and o.detail.get('sell_channel') not in ('vendor', 'craft')):
                liq = liquidity(self.price(o.item_id), min_spd)
                o.detail['liquidity'] = liq
                o.flags.extend(f for f in liq['flags'] if f not in o.flags)
        for o in all_opps:
            o.detail['confidence'] = confidence(o.flags)
            o.score, o.detail['rank'] = self.rank(o)
        return {'opportunities': all_opps, 'best_use': best_use, 'top': self.top_picks(all_opps),
                'undervalued': self.undervaluation_watch()}

    @staticmethod
    def _varied(ranked: list[Opportunity], n: int, per_kind: int) -> list[str]:
        """The best n keys, at most per_kind of each kind (so one activity can't fill a section)."""
        seen: dict[str, int] = {}
        out = []
        for o in ranked:
            if seen.get(o.kind, 0) < per_kind:
                seen[o.kind] = seen.get(o.kind, 0) + 1
                out.append(o.key)
            if len(out) == n:
                break
        return out

    def top_picks(self, opps: list[Opportunity], n: int = 15) -> dict:
        bonus = float(self.s.get('switch_bonus', 1.5))
        bad = {'hard_to_sell', 'slow_seller', 'no_sales_data', 'cant_afford', 'unverified_recipe', 'above_region', 'black_market',
               'event_vendor'}

        def clean(o, allow_unaffordable=False):
            return not (set(o.flags) & (bad - {'cant_afford'} if allow_unaffordable else bad))

        for o in opps:
            o.detail['confidence'] = confidence(o.flags)
            if not o.detail.get('rank'):
                o.score, o.detail['rank'] = self.rank(o)
        # "Unlock by levelling" and "switch professions" are about later: what you can afford today doesn't hide them
        later = [o for o in opps if o.kind in ('craft', 'vendor_flip') and clean(o, allow_unaffordable=True)]
        daily = [o for o in later if clean(o)]
        own = [o for o in daily if o.doable]
        best_own = max((o.daily for o in own), default=0)
        stretch = [o for o in later if not o.doable and 'other_profession' in o.flags
                   and o.detail.get('daily_if_affordable', o.daily) >= bonus * best_own]
        # snipes you can afford first, then the rest (still shown, flagged "can't afford")
        speculative = [o for o in opps if o.kind in ('realm_dip', 'ah_to_vendor') and clean(o, allow_unaffordable=True)]
        # data from another WoW version can't reach top picks until Forever data confirms it
        # (a fishing spot needs confirming Forever data and 30+ Forever catches: a few lucky trunks in a
        # small sample can make a zone look 3x better than it is)
        hourly = [o for o in opps if o.gph and o.doable and 'classic_unconfirmed' not in o.flags
                  and (o.kind != 'fishing_spot' or (o.detail.get('confirmed_by') and 'small_sample' not in o.flags))
                  and (o.kind != 'skin_spot' or 'small_sample' not in o.flags)]
        # ranked by Engine.rank: profit x how sure we are x risk x can-do-now x problems x preference
        key = lambda o: o.score
        # sections about later rank by what a pick earns once you have the gold and skill for it
        later_key = lambda o: self.rank(o, later=True)[0]
        return {
            'now': [o.key for o in sorted(own, key=key, reverse=True)[:n]],
            'level_up': [o.key for o in sorted((o for o in later if not o.doable and 'other_profession' not in o.flags),
                                               key=later_key, reverse=True)[:n]],
            'switch': [o.key for o in sorted(stretch, key=later_key, reverse=True)[:5]],
            'hourly': self._varied(sorted(hourly, key=key, reverse=True), n, per_kind=5),
            'snipes': [o.key for o in sorted(speculative, key=lambda o: ('cant_afford' in o.flags, -o.score))[:n]],
        }
