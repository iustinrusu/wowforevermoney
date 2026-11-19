"""Levelling planner: the cheapest way to raise a crafting profession from one skill to another (300 by default;
strategy item 2; overhauled 2026-11-19 at the user's request: "the most efficient and cheap path is the only thing we
want, we don't want lesser paths").

The cost of one skill point with a recipe:
  net cost of one craft = ingredients (cheapest of vendor and AH; a material your own gathering profession provides
                          counts at what you would get for selling it) - what you get back for the product
  expected cost of the point = net cost of one craft / chance that a craft gives a skill point
What you get back for a product is the best of three, per unit:
  - the AH (after the cut), at the lower of the lowest listing and the region's usual sale price, and only for as many
    as your share of AH_DAYS days of its sales takes (crafting 60 of something that sells 2 a day floods the market);
    the rest go to the next best. Until 2026-11-19 it was a week at the lowest listing, and slow, valuable products
    made a route look like it earns gold: Living Shoulders 255-257 "earned" 61g from 2 sales at 37g, one every 3-4
    days (the user: "slow sells should not rank that high in the algorithm deciding best route")
  - a vendor
  - disenchanting it, valued from ForeverRecipes' WoW Classic table (labelled; only when one of your characters has
    the Enchanting skill for it, and only if you leave "count disenchanting" on)
A recipe's learning cost (trainer fee or recipe item) is paid once, the first time the path uses it.

Choosing the path is a facility-location problem: which recipes to learn (each has a one-time fee) and which recipe to
use for each skill point. The first planner (2026-11-15) chose point by point and charged a recipe's whole fee to the
point it was first used, so a recipe that is far cheaper over its next 20 points but costs a fee lost to a free one
that was cheaper for one point. Now (`_choose`):
  1. which recipes to learn (`_open_set`): each point costs (ingredients - what the product brings back once the AH
     has taken its share) / chance; a recipe's fee is lowered by what the AH pays extra for its first products. Start
     with the recipes you know and the free ones, learn the one that saves the most net of its fee, drop any that no
     longer pays, until nothing changes.
  2. walk the points in order (`_walk`): each gets the learned recipe whose crafts really cost least, with the AH
     taking the first products of each recipe and the rest going to a vendor or disenchanting.
  3. the old point-by-point plan and the two together are walked the same way; the cheapest of the three is kept,
     so the path is never worse than the first planner's. (Averaging the AH's share over a recipe's whole use made
     the choice flip between recipes: Leatherworking 255-270 came out at 386g instead of 209g; caught by comparing.)

Every recipe in the game is a candidate (2026-11-19, the user: "it should be with all recipes in game, and where to
get them or learn them"), not only the ones you know: trainer recipes, patterns on the AH or from a vendor (priced),
and patterns you can't buy with gold now (they only drop, come from a quest, or cost another currency). Those last
ones have no price, so the path uses one only for skill points no recipe you can buy reaches (a large fixed penalty,
FIND, far below the cost of an uncovered point), as few as it can, and the page says where to find each. A recipe
with no source known at all (UNKNOWN) comes after them.

Chance of a skill point: the WoW Classic rule, labelled as such (Forever has not been checked): orange and below
yellow always; from yellow to grey (grey - skill) / (grey - yellow); grey never. Colours are SkillUpForever's
Forever thresholds (ForeverRecipes fills its gaps). Crafts with a cooldown (Mooncloth, transmutes) are left out: one craft every few days.
Rank training (2026-11-19): to pass 75, 150 and 225 you train Journeyman, Expert and Artisan (a fee at a trainer, or a
book or quest for Cooking and First Aid); `training` puts each on the path where it is needed and adds its cost. The
fees, skills and levels are SkillUpForever's, from the WoW Classic database (Engine.rank_training), labelled.
A pattern priced from TSM's market value with none listed now, or the region's, may take a while to find: its step says
so (`learn_wait`); the price still counts.
Not counted: AH deposits, buying many of an ingredient (each costed at the lowest listing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_SKILL = 300
AH_DAYS = 2.0            # the AH takes this many days of your share of a product's sales (setting levelling_ah_days)
BIG = 1e13               # cost of a point no learned recipe can give: finite, so totals stay comparable
FIND = 1e11              # a recipe you'd have to find (drop, quest, another currency): only where nothing bought helps
UNKNOWN = 1e12           # a recipe with no source known: after every recipe you can find


@dataclass
class Option:
    """One recipe the planner may use."""
    spell_id: int
    name: str
    colors: tuple            # (orange, yellow, green, grey): first craftable skill, then the colour changes
    ingredients: int         # copper per craft
    ah_value: int            # copper per craft if sold on the AH (after the cut), 0 if it doesn't sell there
    vendor_value: int        # copper per craft sold to a vendor
    ah_cap: float            # crafts whose product the AH takes (AH_DAYS days of your share of its sales)
    learn: int | None        # one-time learning cost, None = can't be bought (drop / not on the AH)
    learn_how: str = ''
    product_id: int = 0
    mats: list = field(default_factory=list)   # [(item id, count, copper each, own material?)]
    de_value: int = 0        # copper per craft if disenchanted (Classic table); counted only if de_can
    de_can: bool = False     # one of your characters has the Enchanting skill to disenchant it
    find: str = ''           # can't be bought with gold now: 'drop', 'quest', 'vendor' (another currency), 'unknown'
    ah_per_day: float = 0.0  # products your share sells a day on the AH (units): under 1 is a slow sale, said on the page
    learn_wait: bool = False  # its pattern is not listed on your realm now (priced from a market value): may take a wait


def chance(colors: tuple, skill: int) -> float:
    """Chance a craft gives a skill point at this skill (WoW Classic rule)."""
    orange, yellow, green, grey = colors
    if skill < orange or skill >= grey:
        return 0.0
    if skill < yellow:
        return 1.0
    return max(0.0, min(1.0, (grey - skill) / (grey - yellow))) if grey > yellow else 0.0


def color(colors: tuple, skill: int) -> str:
    orange, yellow, green, grey = colors
    if skill < yellow:
        return 'orange'
    if skill < green:
        return 'yellow'
    return 'green' if skill < grey else 'grey'


def resale(o: Option, n: float, use_de: bool = True) -> tuple[float, str]:
    """What n crafts' products bring back on average per craft, and how: the AH (only for the first ah_cap of them),
    else the better of vendor and disenchanting."""
    de = o.de_value if (use_de and o.de_can) else 0
    rest, rest_how = (de, 'disenchant') if de > o.vendor_value else (o.vendor_value, 'vendor')
    if o.ah_value > rest and o.ah_cap > 0:
        if n <= o.ah_cap:
            return float(o.ah_value), 'AH'
        # "AH for 0.4": a slow seller's share of 2 days is under one sale (the page says how slow)
        return (o.ah_cap * o.ah_value + (n - o.ah_cap) * rest) / n, f'AH for {round(o.ah_cap, 1):g}, then {rest_how}'
    return float(rest), rest_how


def _rest(o: Option, use_de: bool) -> float:
    """What a product brings back once the AH has taken its share: the better of a vendor and disenchanting."""
    return float(max(o.vendor_value, o.de_value if (use_de and o.de_can) else 0))


def _open_set(options: list[Option], points: list[int], fee: dict, use_de: bool) -> set:
    """Which recipes to learn: a facility-location choice. Each point costs (ingredients - long-run resale) / chance;
    a recipe's fee is reduced by what the AH pays extra for its first products (only for as many as it can make
    here), never below 0. Start with the free ones; learn the recipe that saves the most net of its fee; drop one
    that no longer pays; until nothing changes."""
    cost, eff = {}, {}
    for o in options:
        per = o.ingredients - _rest(o, use_de)
        cost[o.spell_id] = [per / p if (p := chance(o.colors, s)) > 0 else BIG for s in points]
        reach = sum(1 / p for s in points if (p := chance(o.colors, s)) > 0)
        bonus = max(0.0, o.ah_value - _rest(o, use_de)) * min(o.ah_cap, reach) if o.ah_cap > 0 else 0.0
        eff[o.spell_id] = max(0.0, fee[o.spell_id] - bonus)
    fixed = {r for r in fee if fee[r] == 0}
    opened = set(fixed)

    def best(open_set):
        return [min((cost[r][i] for r in open_set), default=BIG) for i in range(len(points))]

    def total(open_set):
        return sum(best(open_set)) + sum(eff[r] for r in open_set)

    for _ in range(len(options) + 2):
        changed = False
        cur = best(opened)
        gains = []
        for r in cost:                            # learn the recipe that saves the most, net of its fee
            if r in opened:
                continue
            g = sum(cur[i] - c for i, c in enumerate(cost[r]) if c < cur[i])     # a newly covered point: ~BIG
            if g - eff[r] > 1e-9:
                gains.append((g - eff[r], -eff[r], r))
        if gains:
            opened.add(max(gains)[2])
            changed = True
        for r in sorted(opened - fixed):          # drop a learned recipe that no longer pays for its fee
            if total(opened - {r}) <= total(opened) + 1e-9:
                opened.discard(r)
                changed = True
        if not changed:
            break
    return opened


def _walk(by_id: dict, allowed, points: list[int], fee: dict, use_de: bool, fees_now: bool = False) -> tuple:
    """Each point in order gets the allowed recipe with the cheapest real cost for its crafts: the AH takes the first
    products of each recipe, the rest go to the better of vendor and disenchanting. fees_now: a recipe's fee counts on
    the point it is first used (the 2026-11-15 planner, kept as a check). Returns (total with fees, choice)."""
    used, learned, choice, total = {}, set(), {}, 0.0
    prev = None
    for s in points:
        best = None
        for r in allowed:
            o = by_id[r]
            p = chance(o.colors, s)
            if p <= 0:
                continue
            n, before = 1 / p, used.get(r, 0.0)
            back = resale(o, before + n, use_de)[0] * (before + n) - (resale(o, before, use_de)[0] * before if before else 0.0)
            c = n * o.ingredients - back + (fee[r] if fees_now and r not in learned else 0)
            if best is None or c < best[0] - 1e-9 or (abs(c - best[0]) <= 1e-9 and (r == prev or (best[1] != prev and r < best[1]))):
                best = (c, r, n)
        if best is None:
            break
        c, r, n = best
        if fees_now and r not in learned:
            c -= fee[r]
        used[r] = used.get(r, 0.0) + n
        learned.add(r)
        choice[s] = prev = r
        total += c
    total += sum(fee[r] for r in learned)
    return total + BIG * (len(points) - len(choice)), choice


def _choose(options: list[Option], points: list[int], known: set, use_de: bool) -> dict:
    """The cheapest path found: the facility-location choice walked point by point, and two checks (the old
    point-by-point planner, and both together); the cheapest of the three by the same exact cost."""
    by_id = {o.spell_id: o for o in options}
    fee = {o.spell_id: (0 if o.spell_id in known else o.learn if o.learn is not None else
                        UNKNOWN if o.find == 'unknown' else FIND) for o in options}
    opened = _open_set(options, points, fee, use_de)
    tries = [_walk(by_id, opened, points, fee, use_de)]
    old_total, old_choice = _walk(by_id, list(by_id), points, fee, use_de, fees_now=True)
    tries.append((old_total, old_choice))
    tries.append(_walk(by_id, opened | set(old_choice.values()), points, fee, use_de))
    return min(tries, key=lambda t: (t[0], len(set(t[1].values()))))[1]


def plan(options: list[Option], skill: int, target: int = MAX_SKILL, known: set[int] | None = None,
         use_de: bool = True, training: list[dict] | None = None) -> dict:
    """The cheapest path. known: recipe spells you have already (no learning cost). training: the profession ranks to
    train on the way, each {'at': the skill it is needed at (75, 150, 225), 'cost': copper, ...}: paid when the path
    gets there, and shown before the recipe that comes next (step['train'])."""
    known = set(known or ())
    options = [o for o in options if o.spell_id in known or o.learn is not None or o.find]
    by_id = {o.spell_id: o for o in options}
    points = list(range(max(1, skill), min(target, MAX_SKILL)))
    choice = _choose(options, points, known, use_de)
    stuck_at = next((s for s in points if s not in choice), None)
    # walk the path in order: the AH takes the first products of each recipe, the rest go to the next best
    steps, used, learned = [], {}, set(known)
    total = learn_total = crafts_total = mats_total = back_total = train_total = 0.0
    shopping: dict[int, dict] = {}
    train_at = {int(t['at']): t for t in training or ()}
    trained, pending = [], None
    for s in points:
        r = choice.get(s)
        if r is None:
            break
        if s in train_at:                     # the rank below stops here: train the next one first
            t = train_at[s]
            total += t.get('cost') or 0
            train_total += t.get('cost') or 0
            pending = dict(t, cumulative=int(round(total)))
            trained.append(pending)
        o = by_id[r]
        p = chance(o.colors, s)
        crafts = 1 / p
        before = used.get(r, 0.0)
        used[r] = before + crafts
        back_all, how = resale(o, used[r], use_de)
        back_prev = resale(o, before, use_de)[0] * before if before else 0.0
        back = back_all * used[r] - back_prev                 # what this point's crafts bring back
        fee = 0
        if r not in learned:
            learned.add(r)
            fee = o.learn or 0
        cost = crafts * o.ingredients - back + fee
        total += cost
        learn_total += fee
        crafts_total += crafts
        mats_total += crafts * o.ingredients
        back_total += back
        last = steps[-1] if steps else None
        if last and last['spell_id'] == r and not pending:
            last.update(to=s + 1, crafts=last['crafts'] + crafts, cost=last['cost'] + cost, cumulative=total,
                        mats_cost=last['mats_cost'] + crafts * o.ingredients, back=last['back'] + back, back_how=how)
        else:
            steps.append({'from': s, 'to': s + 1, 'spell_id': r, 'recipe': o.name, 'product_id': o.product_id,
                          'color': color(o.colors, s), 'crafts': crafts, 'cost': cost, 'cumulative': total,
                          'learn': fee, 'learn_how': o.learn_how, 'mats': o.mats, 'known': r in known,
                          'find': o.find if (r not in known and o.learn is None) else '',
                          'per_craft': o.ingredients - resale(o, 1.0, use_de)[0],
                          'ingredients': o.ingredients, 'mats_cost': crafts * o.ingredients, 'back': back,
                          'back_how': how, 'channels': {'AH': o.ah_value, 'vendor': o.vendor_value,
                                                        'disenchant': o.de_value, 'disenchant_can': o.de_can},
                          'ah_cap': o.ah_cap, 'ah_per_day': o.ah_per_day,
                          'learn_wait': o.learn_wait and r not in known and fee > 0})
            if pending:
                steps[-1]['train'], pending = pending, None
    for st in steps:
        st['crafts_to_buy'] = math.ceil(st['crafts'] - 1e-9)       # whole crafts: what to buy for this stretch
        for mid, cnt, each, own in st['mats']:
            row = shopping.setdefault(mid, {'item_id': mid, 'count': 0, 'each': each, 'own': own})
            row['count'] += cnt * st['crafts_to_buy']
        st['crafts'] = round(st['crafts'], 1)
        for k in ('cost', 'cumulative', 'mats_cost', 'back'):
            st[k] = int(round(st[k]))
    reached = steps[-1]['to'] if steps else max(1, skill)
    shop = sorted(shopping.values(), key=lambda m: -m['count'] * m['each'])
    for m in shop:
        m['total'] = m['count'] * m['each']
    to_find = [{'spell_id': st['spell_id'], 'recipe': st['recipe'], 'how': st['find'], 'from': st['from']}
               for st in steps if st['find']]
    return {'skill': skill, 'target': min(target, MAX_SKILL), 'reached': reached, 'stuck_at': stuck_at,
            'to_find': to_find,
            'steps': steps, 'total': int(round(total)), 'learn_total': int(learn_total), 'crafts': round(crafts_total),
            'training': trained, 'train_total': int(train_total),
            'to_wait': [{'spell_id': st['spell_id'], 'recipe': st['recipe'], 'from': st['from']}
                        for st in steps if st['learn_wait']],
            'materials_total': int(round(mats_total)), 'back_total': int(round(back_total)), 'shopping': shop,
            'use_disenchant': use_de}
