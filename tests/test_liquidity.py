"""Only suggest items that actually sell (user, 2026-11-14): volume, sale rate and realm backlog."""
import unittest

from tests.test_engine import LIMITED, PRODUCT, SETTINGS, make_world
from wfm.engine import Engine, confidence
from wfm.pricing import liquidity


def p(spd, rate, listed):
    return {'regionSoldPerDay': spd, 'regionSalePercent': rate, 'numAuctions': listed, 'minBuyout': 5000,
            'marketValue': 5000, 'regionSale': 5000}


class Liquidity(unittest.TestCase):
    def test_sells_well(self):
        l = liquidity(p(94, 0.53, 9))
        self.assertEqual(l['flags'], [])
        self.assertAlmostEqual(l['days_of_supply'], 9 / 94)

    def test_hard_to_sell_for_each_reason(self):
        # real cases from 2026-11-13/14
        self.assertEqual(liquidity(p(0.77, 0.31, 0))['flags'], ['hard_to_sell'])     # Azure Windraveled Pants
        self.assertEqual(liquidity(p(125.6, 0.06, 10))['flags'], ['hard_to_sell'])   # Poached Sunscale Salmon
        l = liquidity(p(10.58, 0.41, 131))                                           # Turtle Scale Breastplate
        self.assertEqual(l['flags'], ['hard_to_sell'])
        self.assertIn('131 listed', l['why'])

    def test_slow_and_crowded_are_ranked_lower_not_hidden(self):
        self.assertEqual(liquidity(p(22.75, 0.20, 14))['flags'], ['slow_to_sell'])
        self.assertEqual(liquidity(p(3.69, 0.61, 25))['flags'], ['crowded'])        # 6.8 days of supply
        self.assertEqual(liquidity(p(1.61, 0.12, 14))['flags'], ['slow_to_sell', 'crowded'])
        self.assertLess(confidence(['slow_to_sell', 'crowded']), confidence([]))

    def test_user_minimum_only_raises_the_floor(self):
        self.assertEqual(liquidity(p(3, 0.5, 1), min_sold_per_day=5)['flags'], ['hard_to_sell'])
        self.assertEqual(liquidity(p(0.8, 0.5, 0), min_sold_per_day=0.5)['flags'], ['hard_to_sell'])   # floor of 1

    def test_no_data(self):
        self.assertEqual(liquidity(None)['flags'], ['no_sales_data'])
        self.assertEqual(liquidity({'regionSoldPerDay': 5, 'numAuctions': 2})['flags'], [])   # no sale rate known


class EngineUsesIt(unittest.TestCase):
    def flip_world(self, spd, rate, listed):
        return make_world({LIMITED: p(spd, rate, listed)})

    def test_hard_to_sell_flip_is_never_a_top_pick(self):
        r = Engine(self.flip_world(0.6, 0.5, 2), dict(SETTINGS)).run()
        o = next(o for o in r['opportunities'] if o.key == f'vflip:{LIMITED}')
        self.assertIn('hard_to_sell', o.flags)
        self.assertEqual(o.detail['liquidity']['sold_per_day'], 0.6)
        self.assertNotIn(o.key, sum(r['top'].values(), []))

    def test_well_selling_flip_is_a_top_pick(self):
        r = Engine(self.flip_world(50, 0.6, 3), dict(SETTINGS)).run()
        self.assertIn(f'vflip:{LIMITED}', r['top']['now'])

    def test_vendor_sales_need_no_ah_buyers(self):
        e = Engine(make_world({}), dict(SETTINGS))
        for o in e.run()['opportunities']:
            if o.detail.get('sell_channel') == 'vendor':
                self.assertNotIn('liquidity', o.detail)


if __name__ == '__main__':
    unittest.main()
