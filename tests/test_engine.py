"""Engine math checked against hand-worked numbers. All money in copper."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wfm.engine import Engine
from wfm.gamedata import GameData, Item, Recipe
from wfm.history import History
from wfm.pricing import ah_buy, ah_sell, fmt_money, proceeds
from wfm.questie import QuestieDB
from wfm.skillup import SkillUpData

# ids
MAT_VENDOR, MAT_AH, PRODUCT, PHANTOM_SALT, ALLY_ONLY, LIMITED, CHEAP_SNIPE, FISH, COOKED = range(1, 10)


def item(iid, name, sell=0, buy=0, cls=7, sub=0, quality=1):
    return Item(id=iid, name=name, quality=quality, item_level=10, req_level=0, sell_price=sell, buy_price=buy,
                stack=20, class_id=cls, subclass_id=sub, bonding=0)


def make_world(prices, recipes=(), angler=None):
    gd = GameData(build='test')
    for it in [item(MAT_VENDOR, 'Vendor Spice', sell=1, buy=10), item(MAT_AH, 'Raw Meat'),
               item(PRODUCT, 'Tasty Dish', sell=20), item(PHANTOM_SALT, 'Phantom Salt', buy=4000),
               item(ALLY_ONLY, 'Alliance Malt', buy=50), item(LIMITED, 'Rare Pattern', buy=1000, cls=9),
               item(CHEAP_SNIPE, 'Trinket', sell=500), item(FISH, 'Raw Spotted Yellowtail', sell=4, cls=0),
               item(COOKED, 'Spotted Yellowtail', sell=6, cls=0)]:
        gd.items[it.id] = it
    gd.recipes = list(recipes)
    q = QuestieDB(
        items={MAT_VENDOR: {'vendors': [100]}, ALLY_ONLY: {'vendors': [101]}, LIMITED: {'vendors': [100]}},
        npcs={100: {'name': 'Horde Trader', 'friendlyToFaction': 'AH', 'zoneID': 1},
              101: {'name': 'Ally Trader', 'friendlyToFaction': 'A', 'zoneID': 1}})
    su = SkillUpData(thresholds={500: [100, 140, 160, 180]}, vendor_prices={PHANTOM_SALT: 4000},
                     limited_stock={LIMITED: {100: 3}})
    return SimpleNamespace(gamedata=gd, prices=prices, questie=q, skillup=su, angler=angler)


SETTINGS = {'gold': 1, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'min_sold_per_day': 0.5,
            'professions': {'Cooking': 150}, 'preferred': ['Cooking'], 'casts_per_hour': 200}


class PricingTests(unittest.TestCase):
    def test_buy(self):
        self.assertEqual(ah_buy({'numAuctions': 3, 'minBuyout': 100, 'marketValue': 120}).value, 100)
        q = ah_buy({'numAuctions': 0, 'marketValue': 120})
        self.assertEqual((q.value, q.flags), (120, ('none_listed',)))
        self.assertEqual(ah_buy({'regionMarketValue': 90}).flags, ('no_realm_data',))
        self.assertIsNone(ah_buy({}))

    def test_sell_at_lowest_buyout_by_default(self):
        # The user's rule: you list at the current lowest buyout, so that's the sale price.
        q = ah_sell({'numAuctions': 5, 'minBuyout': 500, 'marketValue': 600, 'regionSoldPerDay': 3, 'regionSale': 550})
        self.assertEqual((q.value, q.source), (500, 'lowest listing'))
        q = ah_sell({'numAuctions': 5, 'minBuyout': 900, 'marketValue': 600, 'regionSoldPerDay': 3})
        self.assertEqual(q.value, 900)
        q = ah_sell({'numAuctions': 5, 'minBuyout': 500, 'marketValue': 600, 'regionSale': 300, 'regionSoldPerDay': 1})
        self.assertEqual(q.value, 500)
        self.assertIn('sells_lower', q.flags, 'listed well above real sales: may not sell at that price')

    def test_odd_lone_listing_uses_recent_average(self):
        # one greedy listing (or a cheap dump about to be bought out) isn't the market
        q = ah_sell({'numAuctions': 1, 'minBuyout': 5000, 'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5})
        self.assertEqual((q.value, 'price_looks_off' in q.flags), (1000, True))
        q = ah_sell({'numAuctions': 2, 'minBuyout': 300, 'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5})
        self.assertEqual(q.value, 1000)
        q = ah_sell({'numAuctions': 40, 'minBuyout': 300, 'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5})
        self.assertEqual(q.value, 300, 'many listings at the new price: that is the market now')

    def test_actual_sales_basis_is_more_conservative(self):
        q = ah_sell({'numAuctions': 5, 'minBuyout': 900, 'marketValue': 600, 'regionSoldPerDay': 3}, 'actual_sales')
        self.assertEqual(q.value, 600)       # never more than the usual realm price
        q = ah_sell({'numAuctions': 5, 'minBuyout': 500, 'marketValue': 600, 'regionSoldPerDay': 3, 'regionSale': 450},
                    'actual_sales')
        self.assertEqual(q.value, 450)       # never more than what it actually sells for

    def test_nothing_listed_uses_the_actual_sale_price(self):
        # Regression from live data (2026-11-13): Hand Axe, nothing listed, realm listing average 2.5g, but it
        # really sells for 6.65s. It topped "Do these now" as a 2.37g vendor flip. Same under either basis.
        for basis in ('min_buyout', 'actual_sales'):
            q = ah_sell({'marketValue': 25050, 'regionMarketValue': 5399, 'regionSale': 665, 'regionSoldPerDay': 1.5,
                         'regionSalePercent': 1.0}, basis)
            self.assertEqual(q.value, 665)
            self.assertIn('none_listed', q.flags)
        self.assertEqual(ah_sell({'marketValue': 800, 'regionMarketValue': 600}).value, 600, 'no sales: lower listing average')

    def test_sell_flags(self):
        q = ah_sell({'numAuctions': 1, 'minBuyout': 5000, 'marketValue': 6000, 'regionMarketValue': 1000})
        self.assertIn('above_region', q.flags)
        self.assertIn('no_sales_data', q.flags)
        self.assertEqual(proceeds(ah_sell({'numAuctions': 1, 'minBuyout': 1000, 'marketValue': 1000, 'regionSoldPerDay': 1}), 0.05), 950)

    def test_money_format(self):
        self.assertEqual(fmt_money(12345), '1g 23s 45c')
        self.assertEqual(fmt_money(-205), '-2s 5c')
        self.assertEqual(fmt_money(7), '7c')


class EngineTests(unittest.TestCase):
    def craft_world(self, **over):
        recipe = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                        product_count=over.get('count', 1), reagents=[(MAT_VENDOR, 2), (MAT_AH, 1)],
                        trivial_low=140, trivial_high=180, min_rank=1)
        prices = {MAT_AH: {'numAuctions': 4, 'minBuyout': 100, 'marketValue': 120, 'regionSoldPerDay': 50},
                  PRODUCT: {'numAuctions': 6, 'minBuyout': 500, 'marketValue': 600, 'regionSoldPerDay': 10,
                            'regionSalePercent': 0.4}}
        return make_world(prices, [recipe])

    def test_craft_profit_hand_worked(self):
        res = Engine(self.craft_world(), dict(SETTINGS)).crafts()
        self.assertEqual(len(res), 1)
        o = res[0]
        # cost = 2 x 10 (vendor) + 1 x 100 (AH lowest listing) = 120
        self.assertEqual(o.cost_unit, 120)
        # sells at min(500 lowest, 600 market) = 500, after 5% cut = 475 -> profit 355
        self.assertEqual(o.profit_unit, 355)
        # demand 10/day x 20% share = 2/day; 1g affords 83 crafts -> 2/day
        self.assertEqual(o.units_day, 2)
        self.assertEqual(o.daily, 710)
        self.assertTrue(o.doable)
        self.assertEqual(o.detail['skill_required'], 100)

    def test_craft_multiple_output(self):
        o = Engine(self.craft_world(count=2), dict(SETTINGS)).crafts()[0]
        self.assertEqual(o.profit_unit, 2 * 475 - 120)
        self.assertEqual(o.units_day, 1)            # 2 products/day sell -> 1 craft/day

    def test_skill_gate(self):
        s = dict(SETTINGS, professions={'Cooking': 90})
        o = Engine(self.craft_world(), s).crafts()[0]
        self.assertFalse(o.doable)
        self.assertIn('Cooking 100', o.needs)

    def test_cant_afford(self):
        s = dict(SETTINGS, gold=0.01)               # 100 copper < 120 cost
        o = Engine(self.craft_world(), s).crafts()[0]
        self.assertEqual(o.units_day, 0)
        self.assertIn('cant_afford', o.flags)

    def test_phantom_vendor_item_is_not_vendor_sold(self):
        # Regression: an old list says vendors sell it, Questie's Forever data has no vendor -> not vendor-sold.
        e = Engine(make_world({}), dict(SETTINGS))
        self.assertIsNone(e.vendor_price(PHANTOM_SALT))

    def test_faction_filter(self):
        e = Engine(make_world({}), dict(SETTINGS))
        self.assertIsNone(e.vendor_price(ALLY_ONLY))
        self.assertIsNotNone(Engine(make_world({}), dict(SETTINGS, faction='A')).vendor_price(ALLY_ONLY))

    def test_observed_vendor_price_overrides_game_files(self):
        w = make_world({})
        w.profile = {'vendors': {100: {'items': {MAT_VENDOR: {'price': 90, 'qty': 3}}}}}
        e = Engine(w, dict(SETTINGS))
        self.assertEqual(e.vendor_price(MAT_VENDOR)[0], 30)      # 90 copper for 3 = 30 each, not the file's 10
        self.assertEqual(e.vendor_flags(MAT_VENDOR), ('vendor_price_seen',))

    def test_black_market_vendor_price_unknown_until_seen(self):
        # Frilled Lichen: game files say 1s 20c, the Black Market agent charges 4g 50s. A flip built on the file
        # price is fiction, so it isn't shown until ForeverMoneyBridge records the real price.
        prices = {LIMITED: {'numAuctions': 2, 'minBuyout': 5000, 'marketValue': 5000, 'regionSoldPerDay': 100}}
        w = make_world(prices)
        w.questie.npcs[100]['subName'] = 'Agent of the Black Market'
        e = Engine(w, dict(SETTINGS))
        self.assertIsNone(e.vendor_price(LIMITED))
        self.assertEqual([o for o in e.vendor_flips() if o.item_id == LIMITED], [])
        w.profile = {'vendors': {100: {'items': {LIMITED: {'price': 1500, 'qty': 1}}}}}     # seen in game
        e = Engine(w, dict(SETTINGS))
        self.assertEqual(e.vendor_price(LIMITED)[0], 1500)
        self.assertEqual(e.vendor_flags(LIMITED), ('vendor_price_seen',))

    def test_vendor_flip_with_limited_stock(self):
        prices = {LIMITED: {'numAuctions': 2, 'minBuyout': 5000, 'marketValue': 5000, 'regionSoldPerDay': 100,
                            'regionSalePercent': 0.5}}
        flips = Engine(make_world(prices), dict(SETTINGS)).vendor_flips()
        o = next(f for f in flips if f.item_id == LIMITED)
        self.assertEqual(o.profit_unit, 4750 - 1000)
        self.assertEqual(o.units_day, 3)            # capped at vendor stock
        self.assertIn('limited_stock', o.flags)

    def test_ah_to_vendor(self):
        prices = {CHEAP_SNIPE: {'numAuctions': 1, 'minBuyout': 200, 'marketValue': 900}}
        res = Engine(make_world(prices), dict(SETTINGS)).ah_to_vendor()
        self.assertEqual([(o.item_id, o.profit_unit) for o in res], [(CHEAP_SNIPE, 300)])

    def test_realm_dip_uses_recent_prices(self):
        base = {'numAuctions': 3, 'regionSoldPerDay': 10, 'regionSalePercent': 0.5}
        # Cheap vs launch-era 60-day average only: NOT a dip (prices are just deflating).
        deflating = dict(base, minBuyout=400, marketValue=500, regionMarketValue=520, regionSale=480, historical=5000)
        self.assertEqual(Engine(make_world({CHEAP_SNIPE: deflating}), dict(SETTINGS)).realm_dips(), [])
        # Cheap vs recent market, region and actual sales: a dip; relist at the lowest of the three.
        dip = dict(base, minBuyout=200, marketValue=1000, regionMarketValue=900, regionSale=800)
        o = Engine(make_world({CHEAP_SNIPE: dip}), dict(SETTINGS)).realm_dips()[0]
        self.assertEqual(o.detail['relist_at'], 800)
        self.assertEqual(o.profit_unit, 760 - 200)

    def test_best_use_and_fishing_zone(self):
        recipe = Recipe(spell_id=500, name='Spotted Yellowtail', profession='Cooking', skill_line=185, product_id=COOKED,
                        product_count=1, reagents=[(FISH, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        prices = {FISH: {'numAuctions': 5, 'minBuyout': 80, 'marketValue': 90, 'regionSoldPerDay': 50},
                  COOKED: {'numAuctions': 5, 'minBuyout': 200, 'marketValue': 210, 'regionSoldPerDay': 50}}
        angler = {'zones': {'Tanaris': {'c': 100, 'k': 90, 'e': 10, 'fish': {FISH: 40}}}}
        w = make_world(prices, [recipe], angler)
        e = Engine(w, dict(SETTINGS, own_logs_for_rates=True))   # opt-in
        best = e.best_uses()
        self.assertEqual(best[FISH]['value'], 190)              # cooked: 200 x 0.95 = 190 beats raw 76
        zone = e.fishing_spots(best)[0]                          # no Classic data: your log only
        self.assertEqual(zone.title, 'Fish in Tanaris')
        self.assertIn('forever_only', zone.flags)
        self.assertEqual(zone.profit_unit, int(190 * 40 / 90))   # value per catch
        # 200 casts/hour, all landed (90 caught + 10 got away of 100), 90% kept -> 180 catches/hour
        self.assertEqual(zone.gph, 15200)                        # 190 x 40/90 x 180 = the old per-cast 190 x 0.4 x 200

    def test_crafts_are_capped_by_ingredient_market_volume(self):
        # Regression: a vendor-sold craft assumed 200 crafts a day (6.36g/day for Mender's Mail Boots); you can't
        # buy more of an AH ingredient a day than its market trades at your share.
        recipe = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                        product_count=1, reagents=[(MAT_AH, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        prices = {MAT_AH: {'numAuctions': 5, 'minBuyout': 5, 'marketValue': 5, 'regionSoldPerDay': 10}}
        o = Engine(make_world(prices, [recipe]), dict(SETTINGS)).crafts()[0]
        self.assertEqual(o.profit_unit, 15)                      # vendor 20 - 5
        self.assertEqual(o.units_day, 2.0)                       # 10 sold/day x 20% share / 1 per craft
        self.assertEqual(o.detail['daily_if_affordable'], 30)
        self.assertEqual(o.detail['limited_by_mat'], 'Raw Meat')

    def test_values_use_recipes_you_can_make_now(self):
        # A fish was valued by a recipe needing Cooking 300 while the user has 150: it overstated catches.
        easy = Recipe(spell_id=500, name='Spotted Yellowtail', profession='Cooking', skill_line=185, product_id=COOKED,
                      product_count=1, reagents=[(FISH, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        hard = Recipe(spell_id=501, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                      product_count=1, reagents=[(FISH, 1)], trivial_low=320, trivial_high=360, min_rank=1)
        prices = {FISH: {'numAuctions': 5, 'minBuyout': 80, 'marketValue': 90, 'regionSoldPerDay': 50},
                  COOKED: {'numAuctions': 5, 'minBuyout': 200, 'marketValue': 210, 'regionSoldPerDay': 50},
                  PRODUCT: {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1000, 'regionSoldPerDay': 50}}
        w = make_world(prices, [easy, hard])
        w.skillup.thresholds[501] = [300, 320, 340, 360]
        e = Engine(w, dict(SETTINGS))
        best = e.best_uses()
        self.assertEqual((best[FISH]['value'], best[FISH]['doable']), (950, False))
        self.assertEqual((best[FISH]['doable_value'], best[FISH]['doable_recipe']), (190, 'Spotted Yellowtail'))
        v = e.valuer(best).value(FISH)
        self.assertEqual((v.value, v.channel), (190, 'craft'))
        self.assertIn('more_with_skill', v.flags)
        self.assertEqual(v.if_skilled['value'], 950)

    def test_without_skillup_crafts_show_flagged_not_vanish(self):
        # a friend without SkillUpForever saw an empty Crafting tab: every recipe was dropped as unverified
        hard = Recipe(spell_id=501, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                      product_count=1, reagents=[(FISH, 1)], trivial_low=120, trivial_high=160, min_rank=1)
        prices = {FISH: {'numAuctions': 5, 'minBuyout': 80, 'marketValue': 90, 'regionSoldPerDay': 50},
                  PRODUCT: {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1000, 'regionSoldPerDay': 50}}
        w = make_world(prices, [hard])
        self.assertEqual([o for o in Engine(w, dict(SETTINGS)).crafts()], [])     # SkillUp present, 501 unknown: hidden
        w.skillup.thresholds.clear()                                                 # SkillUp not installed
        e = Engine(w, dict(SETTINGS))
        crafts = e.crafts()
        self.assertEqual([o.title for o in crafts], ['Craft Tasty Dish'])
        self.assertIn('unverified_recipe', crafts[0].flags)
        self.assertNotIn(crafts[0].key, sum(e.top_picks(crafts).values(), []))     # never a top pick

    def test_soulbound_items_only_sell_to_vendors(self):
        w = make_world({PRODUCT: {'numAuctions': 3, 'minBuyout': 5000, 'marketValue': 5000, 'regionSale': 5000,
                                  'regionSoldPerDay': 9}})
        w.gamedata.items[PRODUCT].bonding = 1
        self.assertEqual(Engine(w, dict(SETTINGS)).sell_value(PRODUCT)[:2], (20, 'vendor'))

    def test_event_only_vendors_are_flagged(self):
        # Regression from live data: Heavy Leather Ball (Flik, Darkmoon Faire) and Green Firework (holiday
        # fireworks vendors) ranked as everyday vendor flips.
        w = make_world({})
        w.questie.items[ALLY_ONLY] = {'vendors': [102]}
        w.questie.npcs[102] = {'name': 'Flik', 'friendlyToFaction': 'AH', 'zoneID': 215,
                               'spawns': {12: [[41.0, 68.0]], 215: [[41.8, 68.1]]}}
        w.questie.items[LIMITED] = {'vendors': [103, 100]}
        w.questie.npcs[103] = {'name': 'Ziggle Sparks', 'subName': 'Holiday Fireworks Vendor', 'friendlyToFaction': 'AH'}
        e = Engine(w, dict(SETTINGS))
        self.assertIn('event_vendor', e.vendor_flags(ALLY_ONLY))
        self.assertNotIn('event_vendor', e.vendor_flags(LIMITED), 'a regular vendor also sells it')
        self.assertNotIn('event_vendor', e.vendor_flags(MAT_VENDOR))

    def test_top_picks_exclude_risky_and_unaffordable(self):
        prices = {CHEAP_SNIPE: {'numAuctions': 3, 'minBuyout': 200, 'marketValue': 1000, 'regionMarketValue': 900,
                                'regionSale': 800, 'regionSoldPerDay': 10, 'regionSalePercent': 0.5}}
        r = Engine(make_world(prices), dict(SETTINGS)).run()
        self.assertNotIn('dip:%d' % CHEAP_SNIPE, r['top']['now'])
        self.assertIn('dip:%d' % CHEAP_SNIPE, r['top']['snipes'])


class HistoryTests(unittest.TestCase):
    def test_record_once_per_scan(self):
        with tempfile.TemporaryDirectory() as d:
            h = History(Path(d) / 'h.db')
            import time
            now = int(time.time())
            self.assertTrue(h.record('PvP-Horde', now - 100, {1: {'minBuyout': 10, 'marketValue': 12}}))
            self.assertFalse(h.record('PvP-Horde', now - 100, {1: {'minBuyout': 99}}))
            self.assertTrue(h.record('PvP-Horde', now, {1: {'minBuyout': 20, 'marketValue': 22}}))
            self.assertEqual([p['min_buyout'] for p in h.series(1)], [10, 20])
            self.assertEqual(h.previous(now)[1]['minBuyout'], 10)


if __name__ == '__main__':
    unittest.main()
