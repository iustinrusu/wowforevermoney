"""ROI, return on investment (the user, 2026-11-27: "add ROI (return of investment %) on suitable entries"): the
profit on one after the AH cut as a share of what one costs up front. Hand-worked numbers, money in copper."""
import unittest
from types import SimpleNamespace

from wfm import markets, plan, sniper
from wfm.engine import Engine, Opportunity
from wfm.gamedata import Recipe
from wfm.pricing import roi
from tests.test_engine import CHEAP_SNIPE, LIMITED, MAT_AH, MAT_VENDOR, PRODUCT, SETTINGS, make_world


def row(kind, profit, cost):
    return Opportunity(kind=kind, key=f'{kind}:1', item_id=1, title='x', profit_unit=profit, cost_unit=cost,
                       units_day=1, daily=profit)


class RoiHelperTests(unittest.TestCase):
    def test_profit_over_cost(self):
        self.assertEqual(roi(50, 100), 0.5)                  # 1g in, 1g 50s back
        self.assertEqual(roi(200, 100), 2.0)                 # back three times over
        self.assertEqual(roi(355, 120), 2.9583)              # rounded to 4 places (0.01 of a percent)
        self.assertEqual(roi(-30, 120), -0.25)               # a loss is a negative return

    def test_no_return_without_gold_up_front(self):
        self.assertIsNone(roi(500, 0))
        self.assertIsNone(roi(500, -10))
        self.assertIsNone(roi(None, 100))
        self.assertIsNone(roi(500, None))


class RowRoiTests(unittest.TestCase):
    def test_only_rows_you_put_gold_into(self):
        self.assertEqual(row('craft', 50, 100).roi, 0.5)
        self.assertEqual(row('vendor_flip', 300, 1000).roi, 0.3)
        self.assertEqual(row('ah_to_vendor', 300, 200).roi, 1.5)
        self.assertEqual(row('realm_dip', 400, 200).roi, 2.0)
        # farming costs time, not gold: no ROI even where a cost is set (a fishing lure an hour)
        for kind in ('mob_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'fishing_spot', 'gather', 'farm_zone'):
            self.assertIsNone(row(kind, 500, 50).roi, kind)
        self.assertIsNone(row('craft', 500, 0).roi)        # no priced ingredient: nothing to measure
        self.assertIn('roi', row('craft', 50, 100).to_dict())   # the page gets it with the row

    def test_craft_row_hand_worked(self):
        # tests/test_engine.py's craft: cost 2 x 10 (vendor) + 100 (AH) = 120, sells for 500 - 5% = 475 -> 355 profit
        recipe = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                        product_count=1, reagents=[(MAT_VENDOR, 2), (MAT_AH, 1)], trivial_low=140, trivial_high=180,
                        min_rank=1)
        prices = {MAT_AH: {'numAuctions': 4, 'minBuyout': 100, 'marketValue': 120, 'regionSoldPerDay': 50},
                  PRODUCT: {'numAuctions': 6, 'minBuyout': 500, 'marketValue': 600, 'regionSoldPerDay': 10,
                            'regionSalePercent': 0.4, 'regionSale': 400}}
        e = Engine(make_world(prices, [recipe]), dict(SETTINGS))
        o = e.crafts()[0]
        self.assertEqual((o.profit_unit, o.cost_unit, o.roi), (355, 120, round(355 / 120, 4)))   # 295.8%
        # through the whole run: the same, plus the ROI at the region's average sale price (400 - 5% = 380 -> 260)
        o = next(x for x in e.run()['opportunities'] if x.kind == 'craft')
        self.assertEqual(o.roi, round(355 / 120, 4))
        self.assertEqual(o.detail['profit_at_avg_sale'], 260)
        self.assertEqual(o.detail['roi_at_avg_sale'], round(260 / 120, 4))

    def test_vendor_flip_hand_worked(self):
        # Rare Pattern: vendor 10s, lowest listing 50s - 5% = 47s 50c -> 37s 50c profit on 10s: 375%
        prices = {LIMITED: {'numAuctions': 2, 'minBuyout': 5000, 'marketValue': 5000, 'regionSoldPerDay': 100,
                            'regionSalePercent': 0.5}}
        o = next(f for f in Engine(make_world(prices), dict(SETTINGS)).vendor_flips() if f.item_id == LIMITED)
        self.assertEqual((o.profit_unit, o.cost_unit, o.roi), (3750, 1000, 3.75))

    def test_ah_to_vendor_hand_worked(self):
        prices = {CHEAP_SNIPE: {'numAuctions': 1, 'minBuyout': 200, 'marketValue': 900}}
        o = Engine(make_world(prices), dict(SETTINGS)).ah_to_vendor()[0]
        self.assertEqual(o.roi, 1.5)                         # vendor pays 5s for a 2s listing: 3s on 2s

    def test_at_usual_and_up_to(self):
        # realm prices (the default): 10 listed at 10g, sells for 19s -> "at usual" 18s 5c - 10s = 8s 5c on 10s
        wall = {LIMITED: {'numAuctions': 10, 'minBuyout': 100000, 'marketValue': 286, 'regionSale': 1900,
                          'regionSoldPerDay': 20, 'regionSalePercent': 1.0}}
        e = Engine(make_world(wall), dict(SETTINGS))
        o = next(f for f in e.vendor_flips() if f.item_id == LIMITED)
        e.add_upside(o)
        self.assertEqual(o.roi, round((95000 - 1000) / 1000, 4))
        self.assertEqual(o.detail['at_usual']['roi'], round((int(1900 * 0.95) - 1000) / 1000, 4))     # 80.5%
        # the lower basis: priced at the usual 20s (19s profit... 19s - 10s = 9s), "up to" at the 30s listing
        p = {LIMITED: {'numAuctions': 10, 'minBuyout': 3000, 'marketValue': 3000, 'regionSale': 2000,
                       'regionSoldPerDay': 20, 'regionSalePercent': 1.0}}
        e = Engine(make_world(p), dict(SETTINGS, sale_price_basis='lower'))
        o = next(f for f in e.vendor_flips() if f.item_id == LIMITED)
        e.add_upside(o)
        self.assertEqual((o.profit_unit, o.roi), (1900 - 1000, 0.9))
        self.assertEqual(o.detail['upside']['profit_unit'], 2850 - 1000)
        self.assertEqual(o.detail['upside']['roi'], 1.85)


class PlanRoiTests(unittest.TestCase):
    def test_a_step_returns_its_gain_on_the_gold_it_needs(self):
        o = Opportunity(kind='vendor_flip', key='vflip:9', item_id=1, title='Buy Jungle Wine from vendor, sell on AH',
                        profit_unit=1410, cost_unit=300, units_day=11.37, daily=int(1410 * 11.37),
                        detail={'confidence': 1.0, 'vendors': [], 'ah_sell': 1800, 'sold_per_day': 57,
                                'effort': {'minutes': 3.6, 'cost': 3000}})
        a = plan.routine(o, 6000)
        self.assertEqual(a['roi'], round(int(1410 * 11.37) / int(300 * 11.37), 4))
        self.assertAlmostEqual(a['roi'], o.roi, places=2)    # a day's profit on a day's buying: the row's own ROI

    def test_steps_without_gold_up_front_have_none(self):
        self.assertIsNone(plan._action('farm', 'Spend an hour', 'why', 50000, 60)['roi'])
        self.assertIsNone(plan._action('cash_vendor', 'Sell your junk', 'why', 3000, 2)['roi'])
        self.assertEqual(plan._action('snipe', 'Buy', 'why', 400, 2, 1.0, 200)['roi'], 2.0)

    def test_big_flip_counts_the_lower_profit(self):
        o = Opportunity(kind='vendor_flip', key='vflip:7', item_id=1, title='Buy Pattern: Big Gloves from vendor, sell '
                        'on AH', profit_unit=690000, cost_unit=60000, units_day=0.26, daily=int(690000 * 0.26),
                        detail={'confidence': 1.0, 'profit_at_avg_sale': 320000, 'vendors': []})
        a = plan.big_flip(o)
        self.assertEqual(a['roi'], round(320000 / 60000, 4))         # 533%, not the 1150% at the lowest listing


class ElsewhereRoiTests(unittest.TestCase):
    def test_sniper_resale_at_the_snipe_price(self):
        prices = {1: {'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5}}
        rows = [(1, 500, 1000, 900), (1, 950, 1000, 900), (1, 400, 1000, 900), (1, 950, 1000, 900),
                (1, 960, 1000, 900), (2, 20, 50, 50), (2, 25, 50, 50)]
        out = {(r['item_id'], r['how']): r for r in sniper.build(rows, {**prices, 2: {'regionSoldPerDay': 100}},
                                                                 {2: 30})}
        d = out[(1, 'resell on the AH')]
        self.assertEqual(d['roi'], round((int(900 * 0.95) - 540) / 540, 4))     # 315 on 540: 58.3%
        self.assertIsNone(out[(2, 'sell to a vendor')]['roi'])                 # depends on the listing you catch

    def test_biggest_markets_way_in(self):
        o = row('craft', 200000, 100000)
        self.assertEqual(markets.ways_in(o)['roi'], 2.0)
        farm = SimpleNamespace(kind='mob_spot', title='Kill', key='mob:1', daily=0, gph=50000, profit_unit=900,
                               doable=True, needs='')
        self.assertIsNone(markets.ways_in(farm)['roi'])


if __name__ == '__main__':
    unittest.main()
