"""Data audits: cross-check every source against the others so wrong numbers get caught, not trusted.

Run on every recompute (shown on the Data health page) and from the command line:
    python -m wfm.audit
"""
from __future__ import annotations

from . import coverage, everloot, foreverrecipes, gatherlite, interactions, wowhead_items
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

    # 9a. Price health: odd lowest listings (valued at the recent average instead).
    from .pricing import ah_sell
    odd = [f'{engine.name(i)}: lowest {p.get("minBuyout")}c with {p.get("numAuctions")} listed, recent average '
           f'{p.get("marketValue")}c' for i, p in prices.items() if 'price_looks_off' in (ah_sell(p).flags if ah_sell(p) else ())]
    out.append(_check('Odd lowest listings', 'pass',
                      f'{len(odd)} items have only a few listings far from their recent average; they are valued at '
                      f'the recent average until more listings confirm the new price', odd))

    # 9b. Listings above what items actually sell for: priced at real sales instead.
    capped = [f'{engine.name(i)}: listed {min(p.get("minBuyout") or 10**12, p.get("marketValue") or 10**12)}c, '
              f'sells for {p["regionSale"]}c' for i, p in prices.items()
              if p.get('regionSale') and p.get('regionSoldPerDay', 0) >= 1
              and min(p.get('minBuyout') or 10**12, p.get('marketValue') or 10**12) > 1.5 * p['regionSale']]
    basis = world.settings.snapshot().get('sale_price_basis', 'realm')
    safe = basis in ('actual_sales', 'lower', 'realm')
    out.append(_check('Listings far above actual sales', 'pass' if safe else 'warn',
                      f'{len(capped)} actively traded items are listed 1.5x+ above what they actually sell for. '
                      f'Sale price basis: '
                      + ('the lower of the lowest listing and the usual sale price, so they are valued at what they '
                         'usually sell for ("up to" shows the lowest listing)' if basis == 'lower' else
                         'actual sales, so they are valued at what they sell for' if basis == 'actual_sales' else
                         "your realm's lowest listing (your choice); those 3x+ above what sells are flagged and kept out "
                         'of Top picks, and each row shows the profit at the usual sale price too' if basis == 'realm' else
                         'lowest buyout, so these may not sell at the price shown (flag "sells for less")') + '.',
                      capped))

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

    def untrusted_note(w):
        bad = [(s, a, g) for (s, a), g in (getattr(w, 'source_grades', None) or {}).items() if not g['trusted']]
        if not bad:
            return ''
        parts = [f"{a.replace('_', ' ')} from {s} data was wrong in {g['rate']:.0%} of {g['checked']} checks" for s, a, g in bad]
        return (' Not trusted until checked in game: ' + '; '.join(parts) +
                f' ({getattr(w, "untrusted_items", 0):,} unchecked items affected; their vendor price is treated as unknown'
                ' and they are first in line for checks).')

    # 11b. Item data verified by your own game client (ForeverMoneyBridge item checks): which sources were right.
    checked = [it for it in gd.items.values() if it.checked]
    by_src: dict[str, list] = {}
    for it in checked:
        by_src.setdefault(it.checked['against'], []).append(it)
    rows, worst = [], 0.0
    for src, its in sorted(by_src.items()):
        bad = [it for it in its if it.checked['differs']]
        rate = len(bad) / len(its)
        if src in ('client', 'server', 'server-new', 'wowhead') and len(its) >= 20:
            worst = max(worst, rate)
        rows.append(f'{src}: {len(its)} checked, {len(bad)} differed ({rate:.0%})')
    examples = [f"{it.name} ({it.id}): {', '.join(it.checked['differs'])} differed from {it.checked['against']} data"
                for it in checked if it.checked['differs']][:10]
    disagree = world.source_disagreements() if hasattr(world, 'source_disagreements') else []
    out.append(_check('Item data checked in your game', 'warn' if worst > 0.05 or not checked else 'pass',
                      (f'{len(checked)} items verified by your game client; ' + '; '.join(rows) if checked else
                       'No items verified in game yet: log in (or /reload) with ForeverMoneyBridge 1.4+, then /reload '
                       'again a minute later.') + f' {len(disagree)} items where the server data and Wowhead disagree '
                      f'are queued for checking.' + untrusted_note(world), examples))

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

    # Forever source data for every material and item (the user's top priority, 2026-11-14)
    try:
        read = getattr(world, 'forever_pages', None) or {}
        cov = coverage.audit(gd.items, prices, q.items if q else {}, gd.recipes,
                             getattr(world, 'forever_skinning', None), getattr(world, 'forever_fishing', None),
                             pages=wowhead_items.page_kinds(read), node_items=wowhead_items.covered_by_objects(read),
                             unlooted=wowhead_items.no_sources(read),
                             fish_hint=coverage.fish_items(getattr(world, 'classic_fishing', None)))
        kinds = ', '.join(f'{coverage.KIND_TEXT[k]} {c[0]} of {c[1]}' for k, c in sorted(cov['by_kind'].items()))
        out.append(_check('Forever source data for every material', 'warn' if cov['queue'] else 'pass',
                          f"{cov['materials_covered']} of {cov['materials']} traded materials (and {cov['covered']} of "
                          f"{cov['total']} traded items that are looted) have Forever data for every way they are "
                          f"obtained. By way: {kinds}. Without it, values per mob, node or pool are missing or come "
                          f"from WoW Classic. {len(cov['read_no_data'])} items have their Wowhead Forever page read, "
                          f"but Wowhead has not recorded Forever data yet for some ways of getting them (re-read "
                          f"later; listed after the queue). Next to read on Wowhead Forever (one item page covers "
                          f"every source; materials first, most traded value first):",
                          [coverage.describe(r) for r in cov['queue']]
                          + [coverage.describe(r) + ' (page read: no Forever data on Wowhead yet)'
                             for r in cov['read_no_data']]))
    except Exception as e:          # never let a check break the audit
        out.append(_check('Forever source data for every material', 'warn', f'Could not work it out: {e}'))

    # GatherLite: a second Forever source for where nodes, chests and pools are (QuestieDB is the first)
    try:
        gl = getattr(world, 'gatherlite', None) or {}
        if gl.get('nodes'):
            c = gatherlite.compare(gl, q.objects if q else {}, engine.name)
            pools = [r for r in c['only_gatherlite'] if 'School' in r['name'] or 'Debris' in r['name']
                     or 'Wreckage' in r['name']]
            out.append(_check('Node positions: QuestieDB vs GatherLite', 'info',
                              f"GatherLite (an addon, generated from Wowhead's Forever maps) lists {gl.get('points', 0):,} "
                              f"positions for {gl.get('objects', 0)} herbs, veins, chests and pools: {c['gatherlite']:,} distinct "
                              f"after merging repeats of the same node (points closer than {gatherlite.MERGE:g} of the "
                              f"map), against {c['questie']:,} QuestieDB spawns for the same objects. They differ zone by "
                              f"zone: GatherLite has Forever-only zones and more chests, QuestieDB has dungeons. Herb and "
                              f"ore spots still count nodes from QuestieDB. {len(c['only_gatherlite'])} objects only "
                              f"GatherLite places, {len(pools)} of them fishing pools: "
                              + ', '.join(f"{r['name']} ({r['gatherlite']})" for r in pools[:6]) + '.',
                              [f"{r['name']} ({r['object']}): GatherLite {r['gatherlite']:,}, QuestieDB {r['questie']:,}"
                               + (f"; zones only GatherLite has: {', '.join(engine.gd.zones.get(z, str(z)) for z in r['zones_only_gatherlite'][:5])}"
                                  if r['zones_only_gatherlite'] else '') for r in c['rows']]))
    except Exception as e:          # never let a check break the audit
        out.append(_check('Node positions: QuestieDB vs GatherLite', 'warn', f'Could not work it out: {e}'))

    # Vendor prices from TSM (read in game by ForeverMoneyBridge 1.6.2) against the game files
    rep = getattr(world, 'tsm_vendor_report', None) or {}
    if not rep.get('sell') and not rep.get('buy'):
        out.append(_check('Vendor prices from TSM', 'warn',
                          'None yet: ForeverMoneyBridge 1.6.2 reads TSM\'s VendorSell and VendorBuy in game about 30 '
                          'seconds after you log in; /reload after that minute to save them. Until then vendor prices '
                          'come from the game files (checked in game where possible).'))
    else:
        d = rep.get('differ') or []
        out.append(_check('Vendor prices from TSM', 'pass' if not d else 'info',
                          f"TSM's in-game vendor prices are used first: what a vendor pays for {rep.get('sell', 0):,} "
                          f"items, what a vendor charges for {rep.get('buy', 0):,} (TSM's merchant records). "
                          f"{len(d)} game-file sell prices differed from TSM's and were replaced.",
                          [f"{n} ({i}): game file {a}c ({src}), TSM {b}c" for i, n, a, b, src in d]))

    # Every way an item is made, and whether the app counts it (2026-11-19, after the Salt Shaker was missed)
    try:
        out.append(interactions.check(interactions.report(gd, prices), engine.name))
    except Exception as e:          # never let a check break the audit
        out.append(_check('Item interactions covered (every way an item is made)', 'warn', f'Could not work it out: {e}'))

    # ForeverRecipes: a second source of recipe skill levels, compared with SkillUpForever
    fr = getattr(world, 'forever_recipes', None)
    if fr and fr.recipes:
        c = foreverrecipes.compare(getattr(world, 'skillup_raw', None) or su, fr)
        filled = len(getattr(su, 'from_forever_recipes', ()) or ())
        out.append(_check('Recipe skill levels: SkillUpForever vs ForeverRecipes', 'pass' if not c['diff'] else 'warn',
                          f"{c['both']:,} recipes in both: {c['same']:,} have the same colours (yellow, green, grey), "
                          f"{len(c['diff'])} differ. ForeverRecipes fills {filled} gaps (recipes SkillUpForever lacks, "
                          f"like rogue poisons, or whose required skill it doesn't know, like Cured Rugged Hide); "
                          f"{len(c['only_forever_recipes'])} recipes only it has.",
                          [f"{engine.name(ours[s].product_id) if s in ours else s} ({s}): SkillUpForever {a}, ForeverRecipes {b}"
                           for s, a, b in c['diff']]))

    # Everloot: a second Forever source for drop rates (player uploads), compared with the Wowhead pages read (2c)
    try:
        out.append(everloot_check(getattr(world, 'everloot', None) or {}, getattr(world, 'forever_pages', None) or {},
                                  engine.name, q))
    except Exception as e:          # never let a check break the audit
        out.append(_check('Drop rates: Wowhead Forever vs Everloot', 'warn', f'Could not work it out: {e}'))
    return out


def everloot_check(ev: dict, pages: dict, item_name, q=None) -> dict:
    """The Data health entry: how well Everloot's rates agree with the Wowhead Forever counts for the same pairs."""
    name = 'Drop rates: Wowhead Forever vs Everloot'
    if not ev.get('rates'):
        return _check(name, 'info', 'No Everloot data saved (data/everloot/drops_*.json). ' + everloot.CREDIT)
    c = everloot.compare(ev, pages)
    n = c['counts']

    def label(kind, i):
        if kind == 'item':
            return item_name(i)
        rec = ((q.npcs if kind == 'npc' else q.objects).get(i) if q else None) or {}
        return rec.get('name') or f'{"mob" if kind == "npc" else "object"} {i}'

    detail = (f"Everloot (everloot.app) collects WoW: Forever loot from players' uploads: {c['everloot_rates']:,} public "
              f"drop rates (data of {c['as_of'] or '?'}). {len(c['pairs'])} of them are for a mob or object and item "
              f"that the Wowhead Forever pages read so far also count. Compared only where both sides looted at least "
              f"{everloot.MIN_LOOTS} times: {n['agree']} agree within chance, {n['gap']} are far apart (at least "
              f"{everloot.GAP_RATIO:g} times apart and {everloot.GAP_Z:g}+ standard errors: listed first); "
              f"{n['small']} pairs have too few loots on one side to say. Everloot's rates are not used in any number "
              f"yet: this check shows whether the two sources agree before they could fill each other's gaps. "
              + everloot.CREDIT)
    shown = [p for p in c['pairs'] if p['verdict'] != 'small']
    return _check(name, 'warn' if n['gap'] else 'pass', detail,
                  [('Far apart: ' if p['verdict'] == 'gap' else 'Agree within chance: ') + everloot.describe(p, label) for p in shown])


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
    from . import anomalies
    from .profile import apply
    eng = Engine(w, apply(st.snapshot(), w.profile)[0])
    for r in run(w, eng) + [anomalies.audit_check(Engine(w, apply(st.snapshot(), w.profile)[0]).run())]:
        print(f"[{r['status'].upper():4}] {r['name']}: {r['detail']}")
        for ex in r['examples'][:5]:
            print(f'         - {ex}')
