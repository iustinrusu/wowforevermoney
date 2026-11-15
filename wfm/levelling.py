"""Levelling planner: the cheapest way to raise a crafting profession from your skill to 300 (strategy item 2).

For every skill point it picks the recipe with the lowest expected cost for that point:
  cost of one craft = ingredients (cheapest of vendor and AH; a material your own gathering profession provides
                      counts at what you would get for selling it) - what the product sells for
  expected cost of the point = cost of one craft / chance that a craft gives a skill point
and a recipe's learning cost (trainer fee or recipe item) counts once, the first time the plan uses it.

Chance of a skill point: the WoW Classic rule, labelled as such (Forever has not been checked): orange and below
yellow always; from yellow to grey (grey - skill) / (grey - yellow); grey never. Colours are SkillUpForever's
Forever thresholds [orange, yellow, green, grey].

What a product sells for: its AH price (after the cut) only for as many as your share of a week's sales takes, the
rest at its vendor price (crafting 60 of something that sells 2 a day floods the market). Not counted: rank training
at the trainer (Journeyman, Expert, Artisan) and the level it needs, AH deposits, buying many of an ingredient (each
costed at the lowest listing).
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_SKILL = 300
WEEK = 7.0               # product resale at the AH price for a week of your share of its sales


@dataclass
class Option:
    """One recipe the planner may use."""
    spell_id: int
    name: str
    colors: tuple            # (orange, yellow, green, grey): first craftable skill, then the colour changes
    ingredients: int         # copper per craft
    ah_value: int            # copper per craft if sold on the AH (after the cut), 0 if it doesn't sell there
    vendor_value: int        # copper per craft sold to a vendor
    ah_cap: float            # crafts whose product the AH takes (a week of your share of its sales)
    learn: int | None        # one-time learning cost, None = can't be bought (drop / not on the AH)
    learn_how: str = ''
    product_id: int = 0
    mats: list = field(default_factory=list)   # [(item id, count, copper each, own material?)]


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


def plan(options: list[Option], skill: int, target: int = MAX_SKILL, known: set[int] | None = None) -> dict:
    """The cheapest path, one skill point at a time. known: recipe spells you have already (no learning cost)."""
    learned = set(known or ())
    used: dict[int, float] = {}           # crafts planned so far per recipe (for the AH resale cap)
    steps, total, learn_total, crafts_total, stuck_at = [], 0.0, 0, 0.0, None
    for s in range(max(1, skill), min(target, MAX_SKILL)):
        best = None
        for o in options:
            p = chance(o.colors, s)
            if p <= 0:
                continue
            if o.spell_id not in learned and o.learn is None:
                continue
            resale = o.ah_value if used.get(o.spell_id, 0) < o.ah_cap else o.vendor_value
            per_craft = o.ingredients - max(resale, o.vendor_value)
            cost = per_craft / p + (0 if o.spell_id in learned else o.learn)
            if best is None or cost < best[0]:
                best = (cost, o, p, per_craft)
        if best is None:
            stuck_at = s
            break
        cost, o, p, per_craft = best
        if o.spell_id not in learned:
            learned.add(o.spell_id)
            learn_total += o.learn or 0
        crafts = 1 / p
        used[o.spell_id] = used.get(o.spell_id, 0) + crafts
        total += cost
        crafts_total += crafts
        last = steps[-1] if steps else None
        if last and last['spell_id'] == o.spell_id:
            last.update(to=s + 1, crafts=last['crafts'] + crafts, cost=last['cost'] + cost, cumulative=total)
        else:
            steps.append({'from': s, 'to': s + 1, 'spell_id': o.spell_id, 'recipe': o.name, 'product_id': o.product_id,
                          'color': color(o.colors, s), 'crafts': crafts, 'cost': cost, 'cumulative': total,
                          'learn': o.learn if o.learn and o.spell_id not in (known or ()) else 0, 'learn_how': o.learn_how,
                          'per_craft': per_craft, 'mats': o.mats})
    for st in steps:
        st['crafts'] = round(st['crafts'], 1)
        st['cost'], st['cumulative'] = int(round(st['cost'])), int(round(st['cumulative']))
    reached = steps[-1]['to'] if steps else max(1, skill)
    return {'skill': skill, 'target': min(target, MAX_SKILL), 'reached': reached, 'stuck_at': stuck_at,
            'steps': steps, 'total': int(round(total)), 'learn_total': int(learn_total), 'crafts': round(crafts_total)}
