"""Profession advisor (strategy item 1): what each primary profession earns you now and at full skill, and the cost
of getting there, so keeping or switching a profession is a sum you can see.

Gathering (Herbalism, Mining, Skinning): gold an hour, the best spot. "Now" = a spot you can do today; "full skill"
= the best spot that only needs more skill (not a higher level). Rows resting on WoW Classic yields are shown but
labelled, never mixed in silently. Levelling a gathering profession costs no gold: it rises as you gather.
Crafting (the rest): profit a day from the three best crafts that sell, now (recipes you can make) and at 300 (any
recipe, with the gold to buy the ingredients), and the levelling planner's cost from your skill (or from 1) to 300.
Comparing the two kinds needs a common unit: one hour of farming a day is about the gold/hour.
"""
from __future__ import annotations

PRIMARY = ('Alchemy', 'Blacksmithing', 'Enchanting', 'Engineering', 'Herbalism', 'Leatherworking', 'Mining', 'Skinning',
           'Tailoring')
GATHERING = {'Herbalism': ('herb_spot',), 'Mining': ('mine_spot',), 'Skinning': ('skin_spot',)}
BAD = {'not_worth_time', 'hard_to_sell', 'slow_seller', 'no_sales_data', 'unverified_recipe', 'above_region',
       'black_market', 'event_vendor', 'classic_unconfirmed', 'price_check_fails', 'cant_afford'}
CLASSIC = {'classic_yields', 'classic_unconfirmed'}
TOP_CRAFTS = 3


def _gather_row(rows: list) -> dict | None:
    if not rows:
        return None
    o = max(rows, key=lambda o: o.gph or 0)
    return {'title': o.title, 'key': o.key, 'gph': int(o.gph or 0), 'classic': bool(CLASSIC & set(o.flags))}


def gathering(prof: str, opps: list, have: bool) -> dict:
    kinds = GATHERING[prof]
    rows = [o for o in opps if o.kind in kinds and o.gph and not ({'small_sample', 'elite', 'dungeon'} & set(o.flags))]
    forever = [o for o in rows if not (CLASSIC & set(o.flags))]
    now = [o for o in forever if o.doable] if have else []
    full = [o for o in forever if not str(o.needs or '').startswith('level')]
    classic_full = [o for o in rows if CLASSIC & set(o.flags) and not str(o.needs or '').startswith('level')]
    return {'now': _gather_row(now), 'full': _gather_row(full), 'classic_full': _gather_row(classic_full)}


def one_per_cooldown(ranked: list) -> list:
    """Crafts that share a cooldown (Forever's transmutes) can't all be done: keep the best of each group."""
    seen, out = set(), []
    for o in ranked:
        g = o.detail.get('cooldown_group')
        if g and g in seen:
            continue
        seen.add(g)
        out.append(o)
    return out


def crafting(prof: str, opps: list) -> dict:
    rows = [o for o in opps if o.kind == 'craft' and o.profession == prof and not (BAD - {'cant_afford'}) & set(o.flags)]
    now = one_per_cooldown(sorted((o for o in rows if o.doable and 'cant_afford' not in o.flags),
                                  key=lambda o: -o.daily))[:TOP_CRAFTS]
    full = one_per_cooldown(sorted(rows, key=lambda o: -(o.detail.get('daily_if_affordable', o.daily) or 0)))[:TOP_CRAFTS]
    pick = lambda os_, f: [{'title': o.title, 'key': o.key, 'daily': int(f(o) or 0)} for o in os_]
    # a good day (optimistic): one sale of each of its best crafts today, slow ones too; big sales: worth a lot each
    # but selling less than once a day (Devilsaur Leggings), so the average day hides them
    sellable = [o for o in opps if o.kind == 'craft' and o.profession == prof
                and not (BAD - {'cant_afford', 'hard_to_sell'}) & set(o.flags)]
    good = one_per_cooldown(sorted(sellable, key=lambda o: -(o.detail.get('good_day') or 0)))[:TOP_CRAFTS]
    big = sorted((o for o in sellable if (o.units_day or 0) < 1 and o.profit_unit > 0), key=lambda o: -o.profit_unit)[:3]
    return {'good_day': sum(int(o.detail.get('good_day') or 0) for o in good),
            'big_sales': [{'title': o.title, 'key': o.key, 'profit_unit': int(o.profit_unit),
                           'days_per_sale': round(1 / o.units_day) if o.units_day else None} for o in big],
            'now': pick(now, lambda o: o.daily), 'full': pick(full, lambda o: o.detail.get('daily_if_affordable', o.daily)),
            'now_daily': sum(int(o.daily or 0) for o in now),
            'full_daily': sum(int(o.detail.get('daily_if_affordable', o.daily) or 0) for o in full)}


def verdict(r: dict) -> str:
    """One plain sentence per profession."""
    from .pricing import fmt_money
    if r['kind'] == 'gathering':
        now, full, cf = r['gather']['now'], r['gather']['full'], r['gather']['classic_full']
        best = full or cf
        if not best:
            return 'No spot with enough data yet.'
        tail = ' (by WoW Classic yields: not confirmed for Forever)' if not full else ''
        if r['have']:
            return (f"You have it: {fmt_money(now['gph'])} an hour now" if now else 'You have it, but no spot you can do '
                    'today has enough Forever data') + f"; up to {fmt_money(best['gph'])} an hour with more skill{tail}."
        return f"Up to {fmt_money(best['gph'])} an hour once learned and levelled (it levels as you gather){tail}."
    c, lev = r['craft'], r.get('levelling') or {}
    cost = lev.get('total')
    path = ('levelling to 300 earns about ' + fmt_money(-cost) if cost is not None and cost < 0 else
            f"levelling to 300 costs about {fmt_money(cost)}" if cost is not None else 'no levelling path')
    if lev.get('stuck_at'):
        path += f" (the path stops at {lev['stuck_at']}: no recipe you can buy past it)"
    if r['have']:
        return (f"You have it: {fmt_money(c['now_daily'])} a day now from its best crafts; {fmt_money(c['full_daily'])} a day "
                f"at 300; {path}.")
    return f"{fmt_money(c['full_daily'])} a day at 300 from its best crafts; {path} from skill 1."


def build(engine, opps: list, profs: dict, known: set | None = None) -> dict:
    rows = []
    for prof in PRIMARY:
        have = prof in profs
        r = {'profession': prof, 'have': have, 'skill': profs.get(prof)}
        if prof in GATHERING:
            r.update(kind='gathering', gather=gathering(prof, opps, have))
            g = r['gather']
            r['now_value'] = (g['now'] or {}).get('gph', 0)
            r['full_value'] = ((g['full'] or g['classic_full']) or {}).get('gph', 0)
        else:
            r.update(kind='crafting', craft=crafting(prof, opps))
            if prof != 'Enchanting':        # enchantments make no item: not in the recipe tables, no path
                lev = engine.levelling(prof, int(profs.get(prof) or 1), known=known if have else set(), crafts=[])
                r['levelling'] = {k: lev[k] for k in ('total', 'crafts', 'reached', 'stuck_at', 'learn_total')}
            r['now_value'], r['full_value'] = r['craft']['now_daily'], r['craft']['full_daily']
        r['verdict'] = verdict(r)
        rows.append(r)
    rows.sort(key=lambda r: (not r['have'], -r['full_value']))
    primaries = [r['profession'] for r in rows if r['have']]
    return {'rows': rows, 'yours': primaries,
            'note': 'Gathering rows are gold an hour (one hour of farming a day is about that much a day); crafting rows '
                    'are profit a day from the three best crafts that sell. You can have two primary professions.'}
