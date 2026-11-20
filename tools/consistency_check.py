"""Cross-view consistency on real data: the same number shown in two places must agree.

Builds the app as it runs (without writing anything to your AddOns folder) and compares what each tab's own function
returns: Top picks, the plan, Crafting, Professions, Niches, Sniper, Biggest markets, the item drawer, the Market tab,
Investments, the levelling planner, My bags and the purse. Run: python tools/consistency_check.py
Extended 2026-11-20 for the comprehensive review (B1, part 1): every pair the review lists, each with how many were
compared, so a check that compared nothing shows up.
"""
import sys
import threading

sys.path.insert(0, '.')
from wfm import levelling
from wfm.alerts import EventLog
from wfm.app import App
from wfm.engine import Engine, vendor_sell
from wfm.history import History
from wfm.paths import GamePaths, find_wow_dir
from wfm.pricing import ah_buy, ah_sell, proceeds, sold_per_day, usual_sale
from wfm.settings import Settings
from wfm.world import World

app = App.__new__(App)
app.settings = Settings()
app.world = World(GamePaths(find_wow_dir(app.settings.snapshot().get('wow_dir'))), app.settings, lambda m: None)
app.world.load_all()
app.history, app.events, app.result, app.generated_at, app.audit, app.listeners = History(), EventLog(), None, 0, [], []
app.lock, app._settings_dirty, app._force, app.tips = threading.RLock(), threading.Event(), threading.Event(), app._load_tips()
app._write_item_checks = lambda r: None          # never touch the AddOns folder from a check
app._write_prices = lambda r, s: None
app.broadcast = lambda *a, **k: None
app.recompute('consistency check')

w = app.world
s, _ = app.effective_settings()
e = Engine(w, s)
res = app.result
by = res['by_key']
cut = e.cut
problems, compared = [], {}


def check(name):
    def deco(fn):
        found = []
        n = fn(lambda *a: found.append(' '.join(str(x) for x in a)))
        compared[name] = (n, len(found))
        problems.extend(f'[{name}] {p}' for p in found[:5])
        if len(found) > 5:
            problems.append(f'[{name}] ... {len(found)} in all')
        return fn
    return deco


@check('plan steps vs their rows')
def _(P):
    n = 0
    for a in (res['plan'] or {}).get('actions') or []:
        o = by.get(a.get('key'))
        if not o:
            continue
        n += 1
        ef = o.detail.get('effort')
        if a['type'] == 'routine':
            if a['gain'] != o.daily:
                P('gain != row daily:', o.title, a['gain'], o.daily)
            if ef and abs(a['minutes'] - ef['minutes']) > 0.05:
                P('minutes != row minutes:', o.title, a['minutes'], ef['minutes'])
            if ef and a.get('per_hour') and abs(a['per_hour'] - ef['per_hour']) > 2:
                P('per hour != row:', o.title, a['per_hour'], ef['per_hour'])
        if a['type'] == 'farm' and o.gph and abs(a['gain'] - o.gph) > 2:
            P('farm gain != row gph:', o.title, a['gain'], o.gph)
    return n


@check('Top picks vs the tabs')
def _(P):
    views = {v['key']: v for v in app.opps({'limit': ['100000']})}
    n = 0
    for sec, rows in app.state()['top'].items():
        for t in rows:
            v = views.get(t['key'])
            n += 1
            if not v:
                P(sec, 'not in the tabs:', t['title'])
                continue
            for f in ('daily', 'profit_unit', 'cost_unit', 'units_day', 'gph', 'doable', 'flags'):
                if t.get(f) != v.get(f):
                    P(sec, t['title'], f, t.get(f), v.get(f))
    return n


@check('Niches vs their rows')
def _(P):
    n = 0
    for r in app.niches()['rows']:
        o = by.get(r['how']['key'])
        if not o:
            P('row missing:', r['name'])
            continue
        n += 1
        if r['how']['profit_unit'] != o.profit_unit:
            P('profit each:', o.title, r['how']['profit_unit'], o.profit_unit)
        if o.daily and r['profit_day'] != o.daily:
            P('profit a day:', o.title, r['profit_day'], o.daily)
    return n


@check('Professions tab vs Crafting')
def _(P):
    n = 0
    for r in app.professions()['rows']:
        for x in ((r.get('craft') or {}).get('now') or []):
            o = by.get(x['key'])
            n += 1
            if not o or o.daily != x['daily']:
                P(r['profession'], x.get('title'), x['daily'], o.daily if o else None)
    return n


@check('Professions tab vs Gathering and the levelling panel')
def _(P):
    n = 0
    for r in app.professions()['rows']:
        if r['kind'] == 'gathering':
            for part in ('now', 'full', 'classic_full'):
                g = (r.get('gather') or {}).get(part)
                if not g:
                    continue
                n += 1
                o = by.get(g['key'])
                if not o or int(o.gph or 0) != g['gph']:
                    P(r['profession'], part, g['title'], g['gph'], o.gph if o else None)
        lev = r.get('levelling')
        if r['kind'] == 'crafting' and lev and r['have'] and 1 < r['skill'] < 300:
            n += 1
            panel = app.levelling({'profession': [r['profession']], 'skill': [str(r['skill'])]})
            if panel.get('total') != lev.get('total'):
                P(r['profession'], 'levelling cost: Professions', lev.get('total'), 'panel', panel.get('total'))
    return n


@check('item drawer vs the tables')
def _(P):
    n = 0
    seen = set()
    for o in sorted(res['opportunities'], key=lambda o: -(o.daily or 0))[:300]:
        if o.item_id in seen:
            continue
        seen.add(o.item_id)
        d = app.item(o.item_id)
        it = w.gamedata.items.get(o.item_id)
        n += 1
        if d.get('vendor_sell') != vendor_sell(it) and d.get('vendor_sell') != (it.sell_price if it else None):
            P('vendor sell:', d['name'], d.get('vendor_sell'), vendor_sell(it))
        q = ah_sell(w.prices.get(o.item_id), e.sale_basis)
        if q and d.get('ah_sell') != q.value:
            P('AH sell:', d['name'], d.get('ah_sell'), q.value)
        if o.kind == 'vendor_flip' and d.get('vendor_price') != o.cost_unit:
            P('vendor price vs the flip:', d['name'], d.get('vendor_price'), o.cost_unit)
        if o.kind == 'craft' and o.detail.get('sell_channel', 'AH') == 'AH' and o.detail.get('sell_price') \
                and q and o.detail['sell_price'] != q.value:
            P('craft sale price vs drawer:', o.title, o.detail['sell_price'], q.value)
    return n


@check('AH cut taken once (crafts)')
def _(P):
    n = 0
    for o in res['opportunities']:
        if o.kind != 'craft' or o.detail.get('sell_channel', 'AH') != 'AH' or o.detail.get('disenchant'):
            continue
        q = ah_sell(w.prices.get(o.item_id), e.sale_basis)
        unit = e.sell_value(o.item_id)[0]
        if not q or not unit:
            continue
        n += 1
        if unit != proceeds(q, cut):
            P(o.title, unit, proceeds(q, cut))
        if o.detail.get('revenue') != int(unit * (o.detail.get('product_count') or 1)):
            P('revenue:', o.title, o.detail.get('revenue'), unit, o.detail.get('product_count'))
    return n


@check('row arithmetic (profit a day = profit each x a day)')
def _(P):
    n = 0
    for o in res['opportunities']:
        if o.kind not in ('craft', 'vendor_flip') or not o.units_day:
            continue
        n += 1
        expect = o.profit_unit * o.units_day
        if abs(o.daily - expect) > max(1.0, 0.006 * abs(expect)) + abs(o.profit_unit) * 0.005:
            P(o.title, o.daily, o.profit_unit, o.units_day)
    return n


@check('Market tab vs TSM and the drawer')
def _(P):
    n = 0
    for iid in list({o.item_id for o in res['opportunities']})[:150]:
        p = w.prices.get(iid)
        if not p:
            continue
        m = app.market(iid)
        n += 1
        if m.get('prices') != p:
            P('prices differ from TSM:', m.get('name'))
        d = app.item(iid)
        if m.get('vendor_sell') != d.get('vendor_sell'):
            P('vendor sell, Market vs drawer:', m.get('name'), m.get('vendor_sell'), d.get('vendor_sell'))
    return n


@check('Investments vs TSM and the drawer')
def _(P):
    n = 0
    for r in app.investments()['items']:
        p = w.prices.get(r['item_id']) or {}
        n += 1
        for f, k in (('min_buyout', 'minBuyout'), ('market', 'marketValue'), ('region_sale', 'regionSale'),
                     ('sold_per_day', 'regionSoldPerDay')):
            if r.get(f) != p.get(k):
                P(r['name'], f, r.get(f), p.get(k))
        b = ah_buy(p)
        if r.get('buy') != (b.value if b else None):
            P(r['name'], 'buy', r.get('buy'), b.value if b else None)
        d = app.item(r['item_id'])
        if r.get('vendor_sell') != d.get('vendor_sell'):
            P(r['name'], 'vendor sell vs drawer', r.get('vendor_sell'), d.get('vendor_sell'))
    return n


@check('Biggest markets vs TSM and the rows')
def _(P):
    n = 0
    page = app.markets({'limit': ['400']})
    for r in page['rows']:
        p = w.prices.get(r['item_id'])
        n += 1
        if r['price'] != int(usual_sale(p)) or r['sold_per_day'] != sold_per_day(p):
            P(r['name'], r['price'], usual_sale(p), r['sold_per_day'], sold_per_day(p))
        if r['gold_a_day'] != int(r['sold_per_day'] * r['price']):
            P('gold a day:', r['name'], r['gold_a_day'])
        for way in r['ways']:
            o = by.get(way['key'])
            if not o or way['value'] != int((o.gph if way['per'] == 'an hour' else o.daily) or 0):
                P('way in:', r['name'], way['title'], way['value'], (o.gph, o.daily) if o else None)
    return n


@check('Sniper vs TSM')
def _(P):
    n = 0
    for r in app.sniper()['rows']:
        p = w.prices.get(r['item_id']) or {}
        n += 1
        if r['sold_per_day'] != round(sold_per_day(p), 1):
            P(r['name'], r['sold_per_day'], sold_per_day(p))
    return n


@check('levelling planner vs Crafting (product value)')
def _(P):
    lev_opts = {}
    real_plan = levelling.plan
    levelling.plan = lambda options, *a, **k: (lev_opts.update({x.spell_id: x for x in options}), real_plan(options, *a, **k))[1]
    for prof in ('Leatherworking', 'Tailoring', 'Alchemy', 'Blacksmithing', 'Engineering', 'Cooking'):
        e.levelling(prof, 1)
    levelling.plan = real_plan
    n = 0
    for o in res['opportunities']:
        x = lev_opts.get(o.detail.get('recipe_spell')) if o.kind == 'craft' and not o.detail.get('disenchant') else None
        if not x or {'hard_to_sell', 'no_sales_data'} & set(o.flags):
            continue
        n += 1
        rev = o.detail.get('revenue')
        sp, usual = o.detail.get('sell_price'), usual_sale(w.prices.get(o.item_id))
        if sp and usual and usual < sp:      # the planner sells at the lower of the listing and the usual sale (2026-11-19)
            rev = max(int(int(usual * (1 - cut)) * (o.detail.get('product_count') or 1)), x.vendor_value)
        if rev != max(x.ah_value, x.vendor_value):
            P(o.title, max(x.ah_value, x.vendor_value), rev)
    return n


@check('purse vs My bags')
def _(P):
    inv, purse = app.inventory(), app.purse()
    me, key = purse.get('me'), e.character()
    mine = [c for c in inv if key and c['character'].split('-')[0] == key.split('-')[0]]
    if me and mine and abs(me['bags_bank'] - mine[0]['total']) > 1:
        P('bags+bank:', me['bags_bank'], mine[0]['total'])
    return 1 if me and mine else 0


@check('plan cash-in vs My bags values')
def _(P):
    hold = {h['item_id']: h for h in e.my_holdings(e.valuer(res['best_use']))['items']}
    n = 0
    for a in (res['plan'] or {}).get('actions') or []:
        for it in a.get('items') or []:
            h = hold.get(it.get('item_id'))
            # the item line's value each is `unit` (until 2026-11-20 this looked for `each` and compared nothing)
            if h and it.get('unit') is not None and a['type'] in ('cash_ah', 'cash_vendor', 'cash_open'):
                n += 1
                if it['unit'] != h['value']:
                    P(a['type'], it.get('name'), it['unit'], h['value'])
    return n


@check('Data health and header counts vs the tabs')
def _(P):
    st = app.state()
    kinds = {}
    for o in res['opportunities']:
        kinds[o.kind] = kinds.get(o.kind, 0) + 1
    if st['counts'] != kinds:
        P('counts per kind:', st['counts'], kinds)
    page = app.markets({})
    rows = app._markets_rows
    if page['yours'] != sum(1 for r in rows if r['yours']) or page['all'] != len(rows):
        P('Biggest markets counts:', page['yours'], page['all'])
    return len(kinds) + 1


print(f"{len(problems)} problems")
for name, (n, k) in compared.items():
    print(f'  {name}: {n} compared, {k} differ' + ('  <- compared nothing' if not n else ''))
for p in problems[:60]:
    print(' -', p)
