"""Crafted worth counts only for as many units a day as the recipe can use (the user's decision, 2026-11-15).

Hand-worked numbers. The ingredient is the raw fish (sells for 76 after the AH cut); the recipe turns one fish into a
product that sells for 950 after the cut.
"""
import unittest

from tests.test_engine import COOKED, FISH, PRODUCT, SETTINGS, make_world
from wfm.engine import Engine
from wfm.gamedata import Recipe
from wfm.valuation import capped_total, per_day_text

RAW = {'numAuctions': 5, 'minBuyout': 80, 'marketValue': 90, 'regionSoldPerDay': 500}


def recipe(count=1, cooldown_hours=0):
    return Recipe(spell_id=500, name='Transmute', profession='Cooking', skill_line=185, product_id=PRODUCT,
                  product_count=1, reagents=[(FISH, count)], trivial_low=140, trivial_high=180, min_rank=1,
                  cooldown_ms=int(cooldown_hours * 3600 * 1000))


def engine(product_sold_per_day, count=1, cooldown_hours=0, **settings):
    prices = {FISH: RAW, PRODUCT: {'numAuctions': 5, 'minBuyout': 1000, 'marketValue': 1000,
                                   'regionSoldPerDay': product_sold_per_day, 'regionSalePercent': 0.6}}
    return Engine(make_world(prices, [recipe(count, cooldown_hours)]), dict(SETTINGS, gold=100, **settings))


class CappedTotalTests(unittest.TestCase):
    def test_thorium_bar_case(self):
        # Thorium Bar: 21g 65s through Transmute: Arcanite, which can be done 1 every 2 days; it sells for 17s.
        crafted, sale = 216500, 1700
        self.assertEqual(capped_total(crafted, 0.5, sale, 1), 0.5 * 216500 + 0.5 * 1700)      # 10g 91s
        self.assertEqual(capped_total(crafted, 0.5, sale, 20), 0.5 * 216500 + 19.5 * 1700)    # 14g 14s, not 433g
        self.assertEqual(capped_total(crafted, None, sale, 20), 20 * 216500)                  # no limit known
        self.assertEqual(capped_total(crafted, 0.5, sale, 0), 0)

    def test_per_day_text(self):
        self.assertEqual(per_day_text(0.5), '1 every 2 days')
        self.assertEqual(per_day_text(0.51), '1 every 2 days')
        self.assertEqual(per_day_text(4), '4 a day')
        self.assertEqual(per_day_text(2.5), '2.5 a day')
        self.assertEqual(per_day_text(40), '40 a day')


class ValuerCapTests(unittest.TestCase):
    def test_a_cooldown_caps_crafted_worth(self):
        e = engine(500, cooldown_hours=48)            # the market takes 100 a day, the cooldown allows 0.5
        best = e.best_uses()
        self.assertEqual(best[FISH]['doable_units_per_day'], 0.5)
        self.assertEqual(best[FISH]['doable_cap_by'], 'cooldown')
        v = e.valuer(best)
        one = v.value(FISH)
        self.assertEqual((one.channel, one.crafted, one.craft_cap, one.beyond), ('craft', 950, 0.5, 76))
        self.assertEqual(one.value, int(0.5 * 950 + 0.5 * 76))         # 513: half a craft a day, half sold
        self.assertEqual(v.worth_for(FISH, 20), int(0.5 * 950 + 19.5 * 76))   # 1,957, not 20 x 950 = 19,000
        self.assertIn('1 every 2 days', one.how)
        self.assertIn("cooldown", one.how)
        self.assertAlmostEqual(v.unit_worth(FISH, 20), (0.5 * 950 + 19.5 * 76) / 20)

    def test_a_big_market_changes_nothing_for_a_few(self):
        e = engine(200)                               # 200 x 20% = 40 a day, no cooldown
        best = e.best_uses()
        self.assertEqual(best[FISH]['doable_units_per_day'], 40)
        self.assertEqual(best[FISH]['doable_cap_by'], 'market')
        v = e.valuer(best)
        self.assertEqual(v.value(FISH).value, 950)
        self.assertEqual(v.worth_for(FISH, 3), 3 * 950)
        self.assertIn('what its market takes', v.value(FISH).how)
        self.assertEqual(v.worth_for(FISH, 50), 40 * 950 + 10 * 76)    # past 40 a day: sold raw

    def test_an_ingredient_used_three_per_craft(self):
        e = engine(200, count=3)                      # 40 crafts a day x 3 fish = 120 fish a day
        best = e.best_uses()
        self.assertEqual(best[FISH]['doable_value'], 950 // 3)
        self.assertEqual(best[FISH]['doable_units_per_day'], 120)
        v = e.valuer(best)
        self.assertEqual(v.worth_for(FISH, 130), int(120 * (950 // 3) + 10 * 76))

    def test_a_vendor_sold_product_has_no_market_limit(self):
        # a product that only sells to a vendor: no AH sales, so the usual cap of 200 a day, not 0
        prices = {FISH: RAW}
        world = make_world(prices, [Recipe(spell_id=500, name='Cook', profession='Cooking', skill_line=185,
                                           product_id=COOKED, product_count=1, reagents=[(FISH, 1)], trivial_low=140,
                                           trivial_high=180, min_rank=1)])
        world.gamedata.items[COOKED].sell_price = 500
        best = Engine(world, dict(SETTINGS, gold=100)).best_uses()
        self.assertEqual(best[FISH]['doable_units_per_day'], 200)

    def test_an_hour_of_farming_counts_crafted_worth_for_a_day_only(self):
        e = engine(500, cooldown_hours=48, farm_rates={FISH: 30})
        best = e.best_uses()
        row = next(o for o in e.gathering(best) if o.item_id == FISH)
        self.assertEqual(row.gph, int(0.5 * 950 + 29.5 * 76))         # 2,717 an hour, not 30 x 950 = 28,500
        self.assertEqual(row.units_day, 100.0)                         # the raw fish's own market at your share
        self.assertEqual(row.daily, int(0.5 * 950 + 99.5 * 76))
        self.assertIn('1 every 2 days', row.detail['best_use'])


if __name__ == '__main__':
    unittest.main()
