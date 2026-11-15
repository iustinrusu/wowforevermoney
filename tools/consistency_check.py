"""Cross-view consistency on real data: the same number shown in two places must agree. Run: python tools/consistency_check.py"""
import sys

sys.path.insert(0, '.')
from wfm import advisor, niches, valuation
from wfm.app import App
from wfm.engine import Engine
from wfm.pricing import ah_sell, fmt_money as f, proceeds

app = App.__new__(App)
from wfm.paths import GamePaths, find_wow_dir
from wfm.settings import Settings
from wfm.world import World
from wfm.history import History
st = Settings()
w = World(GamePaths(find_wow_dir(st.snapshot().get('wow_dir'))), st, log=lambda m: None)
w.load_all()
app.world, app.settings, app.history = w, st, History()
s, _ = app.effective_settings()
e = Engine(w, s)
res = e.run()
app.result = res
by = {o.key: o for o in res['opportunities']}
problems = []
P = lambda *a: problems.append(' '.join(str(x) for x in a))

# 1. plan steps vs the rows they come from
for a in (res['plan'] or {}).get('actions') or []:
    o = by.get(a.get('key'))
    if not o:
        continue
    ef = o.detail.get('effort')
    if a['type'] == 'routine':
        if a['gain'] != o.daily: P('plan gain != row daily:', o.title, a['gain'], o.daily)
        if ef and abs(a['minutes'] - ef['minutes']) > 0.05: P('plan minutes != row minutes:', o.title, a['minutes'], ef['minutes'])
        if ef and a.get('per_hour') and abs(a['per_hour'] - ef['per_hour']) > 2: P('plan per hour != row:', o.title, a['per_hour'], ef['per_hour'])
    if a['type'] == 'farm' and o.gph and abs(a['gain'] - o.gph) > 2: P('plan farm gain != row gph:', o.title, a['gain'], o.gph)

# 2. niches vs rows
for r in app.niches()['rows'] if hasattr(app, 'niches') else []:
    o = by.get(r['how']['key'])
    if o and r['how']['profit_unit'] != o.profit_unit: P('niche profit != row:', o.title)

# 3. professions tab vs crafting rows
adv = advisor.build(e, res['opportunities'], s.get('professions') or {}, set())
for r in adv['rows']:
    if r['kind'] != 'crafting':
        continue
    for x in r['craft']['now']:
        if by[x['key']].daily != x['daily']: P('professions now != row daily:', x['title'])

# 4. item drawer price vs the tables' sale price
for o in res['opportunities']:
    if o.kind == 'craft' and o.detail.get('sell_channel', 'AH') == 'AH':
        q = ah_sell(w.prices.get(o.item_id), s.get('sale_price_basis', 'realm'))
        unit = e.sell_value(o.item_id)[0]
        if q and unit and proceeds(q, e.cut) != unit and unit != (w.gamedata.items[o.item_id].sell_price or 0):
            P('drawer price != craft sale value:', o.title, proceeds(q, e.cut), unit)
            break

# 5. levelling planner product value vs the crafting row's revenue
lev_opts = {}
from wfm import levelling
real_plan = levelling.plan
levelling.plan = lambda options, *a, **k: (lev_opts.update({x.spell_id: x for x in options}), real_plan(options, *a, **k))[1]
for prof in ('Leatherworking', 'Tailoring', 'Alchemy'):
    e.levelling(prof, 1)
levelling.plan = real_plan
n = 0
for o in res['opportunities']:
    x = lev_opts.get(o.detail.get('recipe_spell')) if o.kind == 'craft' else None
    if x and not {'hard_to_sell', 'no_sales_data'} & set(o.flags) and o.detail.get('revenue') != max(x.ah_value, x.vendor_value):
        n += 1
        if n <= 3: P('levelling sale value != crafting revenue:', o.title, max(x.ah_value, x.vendor_value), o.detail.get('revenue'))
if n > 3: P(f'... {n} recipes in all')

# 6. purse bags+bank vs My bags total for the same character
inv = app.inventory()
purse = app.purse()
me = purse.get('me')
key = e.character()
mine = [c for c in inv if key and c['character'].split('-')[0] == key.split('-')[0]]
if me and mine and abs(me['bags_bank'] - mine[0]['total']) > 1:
    P('purse bags+bank != My bags total:', f(me['bags_bank']), f(mine[0]['total']))

# 7. plan cash-in values vs valuation of the same holdings
hold = {h['item_id']: h for h in e.my_holdings(e.valuer(res['best_use']))['items']}
for a in (res['plan'] or {}).get('actions') or []:
    for it in a.get('items') or []:
        h = hold.get(it.get('item_id'))
        if h and it.get('each') is not None and a['type'] in ('cash_vendor', 'cash_open') and it['each'] != h['value']:
            P('plan item value != holdings value:', it.get('name'), it['each'], h['value'])

print(len(problems), 'problems')
for p in problems[:30]:
    print(' -', p)
