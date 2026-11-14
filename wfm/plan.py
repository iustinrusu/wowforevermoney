"""Your plan for today: a short checklist of the best things to do, the way a seasoned gold-maker plans a session.

A pro doesn't scroll one long list sorted by profit a day. They run a checklist, best value for their time first:
1. Cash in what you already have (no cost, a few minutes): list what sells on the AH, open what is worth more
   opened, sell junk to a vendor, collect auctions that ended.
2. Daily cooldowns of a profession you have (one per shared cooldown).
3. Daily routines: the best crafts and vendor flips that sell about once a day or more.
4. One snipe: a listing far below what the item sells for, if it is still there.
5. One farming session: the best gathering or farming hour backed by Forever data (never Classic yields).
6. One occasional big flip: worth a lot per sale, sells less than once a day.
7. One long-term goal, shown last and not ranked against the rest.

Every action gets a value for today: expected gain (gain x how sure we are) minus the minutes it takes x what your
time is worth. Actions not worth their time are dropped, each type is capped so the list stays varied, the best
8 by value make the list, and they are shown in order of gold per hour of your time, so quick wins come first and
the long farming session last.

Pure functions on plain data (holding dicts, Opportunity rows): unit-tested in tests/test_plan.py.
"""
from __future__ import annotations

import math

MAX_ACTIONS = 8
PER_TYPE = {'routine': 3, 'farm': 1, 'big_flip': 1}   # at most this many per type (2 if not listed): a varied plan
DEFAULT_PER_TYPE = 2
LIST_DAYS = 2                      # list what sells in about two days at your share of the region; keep the rest
AH_TRIP_MIN = 1.0                  # walk to the auction house and open it
VENDOR_TRIP_MIN = 2.0              # go to a vendor and back
POST_SECONDS = 10                  # post one auction (same as engine.POST_SECONDS)
POST_STACK = 5                     # stackables posted a few at a time (same as engine.POST_STACK)
OPEN_SECONDS = 5                   # open one container and loot it
CRAFT_ONCE_MIN = 2.0               # buy the ingredients for one cooldown craft, make it, post it
SNIPE_MIN = 2.0                    # look it up, buy, relist
SNIPE_STILL_THERE = 0.5            # a listing from the last scan may be gone: count half of it
BIG_FLIP_MIN = 10000               # an occasional flip makes the plan only if one sale earns 1g+ (at the usual price)
COOLDOWN_DAILY_HOURS = 20          # a cooldown this long or longer is a once-a-day action, not a routine
SHOWN_ITEMS = 8                    # item lines shown under a cash-in action
CASH_TYPES = ('cash_ah', 'cash_open', 'cash_vendor')
GEAR_CLASSES = (2, 4)              # weapons and armour: may be your own gear, so never in the vendor junk pile
CONSUMABLE, FOOD = 0, 5            # item class 0: potions, food, poisons, lures; 0/5 food includes raw fish
SPELL_REAGENT = (15, 1)            # Flash Powder, Thieves' Tools: things your class spells need
TOOL_SUBCLASSES = (14, 20)         # weapon subclasses: Skinning Knife, Mining Pick (misc.), fishing poles

TYPE_LABEL = {'cash_ah': 'Cash in', 'cash_open': 'Cash in', 'cash_vendor': 'Cash in', 'cooldown': 'Cooldown',
              'routine': 'Daily routine', 'snipe': 'Snipe', 'farm': 'Farming', 'big_flip': 'Big flip',
              'goal': 'Long-term goal'}
BAD_FLAGS = {'not_worth_time', 'hard_to_sell', 'slow_seller', 'no_sales_data', 'cant_afford', 'unverified_recipe',
             'above_region', 'black_market', 'event_vendor', 'classic_unconfirmed', 'classic_yields'}


def gold(c: float | None) -> str:
    """Copper as '5g 13s', '13s 4c' or '4c' (the page's money text)."""
    if c is None:
        return '-'
    c = int(round(c))
    sign, c = ('-' if c < 0 else ''), abs(c)
    g, s, cc = c // 10000, (c // 100) % 100, c % 100
    return sign + (f'{g:,}g {s}s' if g else (f'{s}s {cc}c' if s else f'{cc}c'))


def count_text(n: float) -> str:
    return f'{n:,.0f}' if n >= 10 else f'{n:,.1f}'.replace('.0', '')


def character_key(syndicator: dict, active: str) -> str | None:
    """Syndicator's key for the character you play (the same match the purse uses)."""
    name = (active or '').split('-')[0]
    return next((k for k, c in (syndicator or {}).items() if name and c.get('name') == name), None)


def _action(type_, title, why, gain, minutes, confidence=1.0, gold_needed=0, key=None, item_id=None, **extra) -> dict:
    a = {'type': type_, 'label': TYPE_LABEL[type_], 'title': title, 'why': why, 'gain': int(gain),
         'minutes': round(minutes, 1), 'confidence': round(confidence, 3), 'gold_needed': int(gold_needed),
         'key': key, 'item_id': item_id}
    a.update(extra)
    return a


def _weighted_confidence(rows: list[dict], total: float) -> float:
    return sum(r['confidence'] * r['gain'] for r in rows) / total if total else 1.0


def _item_line(h: dict, n: int, unit: int, cut: float | None = None) -> dict:
    line = {'item_id': h['item_id'], 'name': h['name'], 'quality': h.get('quality', 1), 'count': n,
            'have': h['count'], 'unit': unit, 'total': unit * n}
    if cut is not None:
        line['list_at'] = int(round(unit / (1 - cut)))       # the listing price that leaves `unit` after the AH cut
    return line


def cash_in(holdings: list[dict], share: float, cut: float, ended_auctions: int = 0) -> list[dict]:
    """Actions for what you already own: list on the AH, open containers, sell junk to a vendor.

    holdings: one dict per item you hold (bags, bank, mailbox), valued by valuation.Valuer: item_id, name, quality,
    class_id, stack, count, in_mail, value (copper each through its best channel), channel (AH | vendor | open |
    craft | none), flags, confidence, sold_per_day, sale_rate, liquidity_flags, locked, contents (names),
    reagent (an ingredient in some recipe).

    Things you probably use yourself are named but not counted: consumables (potions, food, poisons, lures,
    bandages), spell reagents (Flash Powder) and profession tools (Skinning Knife, fishing poles). Raw fish is
    "food" in the game data, but recipes use it, so it counts as a material to sell.
    """
    out = []
    own_use = [h for h in holdings if _own_use(h) and h['value'] > 0 and h['channel'] in ('AH', 'vendor')]
    holdings = [h for h in holdings if not _own_use(h)]
    # 1) the AH: items that sell, only as many as the market takes in about two days at your share
    ah, posts, mailed = [], 0.0, 0
    for h in holdings:
        if h['channel'] != 'AH' or h['value'] <= 0 or {'hard_to_sell', 'no_sales_data'} & set(h.get('liquidity_flags') or ()):
            continue
        n = min(h['count'], max(1, math.ceil((h.get('sold_per_day') or 0) * share * LIST_DAYS)))
        relist = min(5.0, 1 / max(0.2, h.get('sale_rate') or 0.5))       # listings per sale, counting expired ones
        posts += math.ceil(n / (POST_STACK if (h.get('stack') or 1) > 1 else 1)) * relist
        mailed += 1 if h.get('in_mail') else 0
        ah.append({**_item_line(h, n, h['value'], cut), 'gain': h['value'] * n, 'confidence': h.get('confidence', 1.0),
                   'kept': h['count'] - n})
    if ah:
        ah.sort(key=lambda r: -r['gain'])
        total = sum(r['gain'] for r in ah)
        kept = sum(1 for r in ah if r['kept'])
        why = (f'{len(ah)} things you own sell best on the auction house: about {gold(total)} after the {cut:.0%} '
               f'AH cut, at the listing prices shown (today\'s lowest listing, or the usual sale price where nobody '
               f'pays the listing).')
        if kept:
            why += (f' For {kept} of them you have more than the market buys in about {LIST_DAYS} days at your '
                    f'share, so list only the amount shown and keep the rest for later days.')
        if ended_auctions:
            why += (f' {ended_auctions} of your auctions have ended since you last looked (sold or came back to '
                    f'your mailbox): collect your mail first and relist what came back.')
        elif mailed:
            why += ' Collect your mail first: some of these are waiting there.'
        if own_use:
            own_use.sort(key=lambda h: -h['value'] * h['count'])
            names = ', '.join(f"{h['count']} {h['name']}" for h in own_use[:4]) + (' and more' if len(own_use) > 4 else '')
            why += (f' Not counted: things you may use yourself ({names}, about '
                    f'{gold(sum(h["value"] * h["count"] for h in own_use))}): sell them too if you do not need them.')
        why += ' Skip anything else you want to keep, such as gear you will wear or ingredients for your own crafting.'
        out.append(_action('cash_ah', f'List {len(ah)} item{"s" if len(ah) != 1 else ""} from your bags on the AH',
                           why, total, AH_TRIP_MIN + posts * POST_SECONDS / 60, _weighted_confidence(ah, total),
                           items=ah[:SHOWN_ITEMS], more=max(0, len(ah) - SHOWN_ITEMS)))
    # 2) open containers worth more opened than sold
    opens = [h for h in holdings if h['channel'] == 'open' and 'open_it' in (h.get('flags') or ()) and h['value'] > 0]
    if opens:
        rows = [{**_item_line(h, h['count'], h['value']), 'gain': h['value'] * h['count'],
                 'confidence': h.get('confidence', 1.0), 'contents': h.get('contents') or [], 'locked': h.get('locked')}
                for h in opens]
        rows.sort(key=lambda r: -r['gain'])
        total, n = sum(r['gain'] for r in rows), sum(r['count'] for r in rows)
        top = rows[0]
        why = (f'Opened, {"they hold" if n > 1 else "it holds"} about {gold(total)} at today\'s prices '
               f'({", ".join(top["contents"][:3]) or "its contents"}{" and more" if top["contents"] else ""}), '
               f'more than selling {"them" if n > 1 else "it"} unopened. Then sell what is inside the same way.')
        if any(r['locked'] for r in rows):
            why += ' Some are locked: pick the lock (rogues, Lockpicking) or use a key first.'
        names = rows[0]['name'] if len(rows) == 1 else f'{n} containers'
        out.append(_action('cash_open', f'Open your {names}' if len(rows) > 1 else f'Open your {n} {names}', why, total,
                           n * OPEN_SECONDS / 60 + 1, _weighted_confidence(rows, total), items=rows[:SHOWN_ITEMS],
                           more=max(0, len(rows) - SHOWN_ITEMS)))
    # 3) junk: anything a vendor pays more for than the AH, except gear (it may be yours)
    junk = [h for h in holdings if h['channel'] == 'vendor' and h['value'] > 0
            and (h.get('quality', 1) == 0 or h.get('class_id') not in GEAR_CLASSES)]
    if junk:
        rows = [{**_item_line(h, h['count'], h['value']), 'gain': h['value'] * h['count'], 'confidence': 1.0}
                for h in junk]
        rows.sort(key=lambda r: -r['gain'])
        total = sum(r['gain'] for r in rows)
        greys = sum(1 for h in junk if h.get('quality', 1) == 0)
        why = (f'A vendor pays {gold(total)} for {len(rows)} of your items ({greys} grey junk, the rest worth more at a '
               f'vendor than on the AH). Weapons and armour are left out in case you wear them.')
        out.append(_action('cash_vendor', 'Sell your junk to a vendor', why, total, VENDOR_TRIP_MIN, 1.0,
                           items=rows[:SHOWN_ITEMS], more=max(0, len(rows) - SHOWN_ITEMS)))
    return out


def _own_use(h: dict) -> bool:
    """Something you probably use yourself rather than sell (grey junk never is)."""
    if h.get('quality', 1) == 0:
        return False
    cls, sub = h.get('class_id'), h.get('subclass_id')
    if cls == CONSUMABLE:
        return not (sub == FOOD and h.get('reagent'))        # raw fish and meat are cooking materials
    return (cls, sub) == SPELL_REAGENT or (cls in GEAR_CLASSES[:1] and sub in TOOL_SUBCLASSES)


def _clean(o) -> bool:
    return not (set(o.flags) & BAD_FLAGS)


def _vendor_text(vendors: list[dict]) -> str:
    v = next((v for v in vendors or [] if not v.get('event') and v.get('located')), None)
    if not v:
        return 'a vendor'
    where = v.get('zone') or ''
    c = v.get('coords')
    if where and isinstance(c, (list, tuple)) and len(c) >= 2:
        where += f' {float(c[0]):.0f}, {float(c[1]):.0f}'
    return f'{v["name"]} ({where})' if where else v['name']


def _mats_text(mats: list[dict], crafts: int) -> str:
    parts = []
    for m in mats[:4]:
        n = m['count'] * crafts
        src = 'from a vendor' if m.get('source') == 'vendor' else 'on the AH'
        parts.append(f'{count_text(n)} {m["name"]} {src}')
    return ', '.join(parts) + (' and more' if len(mats) > 4 else '')


def _sell_text(o) -> str:
    d = o.detail
    if d.get('sell_channel') == 'vendor':
        return 'sell them to a vendor'
    price = d.get('sell_price') or d.get('ah_sell')
    return f'list at {gold(price)} each' if price else 'list them on the AH'


def routine(o, time_value: int) -> dict:
    """A daily craft or vendor flip as one concrete instruction."""
    d = o.detail
    n = max(1, round(o.units_day))
    ef = d.get('effort') or {}
    spd = (d.get('liquidity') or {}).get('sold_per_day') or d.get('sold_per_day') or 0
    if o.kind == 'craft':
        per = d.get('product_count') or 1
        made = f' ({count_text(n * per)} in all)' if per != 1 else ''
        title = (f'Craft {_name(o)} {n} time{"s" if n != 1 else ""}{made}: buy {_mats_text(d.get("mats") or [], n)}; '
                 f'{_sell_text(o)}')
    else:
        title = (f'Buy {n} {_name(o)} from {_vendor_text(d.get("vendors"))} at {gold(o.cost_unit)} each; '
                 f'{_sell_text(o)}')
    if d.get('sell_channel') == 'vendor':
        why = (f'A vendor buys the result, so nothing waits on the AH: {gold(o.profit_unit)} profit each, '
               f'about {count_text(o.units_day)} a day')
    else:
        why = (f'About {count_text(spd)} sell a day across the region; at your share that is about '
               f'{count_text(o.units_day)} a day at {gold(o.profit_unit)} profit each, after the AH cut')
    why += f' ({gold(o.daily)} a day'
    why += f', about {ef["minutes"]:g} minutes of your time).' if ef else ').'
    return _action('routine', title, why, o.daily, ef.get('minutes') or 3.0, d.get('confidence', 1.0),
                   o.cost_unit * o.units_day, key=o.key, item_id=o.item_id)


def _name(o) -> str:
    """The item's name from a row title such as 'Buy Junglevine Wine from vendor, sell on AH'."""
    t = o.title
    if o.kind == 'craft' and t.startswith('Craft '):
        t = t[len('Craft '):]
        per = o.detail.get('product_count') or 1
        return t[:-len(f' x{per:g}')] if per != 1 and t.endswith(f' x{per:g}') else t
    for pre, post in (('Buy cheap ', ' and relist'), ('Buy ', ' from vendor, sell on AH'), ('Buy ', ' on AH, sell to vendor')):
        if t.startswith(pre) and t.endswith(post):
            return t[len(pre):-len(post)]
    return t


def cooldowns(opps: list) -> list[dict]:
    """Once-a-day cooldown crafts you can make now: the best of each shared cooldown, done once if it's ready."""
    rows = [o for o in opps if o.kind == 'craft' and o.doable and _clean(o)
            and (o.detail.get('cooldown_hours') or 0) >= COOLDOWN_DAILY_HOURS and o.profit_unit > 0]
    rows.sort(key=lambda o: -o.profit_unit * o.detail.get('confidence', 1.0))
    seen, out = set(), []
    for o in rows:
        g = o.detail.get('cooldown_group') or o.key
        if g in seen:
            continue
        seen.add(g)
        d = o.detail
        shared = f', which shares its cooldown with {d["cooldown_shared_with"]} other recipes' if d.get('cooldown_shared_with') else ''
        why = (f'One craft earns {gold(o.profit_unit)} and the recipe can only be made every '
               f'{d["cooldown_hours"]:g} hours{shared}: do it whenever it is ready.')
        out.append(_action('cooldown', f'If your cooldown is ready: {d.get("recipe") or o.title} '
                                       f'(buy {_mats_text(d.get("mats") or [], 1)}; {_sell_text(o)})',
                           why, o.profit_unit, CRAFT_ONCE_MIN, d.get('confidence', 1.0), o.cost_unit,
                           key=o.key, item_id=o.item_id))
    return out


def snipe(o) -> dict:
    d = o.detail
    why = (f'At the last scan one was listed at {gold(d.get("min_buyout") or o.cost_unit)}, well under what it sells '
           f'for ({gold(d.get("relist_at"))}): about {gold(o.profit_unit)} profit if it is still there. It is from '
           f'one scan, so check the price in game first; it counts half in this plan.')
    return _action('snipe', f'If it is still listed: buy {_name(o)} at {gold(o.cost_unit)} or less and relist at '
                            f'{gold(d.get("relist_at"))}', why, o.profit_unit, SNIPE_MIN,
                   d.get('confidence', 1.0) * SNIPE_STILL_THERE, o.cost_unit, key=o.key, item_id=o.item_id)


def farm(o) -> dict:
    f = set(o.flags)
    if 'measured' in f:
        src = 'what you actually earned doing this (timed by ForeverMoneyBridge)'
    elif 'measured_pace' in f:
        src = 'Wowhead Forever loot counts at your own measured pace'
    else:
        src = 'Wowhead Forever counts at the pace set in Settings'
    why = f'About {gold(o.gph)} an hour, from {src}.'
    if o.detail.get('gph_with_pools') and o.detail.get('gph_with_pools') > (o.gph or 0):
        why += f' Fishing the pools you pass adds more (up to {gold(o.detail["gph_with_pools"])} an hour).'
    return _action('farm', f'Spend an hour: {o.title}', why, o.gph or 0, 60, o.detail.get('confidence', 1.0),
                   key=o.key, item_id=o.item_id)


def big_flip(o) -> dict | None:
    d = o.detail
    at_avg = d.get('profit_at_avg_sale')
    sure = min(o.profit_unit, at_avg) if at_avg is not None else o.profit_unit
    if sure < BIG_FLIP_MIN or o.units_day <= 0:
        return None
    every = 1 / o.units_day
    why = (f'One sale earns {gold(o.profit_unit)} at the lowest listing'
           + (f' or {gold(at_avg)} at the usual sale price' if at_avg is not None else '')
           + f', but you would sell about one every {count_text(every)} day{"" if abs(every - 1) < 0.05 else "s"}: '
             f'list one and wait. Counted at the lower profit.')
    ef = d.get('effort') or {}
    return _action('big_flip', f'{"Craft and list" if o.kind == "craft" else "List"} one {_name(o)}'
                               + (f' (buy it from {_vendor_text(d.get("vendors"))} at {gold(o.cost_unit)})'
                                  if o.kind == 'vendor_flip' else ''),
                   why, sure, ef.get('minutes') or 3.0, d.get('confidence', 1.0), o.cost_unit, key=o.key,
                   item_id=o.item_id)


def goal(by: dict, top: dict) -> dict | None:
    """The best unlock: a recipe a few skill points away (or a profession worth switching to)."""
    for sec, verb in (('level_up', 'level'), ('switch', 'learn')):
        for k in top.get(sec) or []:
            o = by.get(k)
            if not o:
                continue
            d = o.detail
            per_day = d.get('daily_if_affordable', o.daily)
            if per_day <= 0:
                continue
            if verb == 'level':
                title = f'Level {o.profession} to {d.get("skill_required")} for {o.title.replace("Craft ", "")}'
                why = (f'You have {o.profession} {o.needs.split("you have ")[-1].rstrip(")")}; at '
                       f'{d.get("skill_required")} this recipe would earn about {gold(per_day)} a day '
                       f'({gold(o.profit_unit)} each) once you have the gold for it.')
            else:
                title = f'Consider {o.profession}: {o.title}'
                why = (f'You do not have {o.profession}; this recipe alone would earn about {gold(per_day)} a day '
                       f'({gold(o.profit_unit)} each), well above your best routine.')
            return _action('goal', title, why, per_day, 0, d.get('confidence', 1.0), key=o.key, item_id=o.item_id)
    return None


def finish(actions: list[dict], time_value: int) -> list[dict]:
    """Value each action for today, drop what isn't worth its time, cap each type, keep the best, order them."""
    for a in actions:
        a['time_cost'] = int(a['minutes'] / 60 * time_value)
        a['value'] = int(a['gain'] * a['confidence'] - a['time_cost'])
        a['per_hour'] = int(a['gain'] * a['confidence'] / (a['minutes'] / 60)) if a['minutes'] else None
    kept, seen, keys = [], {}, set()
    for a in sorted(actions, key=lambda a: -a['value']):
        if a['value'] <= 0 or (a['key'] and a['key'] in keys):
            continue
        if seen.get(a['type'], 0) >= PER_TYPE.get(a['type'], DEFAULT_PER_TYPE):
            continue
        seen[a['type']] = seen.get(a['type'], 0) + 1
        keys.add(a['key'])
        kept.append(a)
        if len(kept) == MAX_ACTIONS:
            break
    # quick wins first, the long farming session last: order by gold per hour of your time
    kept.sort(key=lambda a: -(a['per_hour'] or 0))
    for i, a in enumerate(kept, 1):
        a['rank'] = i
    return kept


def build(opps: list, top: dict, holdings: dict, time_value: int, share: float, cut: float, gold_now: int) -> dict:
    """The whole plan: ranked actions, the long-term goal, totals."""
    by = {o.key: o for o in opps}
    actions = cash_in(holdings.get('items') or [], share, cut, holdings.get('ended_auctions') or 0)
    actions += cooldowns(opps)
    # top-pick rows are clean already; checked again so Classic-only or unsellable rows can never slip in
    pick = lambda sec, n: [by[k] for k in (top.get(sec) or []) if k in by and _clean(by[k])][:n]
    actions += [routine(o, time_value) for o in pick('now', 6)]
    actions += [snipe(o) for o in pick('snipes', 3)]
    actions += [farm(o) for o in pick('hourly', 4)]
    actions += [a for a in (big_flip(o) for o in pick('slow', 4)) if a]
    kept = finish(actions, time_value)
    needed = sum(a['gold_needed'] for a in kept)
    return {
        'actions': kept, 'goal': goal(by, top), 'time_value': time_value,
        'total_gain': sum(int(a['gain'] * a['confidence']) for a in kept),
        'total_minutes': round(sum(a['minutes'] for a in kept), 1),
        'gold_needed': needed, 'gold_now': gold_now, 'short_of_gold': needed > gold_now,
        'holdings_found': bool(holdings.get('found')), 'ended_auctions': holdings.get('ended_auctions') or 0,
        'considered': len(actions), 'dropped': len(actions) - len(kept),
    }
