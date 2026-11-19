"""Levelling planner: skill-up chances and the cheapest path, worked out by hand."""
import unittest

from wfm.levelling import Option, chance, color, plan


def opt(sid, colors, ingredients, ah=0, vendor=0, cap=0.0, learn=0, name=None, find=''):
    return Option(spell_id=sid, name=name or f'R{sid}', colors=colors, ingredients=ingredients, ah_value=ah,
                  vendor_value=vendor, ah_cap=cap, learn=learn, find=find)


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
    def test_cheapest_path_with_a_fee_counted_once(self):
        a = opt(1, (1, 10, 15, 20), 100, vendor=10)                 # 90 a craft, fades out from skill 10
        b = opt(2, (5, 30, 40, 50), 300, learn=500)                 # 300 a craft, a 500 fee
        p = plan([a, b], 1, 25)
        # B is needed anyway from 20 (A is grey), so its fee is paid anyway: use B wherever A costs more than 300.
        # 1-9: A at 90 (sure); 10-17: 90 / ((20 - s) / 10), up to 300 at 17 (a tie: A stays); 18-24: B at 300
        # The first planner (point by point, fee charged to the first point) kept A until 19: 4,846, 150 more.
        expected = 9 * 90 + sum(90 / ((20 - s) / 10) for s in range(10, 18)) + 500 + 7 * 300
        self.assertEqual(p['total'], round(expected))                # 4,696
        self.assertEqual([(s['recipe'], s['from'], s['to']) for s in p['steps']], [('R1', 1, 18), ('R2', 18, 25)])
        self.assertEqual(p['learn_total'], 500)
        self.assertEqual(p['steps'][1]['learn'], 500)
        self.assertEqual((p['reached'], p['stuck_at']), (25, None))
        self.assertEqual(p['steps'][0]['crafts'], round(9 + sum(1 / ((20 - s) / 10) for s in range(10, 18)), 1))

    def test_a_fee_is_worth_it_over_many_points(self):
        # A: free, 100 a point. B: a 300 fee, 50 a point. Point by point, B's first point cost 350 (> 100) and B was
        # never chosen; over 20 points B saves 20 x 50 = 1,000 for its 300 fee.
        a = opt(1, (1, 100, 100, 101), 100)
        b = opt(2, (1, 100, 100, 101), 50, learn=300)
        p = plan([a, b], 1, 21)
        self.assertEqual(p['total'], 300 + 20 * 50)
        self.assertEqual([s['recipe'] for s in p['steps']], ['R2'])
        self.assertEqual(plan([a, b], 1, 3)['total'], 2 * 100)      # for 2 points the fee isn't worth it

    def test_learns_what_it_needs_even_when_the_end_is_out_of_reach(self):
        # 2026-11-19 bug: with points nobody could give (21-29), every total was infinite and the planner dropped the
        # recipe it needed for 10-20 (Leatherworking stopped at 265 instead of 270)
        a = opt(1, (1, 100, 100, 101), 100, name='A')
        a.colors = (1, 10, 10, 11)                                    # gives points up to 10
        b = opt(2, (5, 100, 100, 101), 300, learn=500, name='B')
        b.colors = (5, 20, 20, 21)                                    # up to 20
        p = plan([a, b], 1, 30)
        self.assertEqual((p['reached'], p['stuck_at']), (21, 21))
        self.assertEqual([s['recipe'] for s in p['steps']], ['A', 'B'])

    def test_disenchanting_counts_only_when_you_can(self):
        o = opt(1, (1, 100, 100, 101), 100, vendor=10)
        o.de_value = 60
        self.assertEqual(plan([o], 1, 3)['total'], 2 * 90)           # nobody can disenchant it: vendor
        o.de_can = True
        p = plan([o], 1, 3)
        self.assertEqual(p['total'], 2 * 40)                          # disenchanted: 100 - 60
        self.assertEqual(p['steps'][0]['back_how'], 'disenchant')
        self.assertEqual(plan([o], 1, 3, use_de=False)['total'], 2 * 90)

    def test_materials_back_and_shopping_list(self):
        o = opt(1, (1, 10, 15, 20), 100, vendor=10)
        o.mats = [(2589, 2, 50, False)]                               # 2 Linen Cloth at 50 a craft
        p = plan([o], 1, 12)          # 1-9 sure (9 crafts), 10 and 11: 1/1.0 + 1/0.9 crafts
        crafts = 9 + 1 + 1 / 0.9
        self.assertEqual(p['materials_total'], round(crafts * 100))
        self.assertEqual(p['back_total'], round(crafts * 10))
        self.assertEqual(p['total'], round(crafts * 90))
        self.assertEqual(p['shopping'], [{'item_id': 2589, 'count': 2 * 12, 'each': 50, 'own': False, 'total': 1200}])

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

    def test_a_pattern_you_have_to_find_fills_only_the_gap(self):
        # the user (2026-11-19): every recipe in the game, and where to get it. A pattern that can't be bought with gold
        # (it only drops) is used only where nothing you can buy gives a point; its cost is unknown, so not in the total
        a = opt(1, (1, 10, 15, 20), 100)
        dropped = opt(2, (15, 30, 40, 50), 10, learn=None, find='drop')      # far cheaper, but you'd have to find it
        p = plan([a, dropped], 1, 30)
        self.assertEqual((p['reached'], p['stuck_at']), (30, None))
        self.assertEqual([st['spell_id'] for st in p['steps']], [1, 2])     # a, then the drop (a stops at 20)
        # once you have to find it anyway, it is used wherever it is cheaper: from 15, not only from 20
        self.assertEqual(p['to_find'], [{'spell_id': 2, 'recipe': 'R2', 'how': 'drop', 'from': 15}])
        a_cost = 9 * 100 + sum(100 / ((20 - s) / 10) for s in range(10, 15))  # orange to 10, then yellow
        self.assertEqual(p['total'], round(a_cost + 15 * 10))              # its learning cost isn't known: not counted
        self.assertEqual(p['learn_total'], 0)
        bought = opt(3, (15, 30, 40, 50), 500, learn=10_000)                # one you can buy, even dear, comes first
        self.assertEqual([st['spell_id'] for st in plan([a, dropped, bought], 1, 30)['steps']], [1, 3])
        self.assertEqual(plan([a, dropped], 1, 30, known={2})['to_find'], [])   # you know it: nothing to find

    def test_a_recipe_with_no_known_source_comes_last(self):
        a = opt(1, (1, 10, 15, 20), 100)
        nowhere = opt(2, (15, 30, 40, 50), 1, learn=None, find='unknown')
        quest = opt(3, (15, 30, 40, 50), 50, learn=None, find='quest')
        self.assertEqual([st['spell_id'] for st in plan([a, nowhere, quest], 1, 30)['steps']], [1, 3])
        self.assertEqual(plan([a, nowhere], 1, 30)['to_find'][0]['how'], 'unknown')

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

    def test_the_ah_takes_two_days_of_sales_at_the_usual_sale_price(self):
        # the user (2026-11-19): "slow sells should not rank that high in the algorithm deciding best route". Until then
        # the AH took a week of your share at the lowest listing.
        from tests.test_engine import MAT_VENDOR, PRODUCT, SETTINGS, make_world
        from wfm.engine import Engine
        from wfm.gamedata import Recipe
        r = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 2)], trivial_low=140, trivial_high=180, min_rank=1)
        p = {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1000, 'regionMarketValue': 900, 'regionSale': 600,
             'regionSoldPerDay': 5, 'regionSalePercent': 0.5}
        out = Engine(make_world({PRODUCT: p}, [r]), dict(SETTINGS)).levelling('Cooking', 100, known={500}, target=130)
        st = out['steps'][0]                                   # 30 sure crafts (orange to 140), 2 Vendor Spice at 10 each
        self.assertEqual(st['channels']['AH'], 570)            # the lower of 1,000 listed and 600 usually paid, minus 5%
        self.assertAlmostEqual(st['ah_cap'], 2.0)              # 5 a day x your 20% share x 2 days
        self.assertAlmostEqual(st['ah_per_day'], 1.0)
        self.assertEqual(st['back'], 2 * 570 + 28 * 20)        # 2 on the AH, the other 28 to a vendor for 20
        self.assertEqual(out['total'], 30 * 20 - 1700)
        self.assertEqual(out['ah_days'], 2)
        # a slow seller: 1 a day in the region, 0.2 at your share (one sale every 5 days): 0.4 of a sale counts
        slow = {**p, 'regionSoldPerDay': 1}
        st = Engine(make_world({PRODUCT: slow}, [r]), dict(SETTINGS)).levelling('Cooking', 100, known={500}, target=130)['steps'][0]
        self.assertAlmostEqual(st['ah_per_day'], 0.2)
        self.assertEqual(st['back'], round(0.4 * 570 + 29.6 * 20))      # 820
        self.assertEqual(st['back_how'], 'AH for 0.4, then vendor')
        # the setting: a week, as before 2026-11-19
        week = Engine(make_world({PRODUCT: p}, [r]), dict(SETTINGS, levelling_ah_days=7))
        st = week.levelling('Cooking', 100, known={500}, target=130)['steps'][0]
        self.assertAlmostEqual(st['ah_cap'], 7.0)
        self.assertEqual(st['back'], 7 * 570 + 23 * 20)

    def test_cooldown_crafts_are_left_out(self):
        # one craft every few days (Mooncloth, Transmute: Arcanite): the path used them for 20 points in a row
        from tests.test_engine import MAT_VENDOR, PRODUCT, SETTINGS, make_world
        from wfm.engine import Engine
        from wfm.gamedata import Recipe
        r = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 2)], trivial_low=140, trivial_high=180, min_rank=1)
        cd = Recipe(spell_id=501, name='Moon Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                    product_count=1, reagents=[(MAT_VENDOR, 1)], trivial_low=140, trivial_high=180, min_rank=1,
                    cooldown_ms=48 * 3_600_000)
        w = make_world({}, [r, cd])
        w.skillup.thresholds[501] = [100, 140, 160, 180]
        out = Engine(w, dict(SETTINGS)).levelling('Cooking', 100, known={500, 501}, target=130)
        self.assertEqual(out['options'], 1)
        self.assertEqual({st['spell_id'] for st in out['steps']}, {500})


if __name__ == '__main__':
    unittest.main()
