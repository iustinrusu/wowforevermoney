"""Niches: steady demand, low supply. Hand-made TSM rows, one rule broken per item."""
import unittest

from wfm import niches

GOOD, BULK, SLOW, WALLED, CHEAP, NOWAY, LOSS, THIN = range(1, 9)
BASE = {'regionSoldPerDay': 20, 'regionSalePercent': 0.8, 'numAuctions': 4, 'minBuyout': 1000, 'regionSale': 1000}
PRICES = {
    GOOD: dict(BASE),
    BULK: dict(BASE, regionSoldPerDay=10000, numAuctions=1132),          # Silk Cloth: a big commodity
    SLOW: dict(BASE, regionSoldPerDay=3),                                # 0.6 a day at a 20% share
    WALLED: dict(BASE, regionSalePercent=0.3),                           # most listings don't sell
    CHEAP: dict(BASE, minBuyout=800),                                    # undercut: 80% of the usual sale
    NOWAY: dict(BASE),                                                   # nothing you can supply it with
    LOSS: dict(BASE),                                                    # only a losing craft
    THIN: dict(BASE, numAuctions=0, minBuyout=0),                        # sold out now
}
WAY = {'kind': 'craft it', 'title': 'Craft it', 'key': 'k', 'profit_unit': 300, 'doable': True, 'needs': ''}
SUPPLY = {i: [dict(WAY)] for i in PRICES if i != NOWAY}
SUPPLY[LOSS] = [dict(WAY, profit_unit=-50)]


class NicheTests(unittest.TestCase):
    def test_only_items_that_pass_every_rule(self):
        rows = niches.build(PRICES, SUPPLY, 0.2, {THIN: {'scans': 100, 'sold_out': 0.5}})
        self.assertEqual([r['item_id'] for r in rows], [THIN, GOOD])     # thin supply ranks first at equal profit
        good = next(r for r in rows if r['item_id'] == GOOD)
        self.assertEqual(good['sold_per_day'], 4.0)                       # 20 x 20%
        self.assertEqual(good['profit_day'], 300 * 4)
        self.assertIn('80% of listings sell', good['why'])
        thin = rows[0]
        self.assertTrue(thin['thin_supply'])
        self.assertIn('sold out in 50% of our 100 snapshots', thin['why'])

    def test_few_snapshots_are_said_so(self):
        rows = niches.build({GOOD: PRICES[GOOD]}, {GOOD: [dict(WAY)]}, 0.2, {GOOD: {'scans': 23, 'sold_out': 0.0}})
        self.assertIn('too few snapshots', rows[0]['why'])

    def test_sold_out_stats(self):
        self.assertEqual(niches.sold_out_stats([(5, 20, 5)]), {5: {'scans': 20, 'sold_out': 0.25}})


if __name__ == '__main__':
    unittest.main()
