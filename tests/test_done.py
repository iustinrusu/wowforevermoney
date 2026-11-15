"""Done for today: ticks per character and day, and how they change Top picks, rows and the plan."""
import tempfile
import unittest
from pathlib import Path

from tests.test_engine import CHEAP_SNIPE, MAT_AH, MAT_VENDOR, PRODUCT, SETTINGS, make_world
from wfm import done, plan
from wfm.engine import Engine
from wfm.gamedata import Recipe


class DoneStoreTests(unittest.TestCase):
    def test_ticks_are_per_character_and_reset_each_day(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, 'done.json')
            day1 = 1_800_000_000
            done.mark('Testchar Alpha', 'craft:1', 5, 5, 'Craft A', path=p, now=day1)
            self.assertEqual(done.today('Testchar Alpha', p, day1)['craft:1']['done'], 5)
            self.assertEqual(done.today('Alt Beta', p, day1), {})
            self.assertEqual(done.today('Testchar Alpha', p, day1 + 86400), {})      # tomorrow: gone
            done.mark('Testchar Alpha', 'craft:1', 0, 0, undo=True, path=p, now=day1)
            self.assertEqual(done.today('Testchar Alpha', p, day1), {})


class DoneEngineTests(unittest.TestCase):
    def rows(self, ticks):
        r = Recipe(spell_id=500, name='Dish', profession='Cooking', skill_line=185, product_id=PRODUCT, product_count=1,
                   reagents=[(MAT_VENDOR, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        prices = {PRODUCT: {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1000, 'regionSoldPerDay': 50,
                            'regionSalePercent': 0.8, 'regionSale': 1000}}
        e = Engine(make_world(prices, [r]), dict(SETTINGS, gold=100, done_today=ticks))
        return e.run()

    def test_a_full_tick_leaves_top_picks_a_partial_one_keeps_what_is_left(self):
        res = self.rows({})
        o = next(o for o in res['opportunities'] if o.kind == 'craft')
        self.assertIn(o.key, res['top']['now'])
        full = self.rows({o.key: {'done': 10, 'of': 10}})
        f = next(x for x in full['opportunities'] if x.key == o.key)
        self.assertIn('done_today', f.flags)
        self.assertNotIn(o.key, full['top']['now'])
        self.assertNotIn(o.key, [a.get('key') for a in full['plan']['actions']])
        part = self.rows({o.key: {'done': 4, 'of': 10}})
        p = next(x for x in part['opportunities'] if x.key == o.key)
        self.assertEqual(p.units_day, round(o.units_day - 4, 2))
        self.assertEqual(p.daily, int(p.profit_unit * p.units_day))


if __name__ == '__main__':
    unittest.main()
