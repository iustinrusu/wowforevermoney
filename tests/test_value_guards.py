"""The value guards of 2026-11-20 (the user's yes, after the farm meter valued one Rugged Hide at 2g 66s; it costs
7s 77c to buy): the buy-price rule held by the valuer as a safety net, and the watch on values that swing.
(The second opinion on crafted values and the crafted-worth cap: tests/test_crafted_cap.py.) Hand-worked numbers."""
import unittest
from types import SimpleNamespace
from unittest import mock

from tests.test_engine import CHEAP_SNIPE, FISH, MAT_AH, SETTINGS, item, make_world
from wfm import anomalies, valuation
from wfm.app import App
from wfm.engine import Engine

CRATE = 50


def crate_engine(crate_price=100, meat_price=100):
    w = make_world({CRATE: {'numAuctions': 10, 'minBuyout': crate_price, 'marketValue': crate_price,
                            'regionSoldPerDay': 20},
                    MAT_AH: {'numAuctions': 10, 'minBuyout': meat_price, 'marketValue': meat_price,
                             'regionSoldPerDay': 20},
                    CHEAP_SNIPE: {'numAuctions': 10, 'minBuyout': 300, 'marketValue': 300, 'regionSoldPerDay': 5}})
    crate = item(CRATE, 'Supply Crate')
    crate.openable = True
    w.gamedata.items[CRATE] = crate
    e = Engine(w, dict(SETTINGS))
    # one crate holds 5 Raw Meat: 5 x 95 after the AH cut = 475 a crate
    v = valuation.Valuer(e, {}, {CRATE: {'qty': {MAT_AH: 5}, 'opened': 1, 'sources': ['test']}})
    return e, v


class SafetyNetTests(unittest.TestCase):
    def test_a_value_above_the_buy_price_is_held_and_reported(self):
        e, v = crate_engine()
        val = v.value(CRATE)
        self.assertEqual(val.channel, 'open')
        self.assertEqual(val.channels['open'], 475)
        self.assertEqual(val.value, 100)                      # a crate costs 100 on the AH: held there
        self.assertIn('held_at_buy_price', val.flags)
        self.assertIn('held at what buying one costs, 1s 0c', val.how)
        self.assertEqual(v.breaches[CRATE]['value'], 475)
        held, summary = anomalies.check_values(SimpleNamespace(valuer=lambda bu: v, name=e.name), {})
        self.assertEqual((len(held), held[0]['severity'], held[0]['impact']), (1, 'high', 375))
        self.assertIn('Supply Crate came out at 4s 75c', held[0]['text'])
        entry = anomalies.value_rule_check({'anomalies': {'findings': held, 'values': summary}})
        self.assertEqual(entry['status'], 'fail')
        self.assertIn('1 came out above it', entry['detail'])
        self.assertIn('Supply Crate', entry['examples'][0])

    def test_under_the_buy_price_nothing_happens(self):
        e, v = crate_engine(crate_price=1000)                 # crates at 1,000: opening one (475) is not more
        val = v.value(CRATE)
        self.assertEqual((val.value, val.channel), (950, 'AH'))
        self.assertEqual(v.breaches, {})

    def test_a_vendor_price_is_paid_whatever_the_ah_lists(self):
        # Trinket: a vendor pays 500, the AH lists it at 300 (an AH-to-vendor buy): worth 500, no breach
        e, v = crate_engine()
        val = v.value(CHEAP_SNIPE)
        self.assertEqual((val.value, val.channel), (500, 'vendor'))
        self.assertEqual(v.breaches, {})

    def test_worth_for_a_stack_is_held_too(self):
        e, v = crate_engine()
        self.assertEqual(v.worth_for(CRATE, 3), 300)


class SwingTests(unittest.TestCase):
    def test_which_values_swing(self):
        prev = {1: (26643, 888), 2: (843, 888), 3: (500, 0), 4: (2000, 0), 5: (5000, 1000)}
        cur = {1: (9077, 777), 2: (1686, 1776), 3: (1200, 0), 4: (4000, 0), 5: (12000, 2000)}
        # 1: the Rugged Hide, 2.94x while its own price moved 1.14x; 2: follows its own price (2x and 2x);
        # 3: only 7s; 4: no own price, doubled; 5: 2.4x against 2x, under 1.5 x 2
        self.assertEqual(anomalies.swings(prev, cur), [1, 4])
        self.assertEqual(anomalies.swings({}, cur), [])

    def app(self, scan, prices, realm='Realm'):
        a = App.__new__(App)
        a.world = SimpleNamespace(
            prices=prices, gamedata=SimpleNamespace(items={FISH: SimpleNamespace(name='Rugged Hide')}),
            price_data=SimpleNamespace(datasets=[SimpleNamespace(scope=realm, download_time=scan)]))
        a.settings = SimpleNamespace(snapshot=lambda: {'realm': realm})
        return a

    def test_the_app_compares_scans_with_the_same_settings(self):
        how = SimpleNamespace(value=lambda iid: SimpleNamespace(how='Leatherworking: Cured Rugged Hide'))
        with mock.patch('wfm.app.Engine', lambda w, s: SimpleNamespace(valuer=lambda bu: how)):
            a = self.app(1795170000, {FISH: {'numAuctions': 399, 'minBuyout': 888}})
            a._track_swings({'item_values': {FISH: 26643}}, {'level': 51})
            self.assertEqual(a.swings, {})                     # nothing to compare with yet
            a._track_swings({'item_values': {FISH: 26643}}, {'level': 51, 'done_today': {'x': 1}})
            self.assertEqual(a.swings, {})                     # a step ticked done, same scan: nothing compared
            a.world.prices = {FISH: {'numAuctions': 486, 'minBuyout': 777}}
            a.world.price_data.datasets[0].download_time = 1795173600       # the next scan
            a._track_swings({'item_values': {FISH: 9077}}, {'level': 51})
            self.assertIn(FISH, a.swings)
            self.assertIn('Rugged Hide: 2g 66s 43c -> 90s 77c at', a.swings[FISH]['text'])
            self.assertIn('its own price went 8s 88c -> 7s 77c', a.swings[FISH]['text'])
            self.assertIn('Valued by: Leatherworking: Cured Rugged Hide', a.swings[FISH]['text'])
            entry = anomalies.swing_check(a.swings)
            self.assertEqual(entry['status'], 'warn')
            self.assertIn('1 in the last 24 hours', entry['detail'])

    def test_a_settings_change_is_not_a_swing(self):
        with mock.patch('wfm.app.Engine', lambda w, s: self.fail('nothing should be compared')):
            a = self.app(1795170000, {FISH: {'numAuctions': 399, 'minBuyout': 888}})
            a._track_swings({'item_values': {FISH: 26643}}, {'level': 51})
            a.world.price_data.datasets[0].download_time = 1795173600
            a._track_swings({'item_values': {FISH: 9077}}, {'level': 52})     # a level up between the two
            self.assertEqual(a.swings, {})
        self.assertEqual(anomalies.swing_check({})['status'], 'pass')

    def test_old_swings_drop_after_a_day(self):
        a = self.app(1795170000, {})
        a.swings = {FISH: {'ts': 1, 'text': 'old'}}
        a._track_swings({'item_values': {}}, {})
        self.assertEqual(a.swings, {})


class MarketLimitTests(unittest.TestCase):
    """An hour's farmed loot sells on the AH only as far as your share of the region's daily sales; the rest goes to
    the next best way, usually a vendor (the user, 2026-11-20, after the mob farming review)."""

    def engine(self, meat):
        w = make_world({MAT_AH: meat})
        w.gamedata.items[MAT_AH].sell_price = 10                     # a vendor pays 10
        return Engine(w, dict(SETTINGS))

    def test_breath_of_wind_case(self):
        # 49.4 sold a day in the region x 20% = 9.88 a day at 94s; an hour of Gusting Vortex gives 48 (0.8 x 60)
        e = self.engine({'numAuctions': 78, 'minBuyout': 9900, 'marketValue': 9900, 'regionSale': 9000,
                         'regionSoldPerDay': 49.4})
        v = e.valuer({})
        self.assertEqual(v.lanes(MAT_AH)[0][1], 49.4 * 0.2)
        ah = int(9900 * 0.95)
        each = v.unit_worth(MAT_AH, 48)
        self.assertAlmostEqual(each, (9.88 * ah + (48 - 9.88) * 10) / 48)
        self.assertAlmostEqual(v.unit_worth(MAT_AH, 5), ah)            # under the market: all at the AH price
        self.assertAlmostEqual(v.unit_worth(MAT_AH, 0), ah)
        self.assertEqual(e.loot_worth(MAT_AH, {}, 0.8, 60), int(each))

    def test_no_sales_at_all_go_to_the_vendor(self):
        e = self.engine({'numAuctions': 5, 'minBuyout': 500, 'marketValue': 500})
        self.assertAlmostEqual(e.valuer({}).unit_worth(MAT_AH, 3), 10)

    def test_a_listing_far_above_sales_counts_at_the_sale_price(self):
        # Elemental Air on 2026-11-20 17:23: lowest listing 69s 77c, sells for about 21s 66c across the region
        e = self.engine({'numAuctions': 302, 'minBuyout': 6977, 'marketValue': 3058, 'regionSale': 2166,
                         'regionSoldPerDay': 122.6})
        v = e.valuer({}).value(MAT_AH)
        self.assertIn('ah_price_doubtful', v.flags)
        self.assertEqual(v.value, int(2166 * 0.95))


class KillPaceTests(unittest.TestCase):
    """Kill speed by health (the user, 2026-11-20): the kills-per-hour setting is for a typical mob of your level."""

    def engine(self):
        return Engine(make_world({}), dict(SETTINGS))

    def test_forever_health_from_the_page(self):
        # Toxic Horror for a level 51: 2,979 typical health at 51, its Forever page says 3,293
        pace, note = self.engine().kill_pace(60, 51, 54, [3293])
        self.assertAlmostEqual(pace, 60 * 2979 / 3293)
        self.assertIn('3,293 health (its Wowhead Forever page)', note)

    def test_typical_health_at_its_level_otherwise(self):
        pace, note = self.engine().kill_pace(60, 51, 45)              # Gusting Vortex, not read: 2,217 at level 45
        self.assertAlmostEqual(pace, 60 * 2979 / 2217)
        self.assertIn('typical at level 45, WoW Classic rule', note)

    def test_limits_and_unknown_levels(self):
        e = self.engine()
        self.assertEqual(e.kill_pace(60, 60, 10)[0], 90)             # a level 10 mob for a 60: at most 1.5x
        self.assertEqual(e.kill_pace(60, 20, 60)[0], 30)             # a level 60 mob for a 20: at least half
        self.assertEqual(e.kill_pace(60, 51, None)[0], 60)           # level unknown: the setting as it is
        # Scarlet Spellbinder (57-58, 2,714 health) for a level 51: worked out at level 55, the level it needs
        pace, note = e.kill_pace(60, 55, 58, [2714], 51)
        self.assertAlmostEqual(pace, 60 * 3398 / 2714)
        self.assertIn('level 55, the level you need for it', note)


if __name__ == '__main__':
    unittest.main()
