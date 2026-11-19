"""The money-making engine: turns items, recipes, vendors and prices into ranked opportunities.

Every opportunity carries a profit per unit, an estimate of units per day you can realistically move,
whether you can do it right now, and flags that explain any uncertainty. Money is in copper.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass, field

from . import anomalies, fishing, gamedata, nodes, plan, pricing, skinning, valuation, wowhead_items
from . import everloot as everloot_mod
from . import levelling as levelling_mod
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
DOUBT = {'price_check': 0.7, 'price_check_fails': 0.4, 'listed_far_above_sales': 0.8, 'sale_price_outlier': 0.7, 'slow_to_sell': 0.7, 'crowded': 0.7, 'sells_lower': 0.6, 'price_looks_off': 0.6, 'none_listed': 0.8, 'mat_not_listed': 0.8, 'small_sample': 0.8,
         'limited_mat': 0.9, 'limited_stock': 0.9, 'seasonal': 0.9, 'vendor_price_unconfirmed': 0.95,
         'skill_estimated': 0.95, 'tool_unchecked': 0.9, 'assumed_rate': 0.95, 'assumed_kill_rate': 0.9, 'skins_partial': 0.95, 'classic_yields': 0.85, 'dungeon': 0.6, 'snapshot': 0.9, 'craft_limited_demand': 0.8}


def vendor_sell(item) -> int:
    """What a vendor pays for one, or 0 if unknown or from a source the game showed is often wrong."""
    return 0 if not item or 'sell_price' in getattr(item, 'untrusted', ()) else item.sell_price


def confidence(flags) -> float:
    c = 1.0
    for f in set(flags):
        c *= DOUBT.get(f, 1.0)
    return round(c, 3)


# Ranking (Engine.rank). Score = expected profit x how sure we are x risk x can-do-now x problems x preference.
HOURLY_KINDS = ('fishing_spot', 'fishing_zone', 'farm_zone', 'skin_spot', 'herb_spot', 'mine_spot', 'mob_spot')
ELITE = {1, 2, 3}          # Wowhead classification (Questie rank): elite, rare elite, boss; 4 = rare
ONE_OFF_KINDS = ('realm_dip', 'ah_to_vendor')
PROBLEM_FLAGS = {'not_worth_time', 'hard_to_sell', 'slow_seller', 'no_sales_data', 'unverified_recipe', 'above_region', 'black_market',
                 'event_vendor', 'classic_unconfirmed'}
PROBLEM_FACTOR = 0.2        # a flagged problem sinks a row below every clean one of similar profit
SKILL_GAP_FACTOR = 0.5      # your profession, but more skill needed
OTHER_PROFESSION_FACTOR = 0.25   # a profession you don't have
UNAFFORDABLE_SHARE = 0.1    # what more gold would add counts 10%: what you can afford now ranks first
RISK_WEIGHT = 0.05          # risking 20x the profit (if it doesn't sell) halves the score
PREFERRED_BONUS = 1.1
# Effort: estimated seconds of your play time (shown in the app as estimates)
POST_SECONDS = 10            # post one auction (or one stack)
BUY_SECONDS = 15             # buy one ingredient type on the AH
CRAFT_SECONDS = 3            # one craft
VENDOR_TRIP_SECONDS = 120    # go to a vendor and back, once a day
POST_STACK = 5               # stackable items are posted a few at a time
TIME_VALUE_SHARE = 0.5       # AH and crafting time is worth half of what your best farming earns an hour
DEFAULT_TIME_VALUE = 20000   # 2g an hour when no Forever-backed farming spot is known
DAILY_ROUTINE = 1.0         # "Daily routines" (was "Do these now") need about one sale a day or more; slower = occasional flip

COOLDOWN_MIN_MS = 10 * 60 * 1000   # a recipe cooldown of 10+ minutes limits how many you can make a day


def cooldown_per_day(recipe) -> float | None:
    """Most crafts a day a recipe's cooldown allows (Transmute: Arcanite 47 h: 0.51), or None if no cooldown."""
    ms = getattr(recipe, 'cooldown_ms', 0) or 0
    return 86_400_000 / ms if ms >= COOLDOWN_MIN_MS else None


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
        self.sale_basis = settings.get('sale_price_basis', 'realm')   # see pricing.ah_sell
        self.share = float(settings.get('market_share', 0.2))
        self.gold = float(settings.get('gold', 0)) * COPPER_PER_GOLD
        self.time_value = DEFAULT_TIME_VALUE
        self.time_value_source = 'default'
        self.profs = {k: int(v) for k, v in (settings.get('professions') or {}).items()}
        self.preferred = list(settings.get('preferred') or [])
        self.faction = settings.get('faction', 'H')
        self._vendor_cache: dict[int, tuple[int, list] | None] = {}
        self._vendor_flags: dict[int, tuple] = {}
        self._spell_to_recipe_items = self._index_recipe_items()
        self._valuer: valuation.Valuer | None = None
        # things made by using a tool you keep (the Salt Shaker), not by a recipe: product -> its recipe
        self.tool_made = {r.product_id: r for r in self.gd.recipes if getattr(r, 'tool_id', 0)}

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
            listed = (self.su.limited_stock.get(iid) or {}).get(npc_id)
            seen = (((getattr(self.w, 'profile', None) or {}).get('vendors') or {}).get(npc_id) or {}).get('items') or {}
            seen_stock = (seen.get(iid) or {}).get('stock')
            if listed is None and seen_stock is not None and seen_stock > 0:
                listed = int(seen_stock)       # limited, as the addon saw it (what was left then: a floor)
            out.append({'npc': npc_id, 'name': npc.get('name', f'NPC {npc_id}'), 'zone': self.gd.zones.get(zone_id, ''),
                        'coords': spawn, 'friendly': friendly, 'stock': listed,
                        'stock_known': listed is not None or seen_stock is not None,
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
        if getattr(recipe, 'tool_id', 0):          # a tool's own skill requirement (game data): Salt Shaker 250
            return max(1, recipe.min_rank), True
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

    def owns(self, iid: int) -> bool | None:
        """Does the character you play have this item in bags, bank or equipped (Syndicator)? None: bags not read."""
        syn = getattr(self.w, 'syndicator', None) or {}
        key = plan.character_key(syn, self.character())
        if not key:
            return None
        have = set((getattr(self.w, 'inventory', None) or {}).get(key) or {}) | set(syn[key].get('equipped') or {})
        return iid in have

    def learn_cost(self, recipe) -> dict | None:
        tool = getattr(recipe, 'tool_id', 0)
        if tool:                    # nothing to learn: you need the tool once (it is not used up)
            q = self.cheapest(tool)
            return {'how': 'tool', 'item_id': tool, 'name': self.name(tool), 'cost': q.value if q else None,
                    'source': q.source if q else 'not on AH / vendor', 'owned': self.owns(tool)}
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

    def levelling(self, profession: str, skill: int | None = None, known: set[int] | None = None,
                  crafts: list | None = None, target: int = levelling_mod.MAX_SKILL) -> dict:
        """The cheapest way from your skill (or any skill) to a target skill, 300 by default, in a crafting profession
        (levelling.py), and what it unlocks on the way (crafts: this run's craft rows, for their profit once you have
        the skill)."""
        skill = int(skill if skill is not None else (self.profs.get(profession) or 1))
        target = max(skill + 1, min(int(target), levelling_mod.MAX_SKILL))
        min_spd = float(self.s.get('min_sold_per_day', 0.5))
        own_kinds = {sub for sub, prof in GATHER_PROFESSION.items() if prof in self.profs}
        options = []
        for r in self.gd.recipes:
            th = self.su.thresholds.get(r.spell_id)
            if r.profession != profession or not th or len(th) < 4 or not th[3]:
                continue
            # SkillUpForever stores 0/1 as the orange threshold when it doesn't know it: the engine's estimate then
            # (yellow - 40), never "craftable from skill 1" (Heavy Scorpid Bracers needs 255)
            orange = int(th[0]) if th[0] and th[0] > 1 else self.required_skill(r)[0]
            colors = (orange, int(th[1]), int(th[2]), int(th[3]))
            mats, cost, ok = [], 0, True
            for mid, cnt in r.reagents:
                it = self.gd.items.get(mid)
                q = self.cheapest(mid)
                own = bool(it and it.class_id == 7 and it.subclass_id in own_kinds)
                each = q.value if q else None
                if own:          # a material you gather yourself costs what you'd get for selling it
                    sold = self.sell_value(mid)[0]
                    each = sold if sold > 0 else each
                if each is None:
                    ok = False
                    break
                mats.append((mid, cnt, int(each), own))
                cost += each * cnt
            if not ok:
                continue
            item = self.gd.items.get(r.product_id)
            q = ah_sell(self.price(r.product_id), self.sale_basis)
            sells = q and item and item.bonding != 1 and not ({'hard_to_sell', 'no_sales_data'} &
                                                            set(liquidity(self.price(r.product_id), min_spd)['flags']))
            ah_value = int(proceeds(q, self.cut) * r.product_count) if sells else 0
            learn = self.learn_cost(r)
            if learn is None:                # starting recipes (orange at 1) come with the profession
                learn_cost = 0 if orange <= 1 else None
            else:                            # a recipe item that is not on the AH (a drop) can't be bought
                learn_cost = None if learn.get('cost') is None else int(learn['cost'])
            options.append(levelling_mod.Option(
                spell_id=r.spell_id, name=r.name, colors=colors, ingredients=int(cost),
                ah_value=ah_value, vendor_value=int(vendor_sell(item) * r.product_count),
                ah_cap=sold_per_day(self.price(r.product_id)) * self.share * levelling_mod.WEEK / max(r.product_count, 1),
                learn=learn_cost,
                learn_how=(learn or {}).get('how', 'starting recipe' if orange <= 1 else ''), product_id=r.product_id,
                mats=mats))
        out = levelling_mod.plan(options, skill, target, known=known)
        for st in out['steps']:
            st['product'] = self.name(st['product_id'])
            st['mats'] = [{'item_id': m, 'name': self.name(m), 'count': c, 'each': e, 'own': own}
                          for m, c, e, own in st['mats']]
        unlocks = []
        for o in crafts or []:
            req = o.detail.get('skill_required') or 0
            if o.kind == 'craft' and o.profession == profession and skill < req <= target \
                    and not (set(o.flags) & {'hard_to_sell', 'no_sales_data', 'price_check_fails', 'unverified_recipe'}):
                at = next((st['cumulative'] for st in out['steps'] if st['to'] >= req), None)
                unlocks.append({'skill': req, 'title': o.title, 'item_id': o.item_id, 'key': o.key,
                                'daily': int(o.detail.get('daily_if_affordable', o.daily) or 0),
                                'profit_unit': o.profit_unit, 'cost_to_reach': at})
        unlocks.sort(key=lambda u: -u['daily'])
        out.update(profession=profession, unlocks=unlocks[:12], options=len(options),
                   known=len(known or ()), own_materials=sorted(GATHER_PROFESSION[k] for k in own_kinds))
        return out

    # ---------- opportunity builders ----------
    def crafts(self) -> list[Opportunity]:
        out = []
        # Without SkillUpForever nothing can be verified: show every craft flagged "unverified recipe" (kept out of
        # Top picks) rather than an empty Crafting tab (a friend's install showed nothing at all, 2026-11-13).
        include_unverified = self.s.get('include_unverified_recipes', False) or not self.su.thresholds
        for r in self.gd.recipes:
            if r.profession not in PROFESSIONS or not r.reagents:
                continue
            tool = getattr(r, 'tool_id', 0)
            verified = r.spell_id in self.su.thresholds or bool(tool)     # a tool's use comes from the game data
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
                made = self.tool_made.get(mid)
                if made:          # Refined Deeprock Salt: costed at what it sells for, but your Salt Shaker makes it
                    mats[-1]['made_with'] = {'tool': self.name(made.tool_id), 'tool_id': made.tool_id,
                                             'key': f'craft:{made.spell_id}',
                                             'cooldown_hours': round(made.cooldown_ms / 3_600_000, 2)}
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
            per_cooldown = cooldown_per_day(r)
            if per_cooldown is not None and per_cooldown < crafts_uncapped:
                crafts_uncapped, mat_limit = per_cooldown, None
            crafts_day = min(crafts_uncapped, self.affordable(cost))
            req, exact = self.required_skill(r)
            have = self.profs.get(r.profession)
            flags = list(q.flags) if (q and channel == 'AH') else []
            if not verified:
                flags.append('unverified_recipe')
            if per_cooldown is not None:
                flags.append('cooldown')
                if getattr(r, 'cooldown_group', ''):
                    flags.append('shared_cooldown')
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
            owned = self.owns(tool) if tool else None
            if tool and owned is False:
                flags.append('needs_tool')
                if doable:
                    needs, doable = f'Get a {self.name(tool)} (once: you keep it)', False
            elif tool and owned is None:
                flags.append('tool_unchecked')
            product = self.gd.items.get(r.product_id)
            count_text = f' x{r.product_count:g}' if r.product_count != 1 else ''
            out.append(Opportunity(
                kind='craft', key=f'craft:{r.spell_id}', item_id=r.product_id,
                title=(f'{self.name(tool)}: make {self.name(r.product_id)}{count_text}' if tool
                       else f'Craft {self.name(r.product_id)}{count_text}'),
                profit_unit=profit, cost_unit=cost, units_day=round(crafts_day, 2), daily=int(profit * crafts_day),
                doable=doable, needs=needs, profession=r.profession, preferred=r.profession in self.preferred,
                flags=flags,
                detail={'recipe_spell': r.spell_id,
                        'recipe': f'use your {self.name(tool)} to make {self.name(r.product_id)}' if tool else r.name,
                        'tool': {'item_id': tool, 'name': self.name(tool), 'owned': owned} if tool else None,
                        'mats': mats, 'revenue': revenue,
                        'sell_channel': channel, 'sell_source': q.source if q else 'vendor',
                        'sell_price': q.value if (q and channel == 'AH') else None,
                        'product_count': r.product_count, 'skill_required': req, 'skill_exact': exact,
                        'thresholds': self.su.thresholds.get(r.spell_id), 'learn': self.learn_cost(r),
                        'req_level': product.req_level if product else 0,
                        'sold_per_day': sold_per_day(self.price(r.product_id)),
                        'daily_if_affordable': int(profit * crafts_uncapped), 'limited_by_mat': mat_limit,
                        'cooldown_hours': round(r.cooldown_ms / 3_600_000, 2) if per_cooldown is not None else None,
                        'cooldown_group': getattr(r, 'cooldown_group', '') or None,
                        'cooldown_shared_with': sum(1 for x in self.gd.recipes if x is not r and getattr(r, 'cooldown_group', '')
                                                    and getattr(x, 'cooldown_group', '') == r.cooldown_group)}))
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
            stock_unknown = not any(v.get('stock_known') for v in vendors)
            demand = sold_per_day(self.price(iid)) * self.share
            units_uncapped = min(demand, MAX_UNITS_PER_DAY, max(stock) if stock else MAX_UNITS_PER_DAY)
            units = min(demand, self.affordable(cost), MAX_UNITS_PER_DAY)
            flags = list(q.flags) + [f for f in self.vendor_flags(iid) if f != 'vendor_price_seen']
            if stock:
                flags.append('limited_stock')
                units = min(units, max(stock))
            if stock_unknown and not stock:
                flags.append('stock_unknown')      # no list or visit says how many the vendor has
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
        min_spd = float(self.s.get('min_sold_per_day', 0.5))
        for r in self.gd.recipes:
            if r.profession not in PROFESSIONS or r.spell_id not in self.su.thresholds:
                # tools too (the Salt Shaker): one use every 71 h, and Deeprock Salt costs 3s on the AH, so the profit
                # belongs to the tool's own row, not to every Deeprock Salt you hold or farm
                continue
            unit_val, channel, _ = self.sell_value(r.product_id)
            if channel == 'AH' and {'hard_to_sell', 'no_sales_data'} & set(liquidity(self.price(r.product_id), min_spd)['flags']):
                # a product that (barely) never sells adds nothing to its ingredients: Delicate Arcanite Converter
                # (0 sold a day in the region) made Ironweb Spider Silk "worth 18g 11s if crafted" instead of ~30s
                continue
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
            # how many crafts a day the product's market takes at your share (and its cooldown allows)
            # (a product sold to a vendor has no market limit: the usual sanity cap of MAX_UNITS_PER_DAY)
            crafts = self.demand_per_day(r.product_id, channel) / max(r.product_count, 1)
            per_cooldown = cooldown_per_day(r)
            cap_by = 'market'
            if per_cooldown is not None and per_cooldown < crafts:
                crafts, cap_by = per_cooldown, 'cooldown'

            for mid, cnt in r.reagents:
                if self.vendor_price(mid):
                    continue   # vendor mats aren't "your" materials
                val = (revenue - (sum(costs.values()) - costs[mid])) / cnt
                entry = {'value': int(val), 'recipe': r.name, 'product': self.name(r.product_id),
                         'profession': r.profession, 'doable': can, 'skill': req,
                         'units_per_day': round(crafts * cnt, 2), 'cap_by': cap_by}
                cur = best.get(mid)
                if cur is None:
                    cur = best[mid] = dict(entry, doable_value=None, doable_recipe=None, doable_profession=None)
                elif val > cur['value']:
                    cur.update(entry)
                if can and (cur['doable_value'] is None or val > cur['doable_value']):
                    cur['doable_value'], cur['doable_recipe'], cur['doable_profession'] = int(val), r.name, r.profession
                    # what the product's market absorbs at your share (or the cooldown allows), in units of this
                    # ingredient: crafted worth holds only for that many a day (valuation.capped_total)
                    cur['doable_units_per_day'] = round(crafts * cnt, 2)
                    cur['doable_cap_by'] = cap_by
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
            if iid in self.tool_made and not (self.q and any((self.q.items.get(iid) or {}).get(k)
                                                             for k in ('npcDrops', 'objectDrops', 'itemDrops'))):
                continue      # Refined Deeprock Salt: only the Salt Shaker makes it ("Farm" it showed 187g a day)
            is_fish = bool(FISH_WORDS.search(item.name)) and item.class_id in (0, 7, 15) and item.quality <= 2
            if not is_fish and not (item.class_id == 7 and item.subclass_id in GATHER_SOURCE):
                continue
            if not is_fish and self.sold_by_vendor(iid):
                continue          # a vendor sells it (Silken Thread): you'd buy it, not farm it (event vendors aside)
            p = self.price(iid)
            if not p:
                continue
            sell, channel, q = self.sell_value(iid)
            use = best_use.get(iid)
            demand = sold_per_day(p) * self.share
            rate = rates.get(iid)
            value, how, cap = sell, f'Sell ({channel})', None
            if use and (use.get('doable_value') or 0) > value:
                value, how = use['doable_value'], f"{use['doable_profession']}: {use['doable_recipe']}"
                cap = use.get('doable_units_per_day')
                if cap is not None and cap < valuation.CRAFT_DEMAND:
                    how += f' (crafted worth for up to {valuation.per_day_text(cap)}; the rest sold)'
            if value <= 0:
                continue
            # crafted worth only for as many a day as the recipe can use; the rest at the sale price (2026-11-15)
            daily = valuation.capped_total(value, cap, sell, demand)
            unit = daily / demand if demand > 0 else valuation.capped_total(value, cap, sell, 1)
            source = 'Fishing' if is_fish else GATHER_SOURCE.get(item.subclass_id, 'Gathering')
            prof = 'Fishing' if is_fish else GATHER_PROFESSION.get(item.subclass_id)
            doable = prof is None or prof in self.profs
            out.append(Opportunity(
                kind='gather', key=f'gather:{iid}', item_id=iid, title=f'Farm {item.name}',
                profit_unit=int(unit), cost_unit=0, units_day=round(demand, 2), daily=int(daily),
                gph=int(valuation.capped_total(value, cap, sell, rate)) if rate else None, doable=doable,
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
                # never a gold/hour: time logged in a zone includes questing, travel and breaks (user, 2026-11-14)
                gph = None
                flags = ['your_log']
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
        for m in table.values():          # item pages' rows carry ids only: names and levels from QuestieDB (Forever)
            qn = (self.q.npcs.get(m['npc']) if self.q else None) or {}
            m['name'] = m['name'] or qn.get('name') or f"mob {m['npc']}"
            if not m['max_level']:
                m['min_level'], m['max_level'] = qn.get('minLevel') or 0, qn.get('maxLevel') or 0
        level = int(self.s.get('level', 1) or 1)
        skill = self.profs.get('Skinning')
        # pace is the setting only: your logged skinning time includes questing and travel (user, 2026-11-14)
        per_hour = float(self.s.get('kills_per_hour', 60) or 60)
        value_of = lambda iid, share=1.0: self.loot_worth(iid, best_use, share, per_hour)
        # skinning items Wowhead Forever pages are not read for yet (the flag goes once all are read)
        not_read = list(((getattr(self.w, 'forever_skinning', None) or {}).get('not_read') or {}).values())
        out = []
        for sp in skinning.spots(table, value_of, lambda z: self.gd.zones.get(z, f'zone {z}'), skill, level):
            if sp['value'] <= 0:
                continue
            usable = [m for m in sp['mobs'] if m['can_skin'] and m['can_kill']]
            top = (usable or sp['mobs'])[:3]
            flags = ['wowhead_forever'] + (['skins_partial'] if not_read else []) + ['skill_classic_rule', 'assumed_kill_rate']
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
            best_item = max(top[0]['items'], key=lambda i: top[0]['items'][i] * value_of(i, top[0]['items'][i])) if top else 0
            mobs = [{'npc': m['npc'], 'name': m['name'], 'levels': f"{m['min_level']}-{m['max_level']}",
                     'skinned': m['skinned'], 'value': m['value'], 'skill_needed': m['skill_needed'],
                     'can_skin': m['can_skin'], 'can_kill': m['can_kill'],
                     'items': sorted(({'item_id': i, 'name': self.name(i), 'share': round(s, 3), 'value': value_of(i, s)}
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
                        'pace_source': 'your skins-per-hour setting', 'skins_not_read': not_read,
                        'source': 'Wowhead Forever "Skinned from" counts'}))
        return out

    def mob_spots(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Mob farming, one row per mob: Wowhead Forever "Dropped by" counts from item pages read by hand (only those
        items: a floor until the mob's own page is read), plus a skin if you can skin it. Kills per hour: Settings."""
        mobs = wowhead_items.mob_drops(getattr(self.w, 'forever_pages', None) or {})
        # Everloot fills gaps where Wowhead Forever has no rate (30+ loot windows only, labelled, never Top picks)
        everloot_mod.fill_mob_gaps(mobs, getattr(self.w, 'everloot', None) or {})
        if not mobs:
            return []
        q, gd = self.q, self.gd
        skins = skinning.mobs(getattr(self.w, 'forever_skinning', None) or {})
        level = int(self.s.get('level', 1) or 1)
        skill = self.profs.get('Skinning')
        per_hour = float(self.s.get('kills_per_hour', 60) or 60)    # the setting only, never your logged time
        out = []
        for npc, m in mobs.items():
            qn = (q.npcs.get(npc) if q else None) or {}
            sk = skins.get(npc)
            skin_need = skinning.skill_needed(sk['max_level']) if sk else None
            can_skin = bool(sk) and skill is not None and skill >= skin_need
            # what one kill gives of each item (drops, and the skin if you can skin it): an hour's loot sets how many
            # of an item count at its crafted worth (loot_worth)
            per_kill = dict(m['items'])
            if can_skin:
                for i, share in sk['items'].items():
                    per_kill[i] = per_kill.get(i, 0) + share
            skin_items = (sk or {}).get('items') or {}
            value_of = lambda i: self.loot_worth(i, best_use, per_kill.get(i) or skin_items.get(i, 0), per_hour)
            from_everloot = m.get('everloot_items') or set()
            drops = sorted(({'item_id': i, 'name': self.name(i), 'per_kill': round(c, 4), 'value': value_of(i),
                             'count': m['counts'][i][0], 'looted': m['counts'][i][1],
                             'source': 'Everloot' if i in from_everloot else 'Wowhead Forever'}
                            for i, c in m['items'].items()),
                           key=lambda d: -d['per_kill'] * d['value'])
            drop_value = sum(d['per_kill'] * d['value'] for d in drops)
            skin_value = sum(share * value_of(i) for i, share in skin_items.items())
            value = drop_value + (skin_value if can_skin else 0)
            if value <= 0:
                continue
            lo = m['min_level'] or qn.get('minLevel') or (sk or {}).get('min_level')
            hi = m['max_level'] or qn.get('maxLevel') or (sk or {}).get('max_level')
            zone = next((z for z in m['zones'] if z and z > 0), None) or qn.get('zoneID')
            cls = m['classification'] if m['classification'] is not None else qn.get('rank')
            name = qn.get('name') or m['name'] or f'mob {npc}'
            can_kill = bool(hi) and hi <= level + skinning.LEVEL_REACH
            flags = (['wowhead_forever'] if len(from_everloot) < len(m['items']) else []) + ['kills_from_settings']
            if from_everloot:
                flags.append('everloot')
            if not m['complete']:
                flags.append('drops_partial')
            if m['small_sample']:
                flags.append('small_sample')
            if cls in ELITE:
                flags.append('elite')
            if zone and gamedata.is_instance(gd, zone):
                flags.append('dungeon')
            if sk and not can_skin:
                flags.append('skin_extra')
            needs = '' if can_kill else (f'level {max(1, hi - skinning.LEVEL_REACH)}+ (you are {level})' if hi
                                         else 'its level is unknown')
            zname = gd.zones.get(zone, f'zone {zone}') if zone else 'unknown zone'
            out.append(Opportunity(
                kind='mob_spot', key=f'mob:{npc}', item_id=drops[0]['item_id'] if drops else 0,
                title=f'Kill {name} in {zname}', profit_unit=int(value), cost_unit=0, units_day=0, daily=0,
                # elites, bosses and dungeon mobs can't be killed at the kills-per-hour pace: value per kill only
                gph=None if {'elite', 'dungeon'} & set(flags) else int(value * per_hour),
                doable=can_kill, needs=needs, profession=None, preferred=False, flags=flags,
                detail={'npc': npc, 'zone': zname, 'zone_id': zone, 'levels': f'{lo or "?"}-{hi or "?"}',
                        'classification': cls, 'looted': m['looted'], 'drops': drops[:12],
                        'drop_value': int(drop_value), 'skin_value': int(skin_value), 'can_skin': can_skin,
                        'skin_needed': skin_need, 'kills_per_hour': round(per_hour, 1),
                        'pace_source': 'your kills-per-hour setting', 'read': m['read'],
                        'source': 'Wowhead Forever "Dropped by" counts' + (' and "Skinned from" counts' if sk else '')}))
        return out

    def node_spots(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Herbalism and mining spots: Forever node locations (QuestieDB), Classic node loot (labelled)."""
        q, gd = self.q, self.gd
        if not q:
            return []
        herb_names = {it.name for it in gd.items.values() if it.class_id == 7 and it.subclass_id == 9}
        main: dict[int, int] = {}
        for iid, qi in q.items.items():
            it = gd.items.get(iid)
            if not it or it.class_id != 7 or it.subclass_id not in (7, 9):
                continue
            for o in qi.get('objectDrops') or []:
                if nodes.node_kind((q.objects.get(o) or {}).get('name', ''), herb_names):
                    main.setdefault(o, iid)
        if not main:
            return []         # no herb or ore nodes known (and never rebuild the node cache for an empty list)
        loot = nodes.load_or_build(set(main)) or {}
        forever = wowhead_items.object_yields(getattr(self.w, 'forever_pages', None) or {})
        # nodes an hour (the settings only, never your logged time): an hour's loot sets how many of an item count at
        # its crafted worth (loot_worth)
        node_rate = {'herbalism': float(self.s.get('herb_nodes_per_hour', 40) or 40),
                     'mining': float(self.s.get('ore_nodes_per_hour', 40) or 40)}
        node_list = []
        for oid, iid in main.items():
            ob = q.objects.get(oid) or {}
            spawns = ob.get('spawns') or {}
            zones = {int(z): len(c) for z, c in spawns.items()} if isinstance(spawns, dict) else {}
            classic = (loot.get('nodes') or {}).get(str(oid))
            classic_items = nodes.per_node(classic, loot.get('refs') or {}) if classic else {}
            fy = forever.get(oid)
            uses = float((classic or {}).get('uses') or 1.0)
            items, src = nodes.combine(classic_items, fy, uses, iid)
            rate = node_rate.get(nodes.node_kind(ob.get('name', ''), herb_names), 40.0)
            worth = {i: self.loot_worth(i, best_use, c, rate) for i, c in items.items()}
            value = sum(c * worth[i] for i, c in items.items())
            classic_value = sum(c * worth[i] for i, c in items.items() if src[i] != 'forever')
            node_list.append({'id': oid, 'name': ob.get('name', ''), 'kind': nodes.node_kind(ob.get('name', ''), herb_names),
                              'skill': nodes.node_skill(ob.get('name', '')), 'zones': zones, 'classic_loot': bool(classic),
                              'items': items, 'sources': src, 'value': int(value), 'uses': uses, 'worth': worth,
                              'forever_share': round(1 - classic_value / value, 3) if value > 0 else 0.0,
                              'forever_looted': (fy or {}).get('looted', 0),
                              'forever_complete': bool((fy or {}).get('complete')),
                              'small_sample': bool(fy and fy.get('small_sample'))})
        activity = (getattr(self.w, 'profile', None) or {}).get('activity')
        out = []
        for kind, prof, label, setting in (('herbalism', 'Herbalism', 'Gather herbs in', 'herb_nodes_per_hour'),
                                           ('mining', 'Mining', 'Mine in', 'ore_nodes_per_hour')):
            skill = self.profs.get(prof)
            per_hour = node_rate[kind]
            for sp in nodes.spots([n for n in node_list if n['kind'] == kind], lambda z: gd.zones.get(z, f'zone {z}'), skill):
                if sp['value'] <= 0:
                    continue
                top = [n for n in sp['nodes'] if n['can']][:3] or sp['nodes'][:3]
                counted = [n for n in sp['nodes'] if not n['rare']] or sp['nodes']
                # Top picks only once nothing counted here rests on Classic yields (Forever data only, user's rule)
                all_forever = all(n['forever_share'] >= 0.999 for n in counted)
                any_forever = any(n['forever_share'] > 0 for n in counted)
                flags = ['wowhead_forever' if all_forever else 'classic_yields', 'skill_classic_rule', 'assumed_node_rate']
                if any_forever and not all_forever:
                    flags.append('forever_yields_partial')
                if any_forever and any(n['uses'] != 1.0 for n in counted if n['forever_share'] > 0):
                    flags.append('classic_gathers')
                if any(n['small_sample'] for n in counted if n['forever_share'] > 0):
                    flags.append('small_sample')
                if gamedata.is_instance(gd, sp['zone_id']):
                    flags.append('dungeon')
                if any(n['rare'] for n in sp['nodes']):
                    flags.append('rare_nodes_extra')
                if skill is None:
                    flags.append('other_profession')
                if not all(n['classic_loot'] for n in sp['nodes']):
                    flags.append('yield_unknown')
                needs = '' if sp['doable'] else (f'Learn {prof}' if skill is None else
                                                 f'{prof} {sp["skill_needed"]} (you have {skill}; Classic rule)')
                best_item = max(top[0]['items'], key=lambda i: top[0]['items'][i] * top[0]['worth'][i]) if top else 0
                out.append(Opportunity(
                    kind='herb_spot' if kind == 'herbalism' else 'mine_spot', key=f'{kind}:{sp["zone_id"]}',
                    item_id=best_item, title=f'{label} {sp["zone"]}: ' + ', '.join(n['name'] for n in top),
                    profit_unit=sp['value'], cost_unit=0, units_day=0, daily=0, gph=int(sp['value'] * per_hour),
                    doable=sp['doable'], needs=needs, profession=prof, preferred=prof in self.preferred, flags=flags,
                    detail={'zone': sp['zone'], 'zone_id': sp['zone_id'], 'node_count': sp['node_count'],
                            'nodes_per_hour': round(per_hour, 1),
                            'pace_source': 'your nodes-per-hour setting',
                            'nodes': [{'id': n['id'], 'name': n['name'], 'count': n['count'], 'skill': n['skill'],
                                       'can': n['can'], 'rare': n['rare'], 'value': n['value'],
                                       'classic_loot': n['classic_loot'], 'forever_share': n['forever_share'],
                                       'forever_looted': n['forever_looted'], 'forever_complete': n['forever_complete'],
                                       'gathers_per_node': n['uses'],
                                       'items': sorted(({'item_id': i, 'name': self.name(i), 'per_node': round(c, 2),
                                                         'value': n['worth'][i], 'source': n['sources'].get(i, 'classic')}
                                                        for i, c in n['items'].items()),
                                                       key=lambda x: -x['per_node'] * x['value'])[:6]}
                                      for n in sp['nodes'][:10]],
                            'source': 'node locations: QuestieDB (Forever); items per node: '
                                      + ('Wowhead Forever pages read by hand' if all_forever else
                                         'Wowhead Forever pages where read, the rest WoW Classic loot tables'
                                         if any_forever else 'WoW Classic loot tables')}))
        return out

    def valuer(self, best_use: dict[int, dict] | None = None) -> valuation.Valuer:
        """Item values through every channel (AH, vendor, crafting, opening it), built once per run."""
        if self._valuer is None or (best_use is not None and self._valuer.best_use is not best_use):
            contents = valuation.merge_contents(getattr(self.w, 'forever_containers', None),
                                                (getattr(self.w, 'profile', None) or {}).get('containers'))
            self._valuer = valuation.Valuer(self, best_use if best_use is not None else {}, contents)
        return self._valuer

    def fishing_bonus(self) -> tuple[int, str]:
        """Fishing skill added by your pole, lure and fishing gear: a number set in Settings, else worked out from what
        the character you play has in bags, bank and equipped (Syndicator; user's request 2026-11-14)."""
        fixed = self.s.get('fishing_skill_bonus')
        if fixed not in (None, ''):
            return int(fixed), 'your setting'
        syn = getattr(self.w, 'syndicator', None) or {}
        key = plan.character_key(syn, self.character())
        if not key:
            return 0, 'no bags read (needs Syndicator)'
        have = set((getattr(self.w, 'inventory', None) or {}).get(key) or {}) | set(syn[key].get('equipped') or {})
        bonus, parts = fishing.skill_bonus(have, self.gd.items)
        return bonus, ('from your things: ' + ', '.join(parts) + ' (values from Forever tooltips)') if parts else             'nothing in your bags, bank or gear raises Fishing'

    def fishing_lure(self) -> dict | None:
        """The best lure the character you play has (bags, bank), what it adds and what it costs an hour (lures used
        an hour x the cheapest price, vendor or AH). None when the bonus is typed in Settings or you have no lure."""
        if self.s.get('fishing_skill_bonus') not in (None, ''):
            return None
        syn = getattr(self.w, 'syndicator', None) or {}
        key = plan.character_key(syn, self.character())
        if not key:
            return None
        have = set((getattr(self.w, 'inventory', None) or {}).get(key) or {}) | set(syn[key].get('equipped') or {})
        best = fishing.best_lure(have, self.gd.items)
        if not best:
            return None
        iid, bonus = best
        minutes = fishing.LURE_MINUTES.get(iid, 10)
        q = self.cheapest(iid)
        each = q.value if q else 0
        return {'item_id': iid, 'name': self.name(iid), 'bonus': bonus, 'minutes': minutes, 'per_hour': 60 / minutes,
                'each': each, 'cost_per_hour': int(round(each * 60 / minutes)),
                'price_source': q.source if q else 'no known price'}

    def fish_value(self, iid: int, best_use: dict[int, dict]) -> int:
        """What one looted item is worth: the best of selling, crafting and opening it (see valuation.py)."""
        return self.valuer(best_use).worth(iid)

    def loot_worth(self, iid: int, best_use: dict[int, dict], per_loot: float, per_hour: float) -> int:
        """An item's average worth in an hour's loot: it comes per_loot times per loot (catch, kill, skin, node) at
        per_hour loots an hour. Crafted worth counts only for as many as its recipe can use a day (an hour of
        farming a day); the rest at the sale price (the user's decision, 2026-11-15: valuation.capped_total)."""
        return int(self.valuer(best_use).unit_worth(iid, per_loot * per_hour))

    def fishing_spots(self, best_use: dict[int, dict]) -> list[Opportunity]:
        """Fishing, zone by zone, Forever data first.

        Every zone with Forever data (your catches, Wowhead Forever counts) gets one row from that data. While
        the Forever sample is small it's blended with the zone's Classic table that matches it. Every other
        Classic table becomes a "Classic table: ..." row, marked unconfirmed for Forever.
        """
        cf = getattr(self.w, 'classic_fishing', None)
        obs = fishing.observations(self.w.angler, (getattr(self.w, 'profile', None) or {}).get('activity'))
        fishing.add_wowhead(obs, getattr(self.w, 'forever_fishing', None))
        # effective skill = your Fishing skill + what your pole, gear and lure add: the got-away roll uses it
        bonus, bonus_from = self.fishing_bonus()
        skill = int(self.profs.get('Fishing') or 0) + bonus
        # the lure is a choice per spot (used only where it pays: see _fishing_row), so it starts out of the skill
        self._lure = self.fishing_lure()
        if self._lure:
            skill -= self._lure['bonus']
        seasons = fishing.forever_seasons(cf, getattr(self.w, 'forever_fishing', None)) if cf else {}
        self._seasons_confirmed = bool(seasons)       # recent Forever catches say which seasons are on
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
        def val(iid, per_hour=0.0):
            """An item's worth in an hour's catches (per_hour of it): crafted worth only for as many as its recipe
            can use a day (loot_worth)."""
            return self.loot_worth(iid, best_use, per_hour, 1.0)

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
        keep, keep_src = model.keep(zone, zone_skill, skill, use_zone=forever)
        cph0 = model.catches_per_hour(keep)       # catches an hour without a lure: how many of each item an hour gives
        for iid in set(classic) | set(observed):
            share = w * observed.get(iid, 0.0) + (1 - w) * classic.get(iid, 0.0)
            v = 0 if iid in quest else val(iid, share * cph0)
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

        lure, lure_info, lure_cost = getattr(self, '_lure', None), None, 0
        if lure:
            keep_l, src_l = model.keep(zone, zone_skill, skill + lure['bonus'], use_zone=forever)
            no_lure, with_lure = model.catches_per_hour(keep), model.catches_per_hour(keep_l)
            used = fishing.lure_pays(value, no_lure, with_lure, lure['cost_per_hour'])
            lure_info = {**lure, 'used': used, 'gph_without': int(value * no_lure),
                         'gph_with': int(value * with_lure - lure['cost_per_hour'])}
            if used:
                keep, keep_src, lure_cost = keep_l, src_l, lure['cost_per_hour']
                skill += lure['bonus']
        cph, pace = model.catches_per_hour(keep), model.pace_source
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
            per = lambda i, c: val(i, c / fc['n_all'] * cph)      # its worth at an hour's catches of it
            for i, c in sorted(fc['pool'].items(), key=lambda kv: -kv[1] * per(*kv)):
                pool_rows.append({'item_id': i, 'name': self.name(i), 'count': c, 'share': round(c / fc['n_all'], 4),
                                  'value': per(i, c)})
                pool_value += c / fc['n_all'] * per(i, c)
            open_part = sum(c / fc['n_all'] * per(i, c) for i, c in fc['items_all'].items() if i not in fc['pool'])
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
            # in season by recent Forever catches: the value is right for now, no discount (only a note that it drops
            # when the season ends); by the Classic calendar only: a 10% "how sure" discount (Tanaris ranked under
            # Feralas for that while earning more, 2026-11-15)
            flags.append('seasonal_confirmed' if getattr(self, '_seasons_confirmed', False) else 'seasonal')
        if new_fish or missing:
            flags.append('forever_change')
        if zone_skill is not None and keep < 1:
            flags.append('classic_getaway')
        if lure_info and lure_info['used']:
            flags.append('lure_cost')
        flags.append('assumed_rate')
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
            units_day=0, daily=0, gph=round(value * cph - lure_cost) if doable else None, doable=doable,
            needs='' if doable else f'Fishing {zone_skill} (Classic zone skill)', profession='Fishing', preferred=True,
            flags=flags,
            detail={'zone': zone, 'zone_id': zid, 'forever': forever,
                    'classic_spot': spot.label(several) if spot else None,
                    'subzones': spot.names if spot else [], 'areas': spot.areas if spot else [],
                    'zone_skill': zone_skill, 'your_skill': skill,
                    'skill_bonus': self.fishing_bonus()[0] - (lure['bonus'] if lure and not lure_info['used'] else 0),
                    'skill_bonus_from': self.fishing_bonus()[1], 'lure': lure_info,
                    'keep': round(keep, 3), 'keep_source': keep_src,
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
                    'gph_with_pools': round(value_with_pools * cph - lure_cost) if value_with_pools and doable else None,
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

    def effort(self, o: Opportunity) -> dict | None:
        """Estimated minutes of play a day for a daily routine (craft or vendor flip), and what that time earns."""
        if o.kind not in ('craft', 'vendor_flip') or o.units_day <= 0:
            return None
        units = o.units_day
        item = self.gd.items.get(o.item_id)
        stack = item.stack if item else 1
        liq = o.detail.get('liquidity') or {}
        rate = liq.get('sale_rate') or 0.5
        relist = min(5.0, 1 / max(0.2, rate))                     # listings per sale, counting the ones that expire
        to_vendor = o.detail.get('sell_channel') == 'vendor'
        sold = units * (o.detail.get('product_count') or 1) if o.kind == 'craft' else units
        posts = 0.0 if to_vendor else math.ceil(sold / (POST_STACK if stack > 1 else 1)) * relist
        seconds = posts * POST_SECONDS + (5 if to_vendor else 0)
        if o.kind == 'craft':
            mats = o.detail.get('mats') or []
            seconds += units * CRAFT_SECONDS + BUY_SECONDS * sum(1 for m in mats if m.get('source') != 'vendor')
            if any(m.get('source') == 'vendor' for m in mats):
                seconds += VENDOR_TRIP_SECONDS
        else:
            seconds += VENDOR_TRIP_SECONDS
        minutes = round(seconds / 60, 1)
        # while you do it: the day's profit over the minutes it takes (the plan shows the same figure)
        return {'minutes': minutes, 'per_hour': int(o.daily / (minutes / 60)) if minutes else None,
                'time_value': self.time_value, 'cost': int(minutes / 60 * self.time_value),
                'posts': round(posts, 1)}

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
                ef = o.detail.get('effort')
                if ef:
                    base -= ef['cost']           # your time isn't free: minus what it's worth
                    basis += f", minus {ef['minutes']:g} min of your time"
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
        # your loot log per zone (no gold/hour); fishing logs feed the fishing spots below
        logged = [o for o in self.activity_zones(best_use) if o.kind != 'fishing_zone']
        # no snipe rows (AH -> vendor, cheap relists): one-off listings in hour-old data (the user, 2026-11-15)
        all_opps = (self.crafts() + self.vendor_flips()
                    + self.gathering(best_use) + logged + self.fishing_spots(best_use)
                    + self.skinning_spots(best_use) + self.node_spots(best_use) + self.mob_spots(best_use))
        min_spd = float(self.s.get('min_sold_per_day', 0.5))
        self.profit_views(all_opps)
        for o in all_opps:
            # anything you'd sell on the AH: does it actually sell? (hard to sell: never suggested)
            if (o.kind in ('craft', 'vendor_flip', 'gather', 'realm_dip')
                    and o.detail.get('sell_channel') not in ('vendor', 'craft')):
                liq = liquidity(self.price(o.item_id), min_spd)
                o.detail['liquidity'] = liq
                o.flags.extend(f for f in liq['flags'] if f not in o.flags)
        # what an hour of your time is worth: half the best farming spot backed by Forever data (rates from Wowhead
        # Forever counts at the paces in Settings; never your own logged time). A setting can fix it. Mob farming with
        # only some drops counted (no coins or gray items yet) is a floor, so it never sets what your time is worth.
        best = max((o.gph or 0 for o in all_opps if self._hourly_ok(o) and 'drops_partial' not in o.flags), default=0)
        fixed = float(self.s.get('time_value_gold') or 0) * COPPER_PER_GOLD
        self.time_value = int(fixed or (best * TIME_VALUE_SHARE if best else DEFAULT_TIME_VALUE))
        self.time_value_source = 'your setting' if fixed else ('half the best Forever farming spot' if best else 'default')
        for o in all_opps:
            ef = self.effort(o)
            if ef:
                o.detail['effort'] = ef
                if o.daily > 0 and o.daily <= ef['cost'] and 'not_worth_time' not in o.flags:
                    o.flags.append('not_worth_time')
        # price checks: a second opinion at typical prices flags rows that rest on unusual prices (anomalies.py)
        checks = anomalies.run(self, all_opps, best_use)
        for o in all_opps:
            o.detail['confidence'] = confidence(o.flags)
            o.score, o.detail['rank'] = self.rank(o)
            # what each would make if it sold at the region's average sale price, not the lowest listing
            liq = o.detail.get('liquidity')
            sale = pricing.usual_sale(self.price(o.item_id))          # freak sale averages left out
            if liq and sale and o.kind in ('craft', 'vendor_flip') and o.detail.get('sell_channel') != 'vendor':
                per = o.detail.get('product_count') or 1
                o.detail['profit_at_avg_sale'] = int(int(sale * (1 - self.cut)) * per - o.cost_unit)
            self.add_upside(o)
        self.apply_done(all_opps)
        top = self.top_picks(all_opps)
        return {'opportunities': all_opps, 'best_use': best_use, 'top': top,
                'plan': plan.build(all_opps, top, self.my_holdings(self.valuer(best_use)), self.time_value,
                                   self.share, self.cut, int(self.gold), self.s.get('done_today') or {}),
                'time_value': self.time_value, 'time_value_source': self.time_value_source, 'anomalies': checks,
                'undervalued': self.undervaluation_watch()}

    def character(self) -> str:
        """The character the app plans for: the one picked in the header (setting 'character'), else the last played."""
        return self.s.get('character') or (getattr(self.w, 'profile', None) or {}).get('active') or ''

    def sold_by_vendor(self, iid: int) -> bool:
        """A vendor you can use any day sells it (a Darkmoon Faire or other event vendor doesn't count)."""
        vp = self.vendor_price(iid)
        return bool(vp) and any(not v.get('event') for v in (vp[1] or [{}]))

    def gather_rates(self, opps: list) -> dict[int, dict]:
        """item -> the best Forever-backed spot that gives it: units an hour and the spot (skinning, mob, herb and ore
        rows at the Settings paces; never your own logged time). For "with your own materials"."""
        best: dict[int, dict] = {}

        def put(iid, per_hour, o):
            if per_hour > 0 and per_hour > best.get(iid, {}).get('per_hour', 0):
                best[iid] = {'per_hour': per_hour, 'spot': o.title, 'key': o.key}
        for o in opps:
            if not o.gph or {'classic_yields', 'classic_unconfirmed', 'small_sample', 'elite', 'dungeon'} & set(o.flags):
                continue
            d = o.detail
            if o.kind == 'mob_spot':
                for x in d.get('drops') or []:
                    put(x['item_id'], x['per_kill'] * d.get('kills_per_hour', 60), o)
            elif o.kind == 'skin_spot':
                ph = d.get('skins_per_hour', 60)
                usable = [m for m in d.get('mobs') or [] if m.get('can_skin') and m.get('can_kill')] or d.get('mobs') or []
                for m in usable[:1]:
                    for x in m.get('items') or []:
                        put(x['item_id'], x['share'] * ph, o)
            elif o.kind in ('herb_spot', 'mine_spot'):
                ph = d.get('nodes_per_hour', 40)
                for n in (d.get('nodes') or [])[:1]:
                    for x in n.get('items') or []:
                        if x.get('source') == 'forever':
                            put(x['item_id'], x['per_node'] * ph, o)
        return best

    def profit_views(self, opps: list) -> None:
        """Two more views of each craft (the user's request, 2026-11-15), in its details:
        good_day: one sale today at your realm's price even if it sells less than once a day (labelled optimistic);
        own: with the materials you could gather yourself counted at what they'd sell for (never as free), what
        crafting adds over selling them raw, and the farming time from the best Forever-backed spot for each."""
        rates = self.gather_rates(opps)
        for o in opps:
            if o.kind != 'craft':
                continue
            d = o.detail
            d['good_day'] = int(o.profit_unit * max(o.units_day or 0, 1))
            revenue, own, bought, hours, own_names, unknown = d.get('revenue', 0), 0, 0, 0.0, [], []
            for m in d.get('mats') or []:
                it = self.gd.items.get(m['item_id'])
                crafted_only = it and (it.name.startswith(('Cured ', 'Bolt of '))     # made, not gathered
                                       or m['item_id'] in self.tool_made)
                gatherable = (it and not crafted_only and not self.sold_by_vendor(m['item_id'])
                              and (it.class_id == 7 and it.subclass_id in GATHER_SOURCE or m['item_id'] in rates))
                if gatherable:
                    sold = self.sell_value(m['item_id'])[0]
                    own += sold * m['count']
                    own_names.append(m['name'])
                    r = rates.get(m['item_id'])
                    if r:
                        hours += m['count'] / r['per_hour']
                    else:
                        unknown.append(m['name'])
                else:
                    bought += m['unit'] * m['count']
            if own_names:
                farmed = revenue - bought            # gold per craft if you farm the gatherable materials
                d['own'] = {'materials': own_names, 'mats_value': int(own), 'adds': int(revenue - bought - own),
                            'per_craft': int(farmed), 'hours': round(hours, 2) if not unknown else None,
                            'gph': int(farmed / hours) if hours and not unknown else None, 'no_rate': unknown}

    def apply_done(self, opps: list) -> None:
        """What you ticked as done today (done.py): all of it -> flag 'done_today' (out of Top picks and the plan, the
        next best moves up); part of it -> the row keeps what's left for today."""
        ticks = self.s.get('done_today') or {}
        for o in opps:
            t = ticks.get(o.key)
            if not t:
                continue
            o.detail['done_today'] = t
            if t['done'] >= t['of']:
                o.flags.append('done_today')
            elif o.units_day:
                o.units_day = round(max(0.0, o.units_day - t['done']), 2)
                o.daily = int(o.profit_unit * o.units_day)

    def add_upside(self, o: Opportunity) -> None:
        """Priced at the lower of the lowest listing and the usual sale price: what the row would make if it sold at
        the current lowest listing instead ("up to" in the tables). Crafts and vendor flips sold on the AH only."""
        if self.sale_basis not in ('lower', 'realm') or o.kind not in ('craft', 'vendor_flip') \
                or o.detail.get('sell_channel', 'AH') != 'AH':
            return
        p = self.price(o.item_id)
        if self.sale_basis == 'realm':
            # realm prices: the "may sell for less" line, at the region's usual sale price
            lo, used = ah_sell(p, 'lower'), ah_sell(p, 'realm')
            if lo and used and lo.value < used.value:
                per = o.detail.get('product_count') or 1
                each = o.profit_unit - int((proceeds(used, self.cut) - proceeds(lo, self.cut)) * per)
                o.detail['at_usual'] = {'profit_unit': each, 'daily': int(each * o.units_day), 'price': lo.value,
                                        'price_used': used.value}
            return
        hi, used = ah_sell(p, 'min_buyout'), ah_sell(p, 'lower')
        if not hi or not used or hi.value <= used.value:
            return
        per = o.detail.get('product_count') or 1
        each = o.profit_unit + int((proceeds(hi, self.cut) - proceeds(used, self.cut)) * per)
        if each <= o.profit_unit:
            return
        o.detail['upside'] = {'profit_unit': each, 'daily': int(each * o.units_day), 'price': hi.value,
                              'price_used': used.value, 'source': hi.source}

    def my_holdings(self, valuer: valuation.Valuer, now: float | None = None) -> dict:
        """What the character you play holds (bags, bank, mailbox, auctions that ended), each valued: plan.py's input.

        From Syndicator, which saves on /reload or logout. An auction past its end time either sold or came back to
        the mailbox; it counts as mail unless Syndicator already recorded that mail.
        """
        syn = getattr(self.w, 'syndicator', None) or {}
        key = plan.character_key(syn, self.character())
        if not key:
            return {'found': False, 'items': [], 'ended_auctions': 0}
        c = syn[key]
        now = time.time() if now is None else now
        counts = dict((getattr(self.w, 'inventory', None) or {}).get(key) or {})
        mail = dict(c.get('mail') or {})
        ended: dict[int, int] = {}
        for a in c.get('auctions') or []:
            if a.get('expires') and a['expires'] < now:
                ended[a['item']] = ended.get(a['item'], 0) + a.get('count', 1)
        for iid, n in ended.items():
            mail[iid] = max(mail.get(iid, 0), n)
        min_spd = float(self.s.get('min_sold_per_day', 0.5))
        reagents = {m for r in self.gd.recipes for m, _ in r.reagents}
        items = []
        for iid in set(counts) | set(mail):
            it = self.gd.items.get(iid)
            if not it:
                continue
            v = valuer.value(iid)
            _, _, q = self.sell_value(iid)
            liq = liquidity(self.price(iid), min_spd)
            flags = list(v.flags) + (list(q.flags) if q and v.channel == 'AH' else [])
            n = counts.get(iid, 0) + mail.get(iid, 0)
            each = int(valuer.worth_for(iid, n) / n) if n else v.value    # a capped craft: the average over the stack
            items.append({'item_id': iid, 'name': it.name, 'quality': it.quality, 'class_id': it.class_id, 'subclass_id': it.subclass_id,
                          'stack': it.stack, 'count': counts.get(iid, 0) + mail.get(iid, 0),
                          'in_mail': mail.get(iid, 0), 'value': each, 'channel': v.channel, 'flags': flags,
                          'confidence': confidence(flags), 'sold_per_day': liq['sold_per_day'],
                          'sale_rate': liq['sale_rate'], 'liquidity_flags': liq['flags'], 'locked': it.locked,
                          'reagent': iid in reagents,
                          'contents': [x['name'] for x in v.contents[:3]]})
        return {'found': True, 'items': items, 'ended_auctions': sum(1 for a in c.get('auctions') or []
                                                                     if a.get('expires') and a['expires'] < now)}

    @staticmethod
    def _one_per_cooldown(ranked: list[Opportunity]) -> list[Opportunity]:
        """Keep only the best pick of each shared cooldown: doing one transmute blocks the others."""
        seen, out = set(), []
        for o in ranked:
            g = o.detail.get('cooldown_group')
            if g:
                if g in seen:
                    continue
                seen.add(g)
            out.append(o)
        return out

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

    @staticmethod
    def _hourly_ok(o: Opportunity) -> bool:
        """A farming row good enough for Top picks: a gold/hour backed by Forever data, something you can do now."""
        return bool(o.gph and o.doable and not ({'classic_unconfirmed', 'classic_yields'} & set(o.flags))
                    and (o.kind != 'fishing_spot' or (o.detail.get('confirmed_by') and 'small_sample' not in o.flags))
                    and (o.kind != 'skin_spot' or 'small_sample' not in o.flags)
                    and (o.kind != 'mob_spot' or not ({'small_sample', 'elite', 'dungeon', 'everloot'} & set(o.flags))))

    def top_picks(self, opps: list[Opportunity], n: int = 15) -> dict:
        bonus = float(self.s.get('switch_bonus', 1.5))
        bad = {'price_check_fails', 'not_worth_time', 'hard_to_sell', 'slow_seller', 'no_sales_data', 'cant_afford', 'unverified_recipe', 'above_region', 'black_market',
               'event_vendor'}
        if self.sale_basis == 'realm':
            bad.add('listed_far_above_sales')     # realm prices: a listing 3x+ above what sells is not a pick
        bad.add('done_today')                     # done for today: the next best takes its place

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
        hourly = [o for o in opps if self._hourly_ok(o)]
        # ranked by Engine.rank: profit x how sure we are x risk x can-do-now x problems x preference
        key = lambda o: o.score
        # sections about later rank by what a pick earns once you have the gold and skill for it
        later_key = lambda o: self.rank(o, later=True)[0]
        return {
            # daily routines: about one sale a day or more (Pattern: Devilsaur Gauntlets, 0.26 a day, topped this)
            'now': [o.key for o in self._one_per_cooldown(sorted((o for o in own if o.units_day >= DAILY_ROUTINE),
                                                                 key=key, reverse=True))[:n]],
            # occasional big flips: slower sellers, ranked by what one sale earns x how sure we are
            'slow': [o.key for o in self._one_per_cooldown(sorted((o for o in own if 0 < o.units_day < DAILY_ROUTINE),
                                                                  key=lambda o: o.profit_unit * o.detail['confidence'] * o.detail['rank']['risk'],
                                                                  reverse=True))[:8]],
            'level_up': [o.key for o in self._one_per_cooldown(sorted(
                (o for o in later if not o.doable and 'other_profession' not in o.flags), key=later_key, reverse=True))[:n]],
            'switch': [o.key for o in self._one_per_cooldown(sorted(stretch, key=later_key, reverse=True))[:5]],
            'hourly': self._varied(sorted(hourly, key=key, reverse=True), n, per_kind=5),
        }
