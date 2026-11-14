"""Price checks (wfm/anomalies.py): a second opinion at typical prices, crafted worth, the data monitor, alerts.
Built on the real errors of 2026-11-14; numbers worked out by hand. All money in copper."""
import unittest
from types import SimpleNamespace

from wfm import anomalies

CUT = 0.05


def row(kind, profit, cost=0, item_id=1, daily=1000, **detail):
    return SimpleNamespace(kind=kind, key=f'{kind}:{item_id}', item_id=item_id, title=f'{kind} {item_id}',
                           profit_unit=profit, cost_unit=cost, daily=daily, flags=[], detail=detail)


class SecondOpinionTests(unittest.TestCase):
    def test_typical_price_is_the_median_of_independent_references(self):
        p = {'marketValue': 300, 'regionMarketValue': 400, 'regionSale': 200}
        self.assertEqual(anomalies.typical_price(p)[0], 300)
        # a freak sale average is left out: Masterwork Target Dummy, 642g sales vs 11g 25s listings
        dummy = {'regionMarketValue': 112550, 'regionHistorical': 112550, 'regionSale': 6426275}
        self.assertEqual(anomalies.typical_price(dummy)[0], 112550)
        self.assertEqual(anomalies.typical_price({})[0], None)

    def test_a_flip_that_only_pays_at_an_odd_price_fails(self):
        # Bronze Tube: vendor 8s 50c, listed at 14s, typical ~5s 50c -> loses money at typical prices
        prices = {1: {'marketValue': 550, 'regionMarketValue': 600, 'regionSale': 500}}
        o = row('vendor_flip', profit=480, cost=850, ah_sell=1400)
        found = anomalies.check_rows([o], prices, CUT)
        self.assertEqual(found[0]['severity'], 'high')
        self.assertIn('price_check_fails', o.flags)
        self.assertEqual(o.detail['price_check']['profit'], int(550 * 0.95) - 850)   # 522 - 850 = -328

    def test_a_craft_resting_on_a_high_sale_price_and_a_one_off_ingredient(self):
        # sold at 3000 (typical 1000); 2 of an ingredient from a single listing at 50 (typical 200); 1 from a vendor
        prices = {1: {'marketValue': 1000, 'regionMarketValue': 1000, 'regionSale': 1000},
                  2: {'numAuctions': 1, 'minBuyout': 50, 'marketValue': 200, 'regionMarketValue': 200, 'regionSale': 200}}
        mats = [{'item_id': 2, 'name': 'Thin Mat', 'count': 2, 'unit': 50, 'source': 'lowest listing'},
                {'item_id': 3, 'count': 1, 'unit': 100, 'source': 'vendor'}]
        o = row('craft', profit=2000, mats=mats, product_count=1, sell_channel='AH', sell_price=3000)
        found = anomalies.check_rows([o], prices, CUT)
        # second opinion: 1000 x 0.95 = 950 - (2 x 200 + 100) = 450, under a third of 2000
        self.assertEqual(o.detail['price_check']['profit'], 450)
        self.assertEqual((found[0]['severity'], o.flags), ('warn', ['price_check']))
        self.assertIn('one-off cheap listings of Thin Mat', found[0]['text'])

    def test_cheap_ingredients_with_plenty_listed_are_real(self):
        # the same craft, but 40 listed at 50: buyable today, so the second opinion keeps 50 and agrees
        prices = {1: {'marketValue': 1000, 'regionMarketValue': 1000, 'regionSale': 1000},
                  2: {'numAuctions': 40, 'minBuyout': 50, 'marketValue': 200, 'regionMarketValue': 200, 'regionSale': 200}}
        mats = [{'item_id': 2, 'count': 2, 'unit': 50, 'source': 'lowest listing'}]
        o = row('craft', profit=850, mats=mats, product_count=1, sell_channel='AH', sell_price=1000)
        self.assertEqual(anomalies.check_rows([o], prices, CUT), [])

    def test_a_sound_row_and_one_off_snipes_are_left_alone(self):
        prices = {1: {'marketValue': 1000, 'regionMarketValue': 1100, 'regionSale': 900}}
        ok = row('vendor_flip', profit=600, cost=350, ah_sell=1000)   # typical 1000 x 0.95 - 350 = 600
        snipe = row('realm_dip', profit=5000, cost=10)
        self.assertEqual(anomalies.check_rows([ok, snipe], prices, CUT), [])
        self.assertEqual((ok.flags, snipe.flags), ([], []))

    def test_crafted_worth_far_above_sale_for_under_one_a_day(self):
        best = {7: {'value': 216500, 'recipe': 'Transmute: Arcanite', 'units_per_day': 0.51,
                    'doable_value': None, 'doable_units_per_day': None},
                8: {'value': 30000, 'recipe': 'Busy Craft', 'units_per_day': 40, 'doable_value': None}}
        found = anomalies.check_crafted_worth(best, lambda i: 1700, lambda i: f'item {i}')
        self.assertEqual([f['item_id'] for f in found], [7])    # 8 sells 40 a day: its crafted worth holds
        self.assertEqual(found[0]['severity'], 'info')          # needs a skill you don't have: shown, not used

    def test_data_monitor_counts(self):
        prices = {1: {'regionSale': 6426275, 'regionMarketValue': 112550},                     # freak sale average
                  2: {'numAuctions': 10, 'minBuyout': 100000, 'regionSale': 190, 'regionMarketValue': 900,
                      'regionSoldPerDay': 2},                                                  # Short Staff wall
                  3: {'numAuctions': 1, 'minBuyout': 25000000, 'regionMarketValue': 4712400}}   # lone, no sales
        m = anomalies.scan_prices(prices)
        self.assertEqual((m['freak_sales'], m['walls'], m['lone_listings']), (1, 1, 1))

    def test_alerts_only_for_new_findings_on_what_you_see(self):
        f = {'check': 'second_opinion', 'severity': 'high', 'key': 'craft:9', 'item_id': 9, 'title': 'Craft X',
             'text': 'loses money'}
        g = {**f, 'key': 'craft:10', 'title': 'Craft Y'}
        ev = anomalies.new_events({'findings': []}, {'findings': [f, g]}, {'craft:9'})
        self.assertEqual([e['key'] for e in ev], ['check:craft:9'])
        self.assertTrue(ev[0]['important'])
        self.assertEqual(anomalies.new_events({'findings': [f]}, {'findings': [f]}, {'craft:9'}), [])

    def test_audit_check_status(self):
        self.assertEqual(anomalies.audit_check({'anomalies': {'findings': [], 'monitor': {}}})['status'], 'pass')
        bad = {'check': 'second_opinion', 'severity': 'high', 'key': 'k', 'title': 't', 'text': 'x', 'impact': 1}
        self.assertEqual(anomalies.audit_check({'anomalies': {'findings': [bad], 'monitor': {}}})['status'], 'warn')


if __name__ == '__main__':
    unittest.main()
