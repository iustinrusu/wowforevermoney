"""Every way an item turns into another item, and whether the app counts it (the user, 2026-11-19: "let's try to not
miss things like the Salt Shaker anymore. We really need to cover all the items and their interactions").

From the game data (gamedata.py), every spell that creates an item is one of:
- a recipe of a profession (SkillLineAbility): counted when the profession is in engine.PROFESSIONS
- an item use (ItemEffect): a tool you keep (Salt Shaker), an item used up (essences), items combined (Darkmoon
  cards): counted as crafts since 2026-11-19
- something else (`GameData.other_creates`): a class skill (mage food, warlock stones), a spell another spell casts,
  or no player source at all (an NPC, object or quest casts it). Not counted; listed here with the gold its product
  trades a day, so a missing money maker stands out.
Recipes also need tools in your bags (SpellTotems): checked against your bags since 2026-11-19.
Loot is not in the spell data: what each source gives comes from Wowhead Forever pages and other sources; LOOT says
what the app does with each kind.

Run: python -m wfm.interactions
"""
from __future__ import annotations

from .engine import PROFESSIONS
from .pricing import fmt_money, sold_per_day, usual_sale

# kinds of loot: how the app knows what they give, or that it doesn't yet
LOOT = [
    ('Mob drops', 'counted', 'Wowhead Forever "Dropped by" counts read by hand, Everloot where Wowhead has none'),
    ('Skinning', 'counted', 'Wowhead Forever "Skinned from" counts'),
    ('Fishing', 'counted', 'Wowhead Forever zone fishing counts; Classic tables only as labelled rows'),
    ('Herb and ore nodes', 'counted', 'Wowhead Forever "Gathered/Mined from" counts, Classic node tables labelled'),
    ('Opening containers, clams and lockboxes', 'counted', 'Wowhead Forever "Contains" counts and your own opens'),
    ('Pick Pocket', 'partly', 'read on item pages ("Pick pocketed from"), not yet a farming row'),
    ('Disenchanting', 'estimated', 'the WoW Classic reference table in ForeverRecipes (its own words: provisional), '
                                   'labelled "Classic table": shown in item details, My bags and "craft and '
                                   'disenchant it" rows, never in Top picks or the plan (the user said yes, 2026-11-19)'),
    ('Quest rewards', 'not counted', 'quest items are worth their vendor price only'),
]
MIN_SOLD = 1.0           # a product counts as traded at 1+ sold a day in the region
# What Wowhead Forever pages say about spells the game data gives no player source (checklist B10), by name
CHECKED = [('Power Crystal', "Wowhead Forever, 2026-11-27: the Philosopher's Stone page lists Transmute: Red Power "
                             "Crystal to Blue Power Crystal among the spells it is the tool for (the stone binds when "
                             "picked up and alchemists make it at skill 225), but gives it no profession, skill or way "
                             "to learn it, so who can cast these is still unknown")]


def _traded(prices: dict, iid: int) -> tuple[float, int]:
    p = prices.get(iid) or {}
    spd = sold_per_day(p)
    return spd, int(spd * (usual_sale(p) or 0))


def report(gd, prices: dict) -> dict:
    """Counts by kind, and every way of making a traded item the app doesn't count, most gold traded a day first."""
    kinds: dict[str, dict] = {}

    def add(kind, counted):
        k = kinds.setdefault(kind, {'spells': 0, 'counted': 0})
        k['spells'] += 1
        k['counted'] += 1 if counted else 0

    missing = []
    for r in gd.recipes:
        if getattr(r, 'tool_id', 0):
            kind = 'Using a tool you keep (Salt Shaker)'
        elif getattr(r, 'use_item', 0):
            kind = 'Using up or combining items (essences, Darkmoon cards)'
        else:
            kind = f'Recipes: {r.profession}'
        counted = r.profession in PROFESSIONS
        add(kind, counted)
        if not counted:
            spd, gold = _traded(prices, r.product_id)
            if spd >= MIN_SOLD:
                missing.append({'spell': r.spell_id, 'name': r.name, 'product': r.product_id, 'how': kind,
                                'sold_per_day': spd, 'gold_a_day': gold})
    for spell, name, product, count, mats, how in getattr(gd, 'other_creates', []):
        add(how.split(':')[0].split(' (')[0].capitalize(), False)
        spd, gold = _traded(prices, product)
        if spd >= MIN_SOLD:
            note = next((n for word, n in CHECKED if word in (name or '')), '')
            missing.append({'spell': spell, 'name': name, 'product': product,
                            'how': how + (f'. {note}' if note else ''), 'sold_per_day': spd,
                            'gold_a_day': gold, 'reagents': mats})
    missing.sort(key=lambda m: -m['gold_a_day'])
    tools = sum(1 for r in gd.recipes if getattr(r, 'tools_needed', ()) or getattr(r, 'tool_items', ()))
    return {'kinds': kinds, 'missing': missing, 'recipes_needing_tools': tools, 'loot': LOOT}


def check(rep: dict, item_name) -> dict:
    """The Data health entry."""
    k = rep['kinds']
    total = sum(v['spells'] for v in k.values())
    counted = sum(v['counted'] for v in k.values())
    miss = rep['missing']
    status = 'pass' if not miss else 'warn'
    detail = (f'{total:,} ways to make an item in the game data; the app counts {counted:,} of them (every recipe of '
              f'the professions it covers, Poisons included, and every item use: tools like the Salt Shaker, items '
              f'used up like essences, items combined like Darkmoon cards). {rep["recipes_needing_tools"]} recipes '
              f'need a tool in your bags (a hammer, a Philosopher\'s Stone, a runed rod): checked. '
              + (f'{len(miss)} ways make something traded (1+ sold a day) and are not counted: the list says how each '
                 f'is made; most are cast by an NPC, object or quest, which the game data cannot place. '
                 if miss else 'Nothing traded is made in a way the app leaves out. ')
              + 'Loot: ' + '; '.join(f'{n.lower()}: {s}' for n, s, _ in rep['loot']) + '.')
    examples = [f"{item_name(m['product'])} ({m['product']}): {m['sold_per_day']:.0f} sold a day, "
                f"{fmt_money(m['gold_a_day'])} traded a day; {m['how']} (spell {m['spell']} {m['name']})" for m in miss]
    return {'name': 'Item interactions covered (every way an item is made)', 'status': status, 'detail': detail,
            'examples': examples[:10]}


if __name__ == '__main__':
    from .paths import GamePaths, find_wow_dir
    from .settings import Settings
    from .world import World
    st = Settings()
    w = World(GamePaths(find_wow_dir(st.snapshot().get('wow_dir'))), st, log=lambda m: None)
    w.load_all()
    rep = report(w.gamedata, w.prices)
    name = lambda i: (w.gamedata.items.get(i).name if w.gamedata.items.get(i) else str(i))
    print('Ways to make an item, by kind (counted / all):')
    for kind, v in sorted(rep['kinds'].items(), key=lambda kv: -kv[1]['spells']):
        print(f"  {v['counted']:5} / {v['spells']:5}  {kind}")
    print(f"\n{rep['recipes_needing_tools']} recipes need a tool in your bags (checked).")
    print('\nNot counted, but the product trades 1+ a day (most gold a day first):')
    for m in rep['missing']:
        print(f"  {fmt_money(m['gold_a_day']):>14} a day  {name(m['product'])} ({m['sold_per_day']:.0f} sold)  "
              f"<- {m['name']} [{m['spell']}]: {m['how']}")
    print('\nLoot:')
    for n, s, why in rep['loot']:
        print(f'  {n}: {s} ({why})')
