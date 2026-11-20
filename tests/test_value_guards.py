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


if __name__ == '__main__':
    unittest.main()
