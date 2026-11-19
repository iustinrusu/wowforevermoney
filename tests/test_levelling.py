"""Levelling planner: skill-up chances and the cheapest path, worked out by hand."""
import unittest

from wfm.levelling import Option, chance, color, plan


def opt(sid, colors, ingredients, ah=0, vendor=0, cap=0.0, learn=0, name=None):
    return Option(spell_id=sid, name=name or f'R{sid}', colors=colors, ingredients=ingredients, ah_value=ah,
                  vendor_value=vendor, ah_cap=cap, learn=learn)


class ChanceTests(unittest.TestCase):
    def test_classic_rule(self):
        c = (100, 140, 160, 180)
        self.assertEqual(chance(c, 99), 0.0)             # can't craft it yet
        self.assertEqual(chance(c, 120), 1.0)            # orange
        self.assertEqual(chance(c, 140), 1.0)            # yellow starts: (180 - 140) / 40
        self.assertEqual(chance(c, 150), 0.75)           # (180 - 150) / (180 - 140)
        self.assertEqual(chance(c, 170), 0.25)           # green
        self.assertEqual(chance(c, 180), 0.0)            # grey
        self.assertEqual([color(c, s) for s in (120, 150, 170, 185)], ['orange', 'yellow', 'green', 'grey'])


class PlanTests(unittest.TestCase):
    def test_cheapest_recipe_point_by_point_with_a_fee_counted_once(self):
        a = opt(1, (1, 10, 15, 20), 100, vendor=10)                 # 90 a craft, fades out from skill 10
        b = opt(2, (5, 30, 40, 50), 300, learn=500)                 # 300 a craft, a 500 fee
        p = plan([a, b], 1, 25)
        # 1-9: A at 90 (sure); 10: 90/1.0; 11: 90/0.9; ... 18: 90/0.2 = 450; 19: A 900 vs B 300 + 500: B; 20-24: B 300
        expected = 9 * 90 + sum(90 / ((20 - s) / 10) for s in range(10, 19)) + 800 + 5 * 300
        self.assertEqual(p['total'], round(expected))                # 4,846
        self.assertEqual([(s['recipe'], s['from'], s['to']) for s in p['steps']], [('R1', 1, 19), ('R2', 19, 25)])
        self.assertEqual(p['learn_total'], 500)
        self.assertEqual(p['steps'][1]['learn'], 500)
        self.assertEqual((p['reached'], p['stuck_at']), (25, None))
        self.assertEqual(p['steps'][0]['crafts'], round(9 + sum(1 / ((20 - s) / 10) for s in range(10, 19)), 1))

    def test_a_known_recipe_has_no_fee(self):
        b = opt(2, (1, 30, 40, 50), 300, learn=500)
        self.assertEqual(plan([b], 1, 3, known={2})['total'], 600)
        self.assertEqual(plan([b], 1, 3)['total'], 1100)

    def test_the_ah_takes_only_so_many_then_the_vendor_price(self):
        # sells for 200 on the AH, but the market takes 2: crafts 3 and 4 sell to a vendor for 10
        o = opt(1, (1, 100, 100, 101), 100, ah=200, vendor=10, cap=2)
        self.assertEqual(plan([o], 1, 5)['total'], -100 - 100 + 90 + 90)

    def test_no_recipe_you_can_get_stops_the_plan(self):
        a = opt(1, (1, 10, 15, 20), 100)
        dropped = opt(2, (20, 30, 40, 50), 50, learn=None)           # a pattern you can't buy
        p = plan([a, dropped], 1, 30)
        self.assertEqual((p['reached'], p['stuck_at']), (20, 20))
        self.assertEqual(plan([a, dropped], 1, 30, known={2})['reached'], 30)   # unless you know it

    def test_any_range_from_x_to_y(self):
        # the user (2026-11-19): not only to 300, any range
        a = opt(1, (1, 100, 150, 200), 100)
        p = plan([a], 40, 60)
        self.assertEqual((p['skill'], p['target'], p['reached']), (40, 60, 60))
        self.assertEqual(p['total'], 20 * 100)                      # 40 -> 60: 20 sure points at 100 each
        self.assertEqual(plan([a], 40, 400)['target'], 300)         # never past 300


class EngineRangeTests(unittest.TestCase):
    def test_engine_and_unlocks_stop_at_the_target(self):
        from tests.test_engine import MAT_VENDOR, PRODUCT, SETTINGS, make_world
        from wfm.engine import Engine
        from wfm.gamedata import Recipe
        r = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 2)], trivial_low=140, trivial_high=180, min_rank=1)
        e = Engine(make_world({}, [r]), dict(SETTINGS))
        out = e.levelling('Cooking', 100, known={500}, target=130)  # thresholds 100/140/160/180: orange to 140
        self.assertEqual((out['skill'], out['target'], out['reached']), (100, 130, 130))
        self.assertEqual(out['crafts'], 30)
        self.assertEqual(e.levelling('Cooking', 100, target=50)['target'], 101)   # the target is above the start


if __name__ == '__main__':
    unittest.main()
