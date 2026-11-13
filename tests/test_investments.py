import json
import unittest
from types import SimpleNamespace as NS

from wfm import investments as inv

DAY = 86400
T0 = 1_800_000_000


def snap(ts, mb=None, spd=None, market=None):
    return {'ts': ts, 'min_buyout': mb, 'market': market, 'sold_per_day': spd}


class Names(unittest.TestCase):
    def test_mismatched_or_missing_ids_are_dropped_and_reported(self):
        items = {1: NS(name='Black Lotus'), 2: NS(name='Something Else')}
        kept, dropped = inv.check_names([{'id': 1, 'name': 'Black Lotus'}, {'id': 2, 'name': 'Dreamfoil'},
                                         {'id': 3, 'name': 'Icecap'}], items)
        self.assertEqual([e['id'] for e in kept], [1])
        self.assertEqual(dropped, [{'id': 2, 'expected': 'Dreamfoil', 'found': 'Something Else'},
                                   {'id': 3, 'expected': 'Icecap', 'found': None}])

    def test_curated_file_is_valid(self):
        d = inv.load_list()
        self.assertGreater(len(d['items']), 20)
        ids = [e['id'] for e in d['items']]
        self.assertEqual(len(ids), len(set(ids)))
        for e in d['items']:
            for k in ('id', 'name', 'category', 'thesis', 'horizon', 'risk', 'risk_note'):
                self.assertTrue(e.get(k), (e.get('id'), k))
            self.assertIn(e['risk'], ('low', 'medium', 'high'))
        self.assertEqual([c['name'] for c in d['progression_cloth']],
                         ['Linen Cloth', 'Wool Cloth', 'Silk Cloth', 'Mageweave Cloth', 'Runecloth'])


class Trend(unittest.TestCase):
    def test_needs_two_priced_snapshots(self):
        self.assertIsNone(inv.trend([]))
        self.assertIsNone(inv.trend([snap(T0, 100), snap(T0 + 60, None)]))

    def test_short_history_is_first_vs_latest(self):
        t = inv.trend([snap(T0, 100), snap(T0 + 3600, 500), snap(T0 + 7200, 120)])
        self.assertTrue(t['short'])
        self.assertAlmostEqual(t['change'], 0.2)
        self.assertIsNone(t['change_7d'])
        self.assertEqual(t['scans'], 3)

    def test_longer_history_uses_12h_medians_so_one_odd_listing_cant_swing_it(self):
        s = [snap(T0, 100), snap(T0 + 3600, 1), snap(T0 + 7200, 100),            # one odd 1c listing at the start
             snap(T0 + 3 * DAY, 150), snap(T0 + 3 * DAY + 3600, 9999), snap(T0 + 3 * DAY + 7200, 150)]
        t = inv.trend(s)
        self.assertFalse(t['short'])
        self.assertEqual((t['start'], t['end']), (100, 150))
        self.assertAlmostEqual(t['change'], 0.5)
        self.assertIsNone(t['change_7d'])

    def test_seven_day_change_after_a_week(self):
        s = [snap(T0, 100), snap(T0 + 2 * DAY, 200), snap(T0 + 9 * DAY, 300)]
        t = inv.trend(s)
        self.assertAlmostEqual(t['change'], 2.0)
        self.assertAlmostEqual(t['change_7d'], 0.5)    # 200 seven days before the latest 300


class Money(unittest.TestCase):
    def test_downside_to_vendor_floor(self):
        self.assertAlmostEqual(inv.downside(10000, 2000), -0.8)
        self.assertEqual(inv.downside(10000, 0), -1.0)
        self.assertEqual(inv.downside(100, 400), 0.0)    # vendor pays more than the AH: no downside
        self.assertIsNone(inv.downside(None, 100))

    def test_break_even_after_ah_cut(self):
        self.assertAlmostEqual(inv.break_even_rise(0.05), 1 / 0.95 - 1)
        # buying at 100 and reselling at 100 * (1 + rise) nets exactly 100 after the cut
        self.assertAlmostEqual(100 * (1 + inv.break_even_rise(0.05)) * 0.95, 100)


class Progression(unittest.TestCase):
    CLOTH = [{'id': 1, 'name': 'Linen Cloth'}, {'id': 2, 'name': 'Runecloth'}]

    def test_shares_of_daily_cloth_sales(self):
        g = inv.progression(self.CLOTH, {1: {'regionSoldPerDay': 300}, 2: {'regionSoldPerDay': 100}},
                            {1: 350, 2: 50})
        self.assertEqual([t['share'] for t in g['tiers']], [0.75, 0.25])
        self.assertEqual([t['share_then'] for t in g['tiers']], [0.875, 0.125])
        self.assertEqual(g['total'], 400)

    def test_no_data(self):
        g = inv.progression(self.CLOTH, {})
        self.assertEqual([t['share'] for t in g['tiers']], [0.0, 0.0])
        self.assertIsNone(g['tiers'][0]['share_then'])


class Score(unittest.TestCase):
    def test_cheap_vs_long_term_well_selling_low_risk_ranks_first(self):
        good = {'regionSoldPerDay': 50, 'regionSalePercent': 0.6, 'numAuctions': 10}
        self.assertAlmostEqual(inv.invest_score(700, 1000, good, 'low'), 1.3)          # 30% under long-term
        self.assertAlmostEqual(inv.invest_score(1300, 1000, good, 'low'), 0.7)         # 30% over
        self.assertAlmostEqual(inv.invest_score(700, 1000, good, 'high'), 0.65)
        slow = {'regionSoldPerDay': 4, 'regionSalePercent': 0.07, 'numAuctions': 30}  # Black Lotus-like
        self.assertAlmostEqual(inv.invest_score(1000, 1000, slow, 'low'), 0.3)
        self.assertAlmostEqual(inv.invest_score(100, 1000, good, 'low'), 1.75)         # capped at +75%


class Build(unittest.TestCase):
    def setUp(self):
        self.items = {10: NS(name='Black Lotus', quality=2, sell_price=1000),
                      11: NS(name='Icecap', quality=1, sell_price=250),
                      1: NS(name='Linen Cloth', quality=1, sell_price=13),
                      2: NS(name='Runecloth', quality=1, sell_price=400)}
        self.curated = {'checked': '2026-11-13', 'items': [
            {'id': 10, 'name': 'Black Lotus', 'category': 'Raid herbs', 'thesis': 't', 'horizon': 'h', 'risk': 'medium', 'risk_note': 'r'},
            {'id': 11, 'name': 'Icecap', 'category': 'Raid herbs', 'thesis': 't', 'horizon': 'h', 'risk': 'high', 'risk_note': 'r'},
            {'id': 99, 'name': 'Gone Item', 'category': 'x', 'thesis': 't', 'horizon': 'h', 'risk': 'low', 'risk_note': 'r'}],
            'progression_cloth': [{'id': 1, 'name': 'Linen Cloth'}, {'id': 2, 'name': 'Runecloth'}]}
        self.prices = {10: {'minBuyout': 100000, 'numAuctions': 5, 'marketValue': 125000, 'regionSale': 110000,
                            'regionSoldPerDay': 4.0, 'regionSalePercent': 0.07},
                       11: {'marketValue': 5000, 'regionSale': 2000, 'regionSoldPerDay': 40.0, 'regionSalePercent': 0.3},
                       1: {'regionSoldPerDay': 900}, 2: {'regionSoldPerDay': 100}}
        self.recipes = [NS(name='Flask of the Titans', reagents=[(10, 1)]), NS(name='Flask of Distilled Wisdom', reagents=[(10, 1), (11, 10)])]
        self.hist = {10: [snap(T0, 90000), snap(T0 + 2 * DAY, 100000)],
                     1: [snap(T0, spd=800)], 2: [snap(T0, spd=200)]}

    def run_build(self, now=T0 + 2 * DAY):
        return inv.build(self.curated, self.items, self.recipes, self.prices, lambda i: self.hist.get(i, []),
                         [11], 0.05, now=now)

    def test_rows(self):
        r = self.run_build()
        self.assertEqual(r['dropped'], [{'id': 99, 'expected': 'Gone Item', 'found': None}])
        by = {x['name']: x for x in r['items']}
        lotus, icecap = by['Black Lotus'], by['Icecap']
        self.assertEqual([x['name'] for x in r['items']], ['Icecap', 'Black Lotus'])   # Lotus barely sells (7%)
        self.assertEqual(lotus['buy'], 100000)
        self.assertAlmostEqual(lotus['vs_market'], -0.2)
        self.assertAlmostEqual(lotus['downside'], -0.99)
        self.assertAlmostEqual(lotus['trend']['change'], 100000 / 90000 - 1)
        self.assertEqual(lotus['used_in_count'], 2)
        self.assertIn('slow_sale_rate', lotus['flags'])
        self.assertNotIn('short_history', lotus['flags'])
        self.assertFalse(lotus['watching'])
        # nothing listed: buy at the market value, flagged; no "vs 14-day avg"; no history
        self.assertEqual(icecap['buy'], 5000)
        self.assertIn('none_listed', icecap['flags'])
        self.assertIsNone(icecap['vs_market'])
        self.assertIn('short_history', icecap['flags'])
        self.assertTrue(icecap['watching'])
        self.assertEqual(icecap['used_in'], ['Flask of Distilled Wisdom'])

    def test_gauge_comparison_only_after_a_day_of_history(self):
        r = self.run_build(now=T0 + 2 * DAY)
        self.assertEqual([t['share_then'] for t in r['progression']['tiers']], [0.8, 0.2])
        self.assertEqual(r['progression']['then_ts'], T0)
        self.assertEqual([t['share'] for t in r['progression']['tiers']], [0.9, 0.1])
        r = self.run_build(now=T0 + 3600)
        self.assertIsNone(r['progression']['tiers'][0]['share_then'])
        self.assertIsNone(r['progression']['then_ts'])

    def test_result_is_json_serialisable(self):
        json.dumps(self.run_build())


if __name__ == '__main__':
    unittest.main()
