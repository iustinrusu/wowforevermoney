"""Sources graded by in-game checks (2026-11-14: new items' hotfix sell prices were wrong 91% of the time)."""
import unittest

from tests.test_engine import PRODUCT, SETTINGS, make_world
from wfm import gamedata
from wfm.engine import Engine, vendor_sell
from wfm.gamedata import GameData, Item


def item(iid, source, sell=100, checked=None):
    return Item(id=iid, name=f'I{iid}', quality=2, item_level=20, req_level=15, sell_price=sell, buy_price=0, stack=1,
                class_id=4, subclass_id=1, bonding=2, source=source, checked=checked)


class Grading(unittest.TestCase):
    def gd(self, wrong_new, total_new=40):
        gd = GameData(build='t')
        for i in range(total_new):    # checked new items: some had a wrong sell price
            gd.items[i] = item(i, 'in-game', checked={'against': 'server-new',
                                                      'differs': ['sell_price'] if i < wrong_new else []})
        for i in range(100, 140):     # checked client items: all right
            gd.items[i] = item(i, 'in-game', checked={'against': 'client', 'differs': []})
        gd.items[500] = item(500, 'server-new')     # unchecked, from the unreliable source
        gd.items[501] = item(501, 'client')
        return gd

    def test_unreliable_field_is_not_trusted_for_unchecked_items(self):
        gd = self.gd(wrong_new=36)
        grades = gamedata.grade_sources(gd)
        self.assertFalse(grades[('server-new', 'sell_price')]['trusted'])
        self.assertTrue(grades[('server-new', 'quality')]['trusted'])
        self.assertTrue(grades[('client', 'sell_price')]['trusted'])
        self.assertEqual(gamedata.mark_untrusted(gd, grades), 1)
        self.assertEqual(gd.items[500].untrusted, ('sell_price',))
        self.assertEqual(gd.items[501].untrusted, ())
        self.assertEqual(vendor_sell(gd.items[500]), 0)
        self.assertEqual(vendor_sell(gd.items[501]), 100)

    def test_needs_enough_checks_and_a_high_error_rate(self):
        self.assertTrue(gamedata.grade_sources(self.gd(wrong_new=6))[('server-new', 'sell_price')]['trusted'])   # 15%
        self.assertTrue(gamedata.grade_sources(self.gd(wrong_new=20, total_new=20))[('server-new', 'sell_price')]['trusted'])  # < 30 checks


class EngineIgnoresUntrustedVendorPrices(unittest.TestCase):
    def test_no_ah_to_vendor_flip_and_no_vendor_value(self):
        prices = {PRODUCT: {'numAuctions': 2, 'minBuyout': 5, 'marketValue': 6, 'regionSoldPerDay': 5}}
        w = make_world(prices)
        e = Engine(w, dict(SETTINGS))
        self.assertEqual([o.item_id for o in e.ah_to_vendor()], [PRODUCT])       # vendor pays 20c, listed at 5c
        w.gamedata.items[PRODUCT].untrusted = ('sell_price',)
        e = Engine(w, dict(SETTINGS))
        self.assertEqual(e.ah_to_vendor(), [])
        self.assertEqual(e.sell_value(PRODUCT)[1], 'AH')


if __name__ == '__main__':
    unittest.main()
