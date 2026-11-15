"""Worth adding to your TSM Sniper: items our snapshots often caught far below their usual price."""
import unittest

from wfm import sniper

DAGGER, DUST, RARE, SLOW = 1, 2, 3, 4
PRICES = {DAGGER: {'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5},
          DUST: {'marketValue': 50, 'regionSale': 50, 'regionSoldPerDay': 100},
          RARE: {'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 5},
          SLOW: {'marketValue': 1000, 'regionSale': 900, 'regionSoldPerDay': 0.2}}


class SniperTests(unittest.TestCase):
    def test_a_lowest_listing_that_always_sits_below_the_average_is_not_a_snipe(self):
        rows = [(DAGGER, 500, 1000, 900)] * 6                    # always 500: its normal price, not a dip
        self.assertEqual(sniper.build(rows, PRICES, {}), [])

    def test_items_caught_cheap_often_enough(self):
        rows = [(DAGGER, 500, 1000, 900), (DAGGER, 950, 1000, 900), (DAGGER, 400, 1000, 900),   # 2 of 3 under 60% of 900
                (DAGGER, 950, 1000, 900), (DAGGER, 960, 1000, 900),                            # typical lowest: 950
                (DUST, 20, 50, 50), (DUST, 25, 50, 50),                                        # below the vendor's 30c
                (RARE, 500, 1000, 900), (RARE, 950, 1000, 900),                                # only once: not enough
                (SLOW, 100, 1000, 900), (SLOW, 100, 1000, 900)]                                # barely sells
        out = {(r['item_id'], r['how']): r for r in sniper.build(rows, PRICES, {DUST: 30})}
        d = out[(DAGGER, 'resell on the AH')]
        self.assertEqual((d['snipe_at'], d['times'], d['snapshots']), (540, 2, 5))         # 60% of min(950, 900)
        self.assertEqual(d['gain'], int(900 * 0.95) - 540)
        self.assertEqual(out[(DUST, 'sell to a vendor')]['snipe_at'], 30)
        self.assertNotIn((RARE, 'resell on the AH'), out)
        self.assertNotIn((SLOW, 'resell on the AH'), out)


if __name__ == '__main__':
    unittest.main()
