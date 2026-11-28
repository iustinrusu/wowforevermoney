"""Item values through every channel (AH, vendor, crafting, opening), and the undervaluation watch."""
import unittest
from types import SimpleNamespace

from wfm.alerts import diff_runs
from wfm.engine import Engine
from wfm.gamedata import GameData, Item
from wfm.questie import QuestieDB
from wfm.skillup import SkillUpData
from wfm.valuation import merge_contents

TRUNK, MAGEWEAVE, LEATHER, CLAM, MEAT, PEARL, CRATE, GREEN, JUNK, NESTED = 21228, 4339, 4304, 7973, 7974, 7971, 6357, 9928, 99, 500


def item(iid, name, sell=0, cls=7, openable=False, bonding=0, locked=False):
    return Item(id=iid, name=name, quality=1, item_level=1, req_level=0, sell_price=sell, buy_price=0, stack=20,
                class_id=cls, subclass_id=0, bonding=bonding, openable=openable, locked=locked)


def world(prices=None, containers=None, own=None, inventory=None, activity=None):
    gd = GameData(build='test')
    for it in [item(TRUNK, 'Mithril Bound Trunk', sell=2, cls=15, openable=True, bonding=1),
               item(MAGEWEAVE, 'Bolt of Mageweave', sell=100), item(LEATHER, 'Thick Leather', sell=50),
               item(CLAM, 'Big-mouth Clam', sell=1, cls=15, openable=True), item(MEAT, 'Zesty Clam Meat', sell=10),
               item(PEARL, 'Black Pearl', sell=300), item(CRATE, 'Sealed Crate', sell=5, cls=15, openable=True),
               item(GREEN, 'Brigade Breastplate', sell=2000, cls=4), item(JUNK, 'Mystery Thing'),
               item(NESTED, 'Box of Clams', cls=15, openable=True)]:
        gd.items[it.id] = it
    return SimpleNamespace(gamedata=gd, prices=prices or {}, questie=QuestieDB(), skillup=SkillUpData(), angler=None,
                           forever_containers=containers or {}, forever_fishing={},
                           profile={'activity': activity or {}, 'containers': own or {}}, inventory=inventory or {})


SETTINGS = {'gold': 1, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'professions': {}, 'preferred': []}
WOWHEAD = {
    str(TRUNK): {'opened': 100, 'checked': '2026-11-13', 'items': [[MAGEWEAVE, 40, 1, 3], [LEATHER, 30, 2, 4], [GREEN, 1, 1, 1]]},
    str(CLAM): {'opened': 10, 'checked': '2026-11-13', 'items': [[MEAT, 10, 1, 3], [PEARL, 1, 1, 1]]},
    str(NESTED): {'opened': 1, 'checked': '2026-11-13', 'items': [[CLAM, 1, 2, 2]]},
}


class ContentsTests(unittest.TestCase):
    def test_merge_wowhead_and_your_own_opens(self):
        c = merge_contents(WOWHEAD, {TRUNK: {'opened': 2, 'items': {MAGEWEAVE: 5, 14048: 1}}})[TRUNK]
        self.assertEqual(c['opened'], 102)
        self.assertEqual(c['qty'][MAGEWEAVE], 40 * 2 + 5)      # 40 times x average stack 2, plus your 5
        self.assertEqual(c['qty'][LEATHER], 30 * 3)
        self.assertEqual(c['qty'][14048], 1)
        self.assertEqual(len(c['sources']), 2)


class ValuerTests(unittest.TestCase):
    def test_trunk_is_worth_its_contents(self):
        # Regression: a soulbound trunk was "worth 2c" (its vendor price) though it holds cloth and leather.
        prices = {MAGEWEAVE: {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1100, 'regionSoldPerDay': 50,
                              'regionSale': 1000},
                  TRUNK: {'numAuctions': 1, 'minBuyout': 99999, 'marketValue': 99999, 'regionSoldPerDay': 1}}
        v = Engine(world(prices, WOWHEAD), dict(SETTINGS)).valuer({}).value(TRUNK)
        # per open: 0.8 Mageweave at 950 (AH after 5% cut) + 0.9 leather at 50 (vendor) + 0.01 green at 2000
        self.assertEqual(v.channel, 'open')
        self.assertEqual(v.value, int(0.8 * 950 + 0.9 * 50 + 0.01 * 2000))
        self.assertNotIn('AH', v.channels, 'a soulbound item has no AH channel, whatever TSM lists')
        self.assertIn('open_it', v.flags)
        self.assertEqual(v.contents[0]['item_id'], MAGEWEAVE)

    def test_value_follows_current_prices(self):
        cheap = {MAGEWEAVE: {'numAuctions': 5, 'minBuyout': 200, 'marketValue': 200, 'regionSoldPerDay': 50, 'regionSale': 200}}
        dear = {MAGEWEAVE: {'numAuctions': 5, 'minBuyout': 2000, 'marketValue': 2000, 'regionSoldPerDay': 50, 'regionSale': 2000}}
        lo = Engine(world(cheap, WOWHEAD), dict(SETTINGS)).valuer({}).worth(TRUNK)
        hi = Engine(world(dear, WOWHEAD), dict(SETTINGS)).valuer({}).worth(TRUNK)
        self.assertAlmostEqual(hi - lo, 0.8 * (1900 - 190), delta=1)

    def test_openable_without_contents_is_flagged_not_silently_cheap(self):
        v = Engine(world(), dict(SETTINGS)).valuer({}).value(CRATE)
        self.assertEqual((v.value, v.channel), (5, 'vendor'))
        self.assertIn('contents_unknown', v.flags)

    def test_containers_inside_containers(self):
        e = Engine(world(containers=WOWHEAD), dict(SETTINGS)).valuer({})
        clam = e.worth(CLAM)                       # 2 meat x 10 + 0.1 pearl x 300 = 50
        self.assertEqual(clam, 50)
        self.assertEqual(e.worth(NESTED), 2 * clam)

    def test_no_value(self):
        v = Engine(world(), dict(SETTINGS)).valuer({}).value(JUNK)
        self.assertEqual(v.value, 0)
        self.assertIn('no_value', v.flags)

    def test_stray_listing_without_sales_counts_at_sale_price(self):
        prices = {LEATHER: {'numAuctions': 1, 'minBuyout': 5000, 'marketValue': 5000, 'regionMarketValue': 600,
                            'regionSale': 400, 'regionSoldPerDay': 3}}
        v = Engine(world(prices), dict(SETTINGS)).valuer({}).value(LEATHER)
        self.assertEqual(v.value, int(400 * 0.95))
        self.assertIn('ah_price_doubtful', v.flags)

    def test_quest_item_that_does_not_bind_sells_on_the_ah(self):
        # Regression (2026-11-28): every quest-type item counted as unsellable, so Vulture Gizzard (Bonding 0, 73 sold a
        # day in the region at 2g 28s) was worth 0 in Black Slayer's row. A bound quest item (4) or one that binds when
        # picked up (1) still has no AH sale, whatever TSM lists.
        gizzard, bound, bop = 8396, 8397, 8398
        w = world({i: {'numAuctions': 55, 'minBuyout': 23698, 'marketValue': 23000, 'regionSoldPerDay': 73,
                       'regionSale': 22809} for i in (gizzard, bound, bop)})
        for iid, b in ((gizzard, 0), (bound, 4), (bop, 1)):
            w.gamedata.items[iid] = item(iid, f'quest item {b}', cls=12, bonding=b)
        e = Engine(w, dict(SETTINGS))
        v = e.valuer({}).value(gizzard)
        self.assertEqual((v.channel, v.value), ('AH', int(23698 * 0.95)))
        self.assertEqual(e.sell_value(gizzard)[1], 'AH')
        for iid in (bound, bop):
            self.assertEqual(e.valuer({}).value(iid).value, 0)
            self.assertNotIn('AH', e.valuer({}).value(iid).channels)
            self.assertIsNone(e.sell_value(iid)[2])


class WatchTests(unittest.TestCase):
    def test_watch_and_alert(self):
        inv = {'Testchar Alpha': {CRATE: 2, TRUNK: 1, MAGEWEAVE: 5}}
        activity = {'Stranglethorn Vale': {'mobs': {'loots': 3, 'seconds': 0, 'items': {JUNK: 1}}}}
        e = Engine(world(containers=WOWHEAD, inventory=inv, activity=activity), dict(SETTINGS))
        e.valuer({})
        watch = {u['item_id']: u for u in e.undervaluation_watch()}
        self.assertEqual(watch[CRATE]['issue'], 'contents_unknown')
        self.assertEqual(watch[CRATE]['where'], ['your bags'])
        self.assertEqual(watch[JUNK]['issue'], 'no_value')
        self.assertEqual(watch[TRUNK]['issue'], 'open_it')
        self.assertNotIn(MAGEWEAVE, watch)
        prev = {'opportunities': [], 'top': {}, 'undervalued': [watch[JUNK]]}
        cur = {'opportunities': [], 'top': {}, 'undervalued': list(watch.values())}
        events = diff_runs(prev, cur, {}, str)
        self.assertEqual([ev['item_id'] for ev in events if ev['type'] == 'undervalued'], [CRATE],
                         'only newly seen problems alert; "open it" is advice, not an alert')


if __name__ == '__main__':
    unittest.main()
