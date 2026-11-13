"""Data audits: cross-check every source against the others so wrong numbers get caught, not trusted.

Run on every recompute (shown on the Data health page) and from the command line:
    python -m wfm.audit
"""
from __future__ import annotations

from .engine import PROFESSIONS


def _check(name, status, detail, examples=None):
    return {'name': name, 'status': status, 'detail': detail, 'examples': (examples or [])[:10]}


def run(world, engine) -> list[dict]:
    out = []
    gd, su, q, prices = world.gamedata, world.skillup, world.questie, world.prices
    if not gd:
        return [_check('Game data loaded', 'fail', 'No game data.')]

    # 1. Game tables match the installed client.
    cb = world.client_build
    out.append(_check('Game data matches your client build', 'pass' if cb == gd.build else 'fail',
                      f'client {cb}, tables {gd.build}'))

    # 2. Vendor prices: ours vs SkillUpForever's independent list.
    diffs = [(i, engine.name(i), p, gd.items[i].buy_price) for i, p in su.vendor_prices.items()
             if i in gd.items and gd.items[i].buy_price and gd.items[i].buy_price != p]
    out.append(_check('Vendor prices agree with SkillUpForever', 'pass' if not diffs else 'warn',
                      f'{len(su.vendor_prices)} compared, {len(diffs)} differ', [f'{n} ({i}): {a} vs {b}' for i, n, a, b in diffs]))

    # 3. Items an old list says vendors sell, but Questie's Forever data has no vendor for.
    phantom = [f'{engine.name(i)} ({i})' for i in su.vendor_prices if not engine.vendor_price(i)]
    out.append(_check('Vendor-sold items confirmed by a Forever vendor', 'pass' if not phantom else 'warn',
                      f'{len(phantom)} listed as vendor-sold with no vendor you can use (treated as not vendor-sold)', phantom))

    # 4. Recipes: ours vs SkillUpForever's.
    ours = {r.spell_id: r for r in gd.recipes}
    reag_diff, out_diff = [], []
    for sid, d in (su.recipe_data or {}).items():
        r = ours.get(sid)
        if not r:
            continue
        theirs = sorted((x['itemID'], x['quantity']) for x in d.get('reagents', []))
        if theirs != sorted(r.reagents):
            reag_diff.append(f'{r.name}: SkillUp {theirs} vs game {sorted(r.reagents)}')
        o = d.get('output')
        if isinstance(o, dict) and (o.get('itemID') != r.product_id or abs(float(o.get('quantity', 1)) - r.product_count) > 0.01):
            out_diff.append(f'{r.name}: SkillUp {o} vs game {r.product_id} x{r.product_count}')
    note = '' if su.source_build == gd.build else f' (SkillUp data is from build {su.source_build}; differences may be real game changes)'
    out.append(_check('Recipe ingredients agree with SkillUpForever', 'pass' if not reag_diff else 'warn',
                      f'{len(reag_diff)} recipes differ{note}', reag_diff))
    out.append(_check('Recipe outputs agree with SkillUpForever', 'pass' if not out_diff else 'warn',
                      f'{len(out_diff)} differ', out_diff))

    # 5. Skill requirements known exactly.
    crafts = [r for r in gd.recipes if r.profession in PROFESSIONS and r.reagents]
    exact = sum(1 for r in crafts if (su.thresholds.get(r.spell_id) or [0])[0] > 1)
    unverified = sum(1 for r in crafts if r.spell_id not in su.thresholds)
    out.append(_check('Recipe skill requirements', 'pass' if exact / max(len(crafts), 1) > 0.8 else 'warn',
                      f'{exact} of {len(crafts)} exact; others estimated as yellow - 40. '
                      f'{unverified} recipes not in SkillUp\'s list are hidden unless you enable unverified recipes.'))

    # 6. TSM values are in range.
    bad_rate = [i for i, p in prices.items() if not 0 <= p.get('regionSalePercent', 0) <= 1]
    neg = [i for i, p in prices.items() if any(v < 0 for v in p.values())]
    out.append(_check('TSM values in valid ranges', 'pass' if not bad_rate and not neg else 'fail',
                      f'{len(bad_rate)} sale rates outside 0-1, {len(neg)} negative values'))

    # 7. TSM items exist in game data.
    unknown = [i for i in prices if i not in gd.items]
    partial = [i for i in prices if i in gd.items and gd.items[i].partial]
    no_sell = [i for i in partial if not gd.items[i].sell_price]
    out.append(_check('TSM items exist in game data', 'pass' if len(unknown) < 0.02 * max(len(prices), 1) else 'warn',
                      f'{len(prices)} priced items: {len(prices) - len(partial) - len(unknown)} fully in game tables, '
                      f'{len(partial)} filled from Wowhead tooltips/Questie ({len(no_sell)} without a known vendor price yet), '
                      f'{len(unknown)} unknown', [str(i) for i in unknown]))

    # 8. Realm present.
    realm = world.settings.snapshot().get('realm')
    realms = world.price_data.realms() if world.price_data else []
    out.append(_check('Your realm is in the TSM data', 'pass' if realm in realms else 'fail',
                      f'looking for "{realm}", TSM has {realms}'))

    # 9. Price sanity: listings wildly above the region average distort "sell" prices.
    spikes = [f'{engine.name(i)}: lowest {p["minBuyout"]}c vs region {p["regionMarketValue"]}c'
              for i, p in prices.items()
              if p.get('numAuctions', 0) and p.get('regionMarketValue') and p.get('minBuyout', 0) > 5 * p['regionMarketValue']]
    out.append(_check('Price spikes (lowest listing > 5x region value)', 'pass' if len(spikes) < 50 else 'warn',
                      f'{len(spikes)} items; their sell price is capped at the realm market value and the actual '
                      f'average sale price', spikes))

    # 9b. Listings above what items actually sell for: priced at real sales instead.
    capped = [f'{engine.name(i)}: listed {min(p.get("minBuyout") or 10**12, p.get("marketValue") or 10**12)}c, '
              f'sells for {p["regionSale"]}c' for i, p in prices.items()
              if p.get('regionSale') and p.get('regionSoldPerDay', 0) >= 1
              and min(p.get('minBuyout') or 10**12, p.get('marketValue') or 10**12) > 1.5 * p['regionSale']]
    out.append(_check('Sale prices follow actual sales', 'pass',
                      f'{len(capped)} actively traded items are listed 1.5x+ above what they actually sell for; '
                      f'they are valued at the real average sale price, not the listing', capped))

    # 10. Questie vendor items have a vendor price.
    if q:
        no_price = [f'{engine.name(i)} ({i})' for i, qi in q.items.items() if qi.get('vendors') and i in gd.items
                    and not gd.items[i].buy_price]
        out.append(_check('Vendor items have a buy price', 'pass' if len(no_price) < 50 else 'warn',
                          f'{len(no_price)} vendor items without a price in game data', no_price))

    # 11. Classic fishing tables vs Forever data (your catches + Wowhead Forever counts).
    if getattr(world, 'classic_fishing', None):
        rows = [o for o in engine.fishing_spots({}) if o.detail.get('forever') and o.detail['forever_catches'] >= 100]
        agree, differ = [], []
        for o in rows:
            d = o.detail
            new = ', '.join(f['name'] for f in d['new_in_forever'][:4])
            ratio = (d['observed_value'] or 0) / d['classic_value'] if d.get('classic_value') else None
            worth = (f"worth per catch: Classic {d['classic_value']}c, Forever {d['observed_value']}c"
                     if ratio is not None else '')
            if d['classic_spot'] and not d['new_in_forever'] and not d['classic_missing'] and 0.7 <= ratio <= 1.3:
                agree.append(f"{d['zone']}: matches Classic \"{d['classic_spot']}\" ({d['forever_catches']:,} Forever "
                             f"catches; {worth})")
            elif d['classic_spot']:
                differ.append(f"{d['zone']}: closest Classic table \"{d['classic_spot']}\"; {worth}"
                              f"{'; Forever adds ' + new if new else ''}"
                              f"{'; lacks ' + ', '.join(f['name'] for f in d['classic_missing']) if d['classic_missing'] else ''}")
            else:
                differ.append(f"{d['zone']}: no Classic table explains Forever's catches here ({d['forever_catches']:,}); "
                              f"new: {new or '-'}")
        classic_only = sum(1 for o in engine.fishing_spots({}) if 'classic_unconfirmed' in o.flags)
        out.append(_check('Classic fishing tables vs Forever data', 'warn' if differ else 'pass',
                          f'{len(rows)} zones with 100+ Forever catches: {len(agree)} match Classic, {len(differ)} differ. '
                          f'{classic_only} fishing rows are Classic-only (unconfirmed, kept out of Top picks).',
                          differ + agree))

    # 12. Undervaluation watch: what you loot, carry or catch, valued through every channel.
    engine.valuer(engine.best_uses())
    watch = engine.undervaluation_watch()
    unknown = [u for u in watch if u['issue'] == 'contents_unknown']
    no_value = [u for u in watch if u['issue'] == 'no_value']
    open_it = [u for u in watch if u['issue'] == 'open_it']
    fmt = lambda u: f"{u['name']} ({u['item_id']}): {u['value']}c via {u['how']}; seen in {', '.join(u['where'])}"
    out.append(_check('Possibly undervalued items', 'warn' if unknown or no_value else 'pass',
                      f'{len(unknown)} openable items with unknown Forever contents (valued as a floor), '
                      f'{len(no_value)} with no known value, {len(open_it)} worth more opened than sold. '
                      f'Values follow current prices; container contents come from your opened containers '
                      f'(ForeverMoneyBridge) and Wowhead Forever.',
                      [fmt(u) for u in unknown + no_value + open_it]))
    return out


def summary(results: list[dict]) -> dict:
    s = {'pass': 0, 'warn': 0, 'fail': 0}
    for r in results:
        s[r['status']] = s.get(r['status'], 0) + 1
    return s


if __name__ == '__main__':
    from .engine import Engine
    from .paths import GamePaths, find_wow_dir
    from .settings import Settings
    from .world import World
    st = Settings()
    w = World(GamePaths(find_wow_dir(st.snapshot().get('wow_dir'))), st, log=lambda m: None)
    w.load_all()
    for r in run(w, Engine(w, st.snapshot())):
        print(f"[{r['status'].upper():4}] {r['name']}: {r['detail']}")
        for ex in r['examples'][:5]:
            print(f'         - {ex}')
