"""Price checks: find the numbers that rest on a price that looks wrong (user's request, 2026-11-14: "we need a
system to detect these errors").

Every run, three checks, each a generalization of a real error found that day:

1. Second opinion on every craft and flip. The row's profit is recomputed independently at *typical* prices: the
   median of the realm listing average, the region listing average and the usual sale price (freak sale averages
   left out), ingredients from the AH at their typical price too, vendor prices as they are. A row that makes money
   only at today's unusual prices gets `price_check_fails` (kept out of Top picks and the plan); one that makes less
   than a third as much gets `price_check`. Caught: Masterwork Target Dummy's 608g craft (a 642g freak sale
   average), the Bronze Tube flip (+5s at the 14s listing, -3s at the usual ~5s).
2. Crafted worth. An ingredient whose "worth if crafted" is over 5x its sale price (and 1g+ more) while the product's
   market takes less than one of it a day: the worth holds for a single craft, not for a stack (Thorium Bar 21g 65s
   via Transmute: Arcanite, one every 47 hours; Ironweb Spider Silk 18g 11s via a product nobody bought). Since
   2026-11-15 every value counts crafted worth only for that many a day (valuation.capped_total), so this is a
   monitor ('info'): it lists them so a wrong recipe or price behind a crafted worth still stands out.
3. Data monitor. Counts in TSM's data that point at odd prices: freak sale averages, walls of listings far above
   sales, lone listings far above the region with no sales. Shown on Data health each run, so a jump stands out.
4. Item values (2026-11-20, after the farm meter valued one Rugged Hide at 2g 66s; it costs 7s 77c to buy): no value
   may be above what buying one costs on your realm's AH (a vendor's price aside). The valuer holds any that is
   (valuation.Valuer.breaches), and Data health shows it as an error. Crafts that fail the second opinion give their
   ingredients no crafted worth (Engine.best_uses), listed here too.
5. Values that swing (the app, at every price update): a value that moved by half or more beyond its own price's move
   rests on other items' prices (a thin margin between big ones), so it is listed for 24 hours (`swings`).

New findings on Top picks or the plan become events (alerts). `python -m wfm.anomalies` prints the full report.
"""
from __future__ import annotations

import statistics
import time

from .pricing import SALE_OUTLIER, WALL, fmt_money, listed, usual_sale

CHECKED_KINDS = ('craft', 'vendor_flip')     # snipes and AH->vendor buys are one-off snapshots by design
FAIL_SHARE = 1 / 3                           # under a third of the shown profit at typical prices: price_check
CRAFTED_FACTOR, CRAFTED_MIN = 5.0, 10000     # crafted worth over 5x the sale price and 1g+ above it


def typical_price(p: dict | None) -> tuple[int | None, dict]:
    """The median of the independent references for an item's price, and the references themselves."""
    p = p or {}
    refs = {'realm listing average': int(p.get('marketValue') or 0),
            'region listing average': int(p.get('regionMarketValue') or 0),
            'usual sale price': usual_sale(p)}
    vals = [v for v in refs.values() if v > 0]
    return (int(statistics.median(vals)) if vals else None), {k: v for k, v in refs.items() if v > 0}


THIN_LISTINGS, THIN_SHARE = 3, 0.5          # 1-3 listings under half the typical price: a one-off, not a cost


def second_opinion(o, prices: dict, cut: float) -> dict | None:
    """The row's profit per unit with every price it uses capped at what is typical, or None when there is nothing
    independent to compare with. It only corrects optimism: a sale price above the typical one comes down to it, and
    an ingredient bought from 1-3 listings at under half its typical price is costed at the typical price (it won't
    be there again). A price below typical with plenty listed is real today and stays."""
    d = o.detail or {}
    if o.kind == 'craft':
        per = float(d.get('product_count') or 1)
        sell_typ, refs = None, {}
        if d.get('sell_channel') == 'vendor':
            revenue = d.get('revenue') or 0
        else:
            sell_typ, refs = typical_price(prices.get(o.item_id))
            used = d.get('sell_price')
            if sell_typ is None or not used:
                return None
            revenue = int(min(used, sell_typ) * (1 - cut)) * per
        cost, thin = 0, []
        for m in d.get('mats') or []:
            unit = m['unit']
            if m.get('source') != 'vendor':
                mp = prices.get(m['item_id']) or {}
                typ, _ = typical_price(mp)
                if typ and (mp.get('numAuctions') or 0) <= THIN_LISTINGS and unit < THIN_SHARE * typ:
                    unit = typ
                    thin.append(m.get('name') or str(m['item_id']))
            cost += unit * m['count']
        return {'profit': int(revenue - cost), 'sell_typical': sell_typ, 'refs': refs, 'cost_typical': int(cost),
                'thin_mats': thin}
    if o.kind == 'vendor_flip':
        sell_typ, refs = typical_price(prices.get(o.item_id))
        used = d.get('ah_sell')
        if sell_typ is None or not used:
            return None
        return {'profit': int(min(used, sell_typ) * (1 - cut)) - o.cost_unit, 'sell_typical': sell_typ, 'refs': refs,
                'cost_typical': o.cost_unit, 'thin_mats': []}
    return None


def check_rows(opps, prices: dict, cut: float) -> list[dict]:
    """Flag crafts and flips whose profit rests on unusual prices (in place) and return the findings."""
    out = []
    for o in opps:
        if o.kind not in CHECKED_KINDS or o.profit_unit <= 0:
            continue
        so = second_opinion(o, prices, cut)
        if so is None:
            continue
        refs = ', '.join(f'{k} {fmt_money(v)}' for k, v in so['refs'].items())
        if so['thin_mats']:
            refs = (refs + '; ' if refs else '') + 'one-off cheap listings of ' + ', '.join(so['thin_mats'])
        if so['profit'] <= 0:
            flag, severity = 'price_check_fails', 'high'
            text = (f"At typical prices this loses {fmt_money(-so['profit'])} instead of making "
                    f"{fmt_money(o.profit_unit)}: it only pays at today's unusual prices ({refs}).")
        elif so['profit'] < o.profit_unit * FAIL_SHARE:
            flag, severity = 'price_check', 'warn'
            text = (f"At typical prices this makes {fmt_money(so['profit'])}, under a third of the "
                    f"{fmt_money(o.profit_unit)} shown ({refs}).")
        else:
            continue
        if flag not in o.flags:
            o.flags.append(flag)
        o.detail['price_check'] = {**so, 'text': text, 'severity': severity}
        out.append({'check': 'second_opinion', 'severity': severity, 'key': o.key, 'item_id': o.item_id,
                    'title': o.title, 'text': text, 'impact': int(o.daily)})
    return out


def check_crafted_worth(best_use: dict, sell_value, names) -> list[dict]:
    """Ingredients whose crafted worth is far above their sale price while the product's market takes under one a day."""
    out = []
    for iid, u in (best_use or {}).items():
        for which in ('doable', 'any'):
            value = u.get('doable_value') if which == 'doable' else u.get('value')
            units = u.get('doable_units_per_day') if which == 'doable' else u.get('units_per_day')
            if not value or units is None:
                continue
            sale = sell_value(iid)
            if value > CRAFTED_FACTOR * max(sale, 1) and value - sale >= CRAFTED_MIN and units < 1:
                recipe = u.get('doable_recipe') if which == 'doable' else u.get('recipe')
                how = ('counted at that worth for that many a day only, the rest at the sale price' if which == 'doable'
                       else "a recipe you can't make yet, so not counted")
                out.append({'check': 'crafted_worth', 'severity': 'info',
                            'item_id': iid, 'key': f'value:{iid}', 'title': names(iid), 'impact': int(value - sale),
                            'text': f"{names(iid)}: worth {fmt_money(value)} crafted into {recipe}, but that market takes "
                                    f"{units:.2f} a day at your share ({how}); otherwise it sells for "
                                    f"{fmt_money(sale)}."})
                break
    return out


def scan_prices(prices: dict) -> dict:
    """Counts of odd patterns in TSM's data (monitoring, not row flags), with the worst examples by traded value."""
    freak, wall, lone = [], [], []
    for iid, p in prices.items():
        spd = float(p.get('regionSoldPerDay') or 0)
        sale = int(p.get('regionSale') or 0)
        la = max(int(p.get('regionMarketValue') or 0), int(p.get('regionHistorical') or 0))
        if sale and la and sale > SALE_OUTLIER * la:
            freak.append((sale * max(spd, 0.1), iid))
        if listed(p) and sale and p['minBuyout'] > WALL * sale:
            wall.append((p['minBuyout'] * max(spd, 0.1), iid))
        if listed(p) and p.get('numAuctions', 0) <= 3 and not spd and la and p['minBuyout'] > WALL * la:
            lone.append((p['minBuyout'], iid))
    top = lambda rows: [i for _, i in sorted(rows, reverse=True)[:10]]
    return {'freak_sales': len(freak), 'walls': len(wall), 'lone_listings': len(lone),
            'examples': {'freak_sales': top(freak), 'walls': top(wall), 'lone_listings': top(lone)}}


def check_values(engine, best_use: dict) -> tuple[list[dict], dict]:
    """The buy-price rule: the values the valuer had to hold at the buy price (each an error: some part of the app
    worked out more), and a summary for Data health: values checked, crafted values capped by design, crafts that
    give no crafted worth because they fail the second opinion."""
    valuer = engine.valuer(best_use)
    out = []
    for b in valuer.breaches.values():
        out.append({'check': 'value_rule', 'severity': 'high', 'item_id': b['item_id'], 'key': f"value:{b['item_id']}",
                    'title': b['name'], 'impact': int(b['value'] - b['held']),
                    'text': f"{b['name']} came out at {fmt_money(b['value'])} ({b['how']}), above what buying one costs "
                            f"on your realm's AH ({fmt_money(b['buy'])}): held at {fmt_money(b['held'])}."})
    skipped = sorted(getattr(engine, 'no_crafted_worth', None) or [], key=lambda r: -r['today'])

    def example(r):
        typical = f"loses {fmt_money(-r['typical'])}" if r['typical'] < 0 else 'makes nothing'
        return (f"{r['recipe']} ({r['profession']}): makes {fmt_money(r['today'])} a craft at today's prices but "
                f"{typical} at typical prices, so it adds nothing to the worth of "
                f"{', '.join(engine.name(m) for m in r['mats'])}")
    summary = {'checked': len({k[0] for k in valuer._cache}), 'held': len(out),
               'capped': sum(1 for u in (best_use or {}).values() if u.get('doable_capped')),
               'no_crafted_worth': sum(1 for r in skipped if r['today'] > 0),
               'crafts_losing': sum(1 for r in skipped if r['today'] <= 0),
               'no_crafted_worth_examples': [example(r) for r in skipped if r['today'] > 0][:5]}
    return out, summary


SWING, SWING_MIN = 1.5, 1000       # a value 1.5x beyond its own price's move, and 10s or more: it swings
SWING_KEEP = 24 * 3600             # listed for a day


def own_price(p: dict | None) -> int:
    """An item's own price on your realm: the lowest listing, else the realm's listing average, else 0."""
    p = p or {}
    return int(p['minBuyout']) if listed(p) else int(p.get('marketValue') or 0)


def swings(prev: dict, cur: dict) -> list[int]:
    """Items whose value moved by SWING or more beyond their own price's move (and SWING_MIN or more): their value
    rests on other items' prices. prev and cur: item -> (value, own price), from two price updates in a row."""
    out = []
    for iid, (now, own_now) in cur.items():
        if iid not in prev:
            continue
        before, own_before = prev[iid]
        if abs(now - before) < SWING_MIN:
            continue
        moved = max(now, before) / max(min(now, before), 1)
        own_moved = max(own_now, own_before) / max(min(own_now, own_before), 1) if own_now and own_before else 1.0
        if moved >= SWING * own_moved:
            out.append(iid)
    return out


def run(engine, opps, best_use: dict) -> dict:
    """All checks for one engine run: row flags are set in place; returns the findings and the data monitor."""
    rows = check_rows(opps, engine.prices, engine.cut)
    crafted = check_crafted_worth(best_use, lambda i: engine.sell_value(i)[0], engine.name)
    held, values = check_values(engine, best_use)
    findings = sorted(rows + crafted + held, key=lambda f: ({'high': 0, 'warn': 1, 'info': 2}[f['severity']], -f['impact']))
    return {'findings': findings, 'monitor': scan_prices(engine.prices), 'values': values,
            'checked_at': int(time.time())}


def new_events(prev: dict | None, cur: dict, shown_keys: set[str]) -> list[dict]:
    """Events for findings that are new since the last run and touch something shown (Top picks, the plan)."""
    before = {(f['check'], f['key']) for f in ((prev or {}).get('findings') or [])}
    now = int(time.time())
    return [{'ts': now, 'type': 'price_check', 'key': f"check:{f['key']}", 'item_id': f.get('item_id'),
             'text': f"Price check: {f['title']}: {f['text']}", 'important': f['severity'] == 'high'}
            for f in cur.get('findings') or []
            if (f['check'], f['key']) not in before and f['key'] in shown_keys]


def audit_check(result: dict | None) -> dict:
    """The Data health entry."""
    a = (result or {}).get('anomalies') or {}
    fs, mon = a.get('findings') or [], a.get('monitor') or {}
    high = [f for f in fs if f['severity'] == 'high']
    warn = [f for f in fs if f['severity'] == 'warn']
    status = 'warn' if high or warn else 'pass'          # found rows are already handled: a warning, not a failure
    detail = (f"Second opinion on every craft and flip (typical prices: the median of the realm and region listing "
              f"averages and the usual sale price): {len(high)} only pay at today's unusual prices (kept out of Top "
              f"picks and the plan), {sum(1 for f in warn if f['check'] == 'second_opinion')} make under a third as "
              f"much at typical prices. {sum(1 for f in fs if f['check'] == 'crafted_worth')} ingredients are worth far "
              f"more crafted than sold, for under one a day (counted at crafted worth for that many a day only). "
              f"In TSM's data: {mon.get('freak_sales', 0)} freak sale "
              f"averages (ignored), {mon.get('walls', 0)} walls of listings far above sales (valued at sales), "
              f"{mon.get('lone_listings', 0)} lone listings far above the region with no sales.")
    return {'name': 'Price checks (second opinion)', 'status': status, 'detail': detail,
            'examples': [f"{f['title']}: {f['text']}" for f in fs if f['check'] != 'value_rule'][:10]}


def value_rule_check(result: dict | None) -> dict:
    """The Data health entry for the buy-price rule."""
    a = (result or {}).get('anomalies') or {}
    v = a.get('values') or {}
    held = [f for f in a.get('findings') or [] if f['check'] == 'value_rule']
    found = (f"{len(held)} came out above it and were held at the buy price: some part of the app broke the rule, "
             f"worth a look." if held else "none came out above it.")
    n = v.get('no_crafted_worth', 0)
    one = n == 1
    crafts = (f"{n:,} craft{'' if one else 's'} that only pay{'s' if one else ''} at today's unusual prices "
              f"give{'s' if one else ''}")
    detail = (f"An item you hold or loot is worth at most what buying one costs on your realm's AH (a vendor's price "
              f"aside): one you have only saves you buying one. Checked on every value the app works out "
              f"({v.get('checked', 0):,} items, as My bags and the farm meter use them): {found} By design, "
              f"{v.get('capped', 0)} crafted values are counted at the buy price (the craft's profit is on its Crafting "
              f"row), and {crafts} {'its' if one else 'their'} ingredients no crafted worth (nor do {v.get('crafts_losing', 0):,} that "
              f"lose money even at today's prices).")
    return {'name': 'Values never above the buy price', 'status': 'fail' if held else 'pass', 'detail': detail,
            'examples': ([f"{f['title']}: {f['text']}" for f in held] + v.get('no_crafted_worth_examples', []))[:10]}


def swing_check(found: dict) -> dict:
    """The Data health entry for values that swing: found = item -> {'text', 'ts'} from the last 24 hours."""
    rows = sorted(found.values(), key=lambda f: -f['ts'])
    detail = ("At every price update, each value is compared with the one before. A value that moved by half or more "
              "(and 10s or more) beyond its own price's move rests on other items' prices, such as a thin margin "
              "between two big prices, so it can be far off an hour later: treat it with care. "
              + (f"{len(rows)} in the last 24 hours." if rows else "None in the last 24 hours."))
    return {'name': 'Values that swing', 'status': 'warn' if rows else 'pass', 'detail': detail,
            'examples': [f['text'] for f in rows][:10]}


if __name__ == '__main__':
    from .engine import Engine
    from .paths import GamePaths, find_wow_dir
    from .profile import apply
    from .settings import Settings
    from .world import World
    st = Settings()
    w = World(GamePaths(find_wow_dir(st.snapshot().get('wow_dir'))), st, log=lambda m: None)
    w.load_all()
    res = Engine(w, apply(st.snapshot(), w.profile)[0]).run()
    c = audit_check(res)
    print(f"[{c['status'].upper()}] {c['detail']}")
    for f in res['anomalies']['findings']:
        print(f"  {f['severity']:4} {f['check']:14} {f['title']}: {f['text']}")
