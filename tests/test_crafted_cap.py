"""Crafted worth counts only for as many units a day as the recipe can use (the user's decision, 2026-11-15).

Hand-worked numbers. The ingredient is the raw fish (sells for 76 after the AH cut); the recipe turns one fish into a
product that sells for 950 after the cut. None are listed on the AH right now (realm market value 80), so nothing
caps the crafted worth at a buy price (BuyPriceCapTests: that cap, the user's decision of 2026-11-20).
"""
import unittest

from tests.test_engine import COOKED, FISH, MAT_AH, PRODUCT, SETTINGS, make_world
from wfm.engine import Engine
from wfm.gamedata import Recipe
from wfm.valuation import capped_total, per_day_text

RAW = {'numAuctions': 0, 'marketValue': 80, 'regionSoldPerDay': 500}


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


# The 13:22 snapshot of 2026-11-20. Cured Rugged Hide makes 2 in Forever (game files and ForeverRecipes):
# 1 Rugged Hide + 1 Refined Deeprock Salt. Here the hide is FISH, the salt MAT_AH, Cured Rugged Hide COOKED.
HIDE = {'numAuctions': 399, 'minBuyout': 888, 'marketValue': 1827, 'regionSale': 529, 'regionSoldPerDay': 87.672}
SALT = {'numAuctions': 34, 'minBuyout': 655599, 'marketValue': 514633, 'regionSale': 537500, 'regionSoldPerDay': 16.244}
CURED = {'numAuctions': 24, 'minBuyout': 359075, 'marketValue': 289868, 'regionMarketValue': 261972,
         'regionSale': 294495, 'regionSoldPerDay': 11.22}
# the same listing, with typical prices that back it (realm and region averages and sales at 35g 91s): a sound craft
SOUND = dict(CURED, marketValue=359075, regionMarketValue=359075, regionSale=359075)


def hide_engine(hide=None, salt=None, cured=None):
    r = Recipe(spell_id=500, name='Cured Rugged Hide', profession='Cooking', skill_line=185, product_id=COOKED,
               product_count=2, reagents=[(FISH, 1), (MAT_AH, 1)], trivial_low=140, trivial_high=180, min_rank=1)
    prices = {FISH: hide or HIDE, MAT_AH: salt or SALT, COOKED: cured or SOUND}
    return Engine(make_world(prices, [r]), dict(SETTINGS, gold=100))


class BuyPriceCapTests(unittest.TestCase):
    """An ingredient listed on your realm's AH is worth at most what buying one costs (the user's decision,
    2026-11-20, after the farm meter valued one Rugged Hide at 2g 66s 43c). The craft's profit stays on its own row.
    Here the craft is sound at typical prices too (SOUND), so only the cap is at work."""

    def test_the_rugged_hide_case(self):
        e = hide_engine()
        best = e.best_uses()
        hide = best[FISH]
        # 2 x 359,075 x 0.95 = 682,242 for two Cured Rugged Hides, minus the salt at 655,599: 26,643 (2g 66s 43c),
        # what the meter showed; capped at the hide's lowest listing, 888 (8s 88c, 399 listed)
        self.assertEqual(hide['margin'], 2 * int(359075 * 0.95) - 655599)
        self.assertEqual(hide['margin'], 26643)
        self.assertEqual((hide['doable_value'], hide['value'], hide['buy_now']), (888, 888, 888))
        self.assertTrue(hide['capped'] and hide['doable_capped'])
        v = e.valuer(best).value(FISH)
        self.assertEqual((v.value, v.channel), (888, 'craft'))      # beats selling it: 888 x 0.95 = 843
        self.assertIn('crafted_at_buy_price', v.flags)
        self.assertIn('what buying one costs on the AH, 8s 88c', v.how)
        # the salt: 682,242 - 888 = 681,354 crafted, but buying one costs 655,599
        self.assertEqual((best[MAT_AH]['margin'], best[MAT_AH]['doable_value']), (681354, 655599))

    def test_an_hour_later_the_same_value(self):
        # 14:22: Cured Rugged Hide 355,075 and the salt 665,565 moved the margin to 9,077 (90s 77c);
        # the hide's worth only follows its own price (7s 77c, 486 listed)
        e = hide_engine(hide=dict(HIDE, minBuyout=777, numAuctions=486),
                        salt=dict(SALT, minBuyout=665565, numAuctions=49), cured=dict(SOUND, minBuyout=355075))
        hide = e.best_uses()[FISH]
        self.assertEqual(hide['margin'], 2 * int(355075 * 0.95) - 665565)
        self.assertEqual(hide['margin'], 9077)
        self.assertEqual(hide['doable_value'], 777)

    def test_a_craft_that_loses_today_gives_no_crafted_worth(self):
        # hides at 5g: the craft costs 655,599 + 50,000 and brings 682,242, so a hide is worth more sold
        e = hide_engine(hide=dict(HIDE, minBuyout=50000, numAuctions=10))
        self.assertNotIn(FISH, e.best_uses())
        self.assertEqual(e.no_crafted_worth[0]['today'], 682242 - 655599 - 50000)
        self.assertEqual(e.valuer(e.best_uses()).value(FISH).channel, 'AH')

    def test_none_listed_keeps_the_crafted_worth(self):
        hide = {'numAuctions': 0, 'marketValue': 1827, 'regionSoldPerDay': 87.672}
        best = hide_engine(hide=hide).best_uses()[FISH]
        self.assertEqual((best['doable_value'], best['buy_now'], best['capped']), (26643, None, False))

    def test_a_thin_supply_counts_at_the_market_value(self):
        # 2 listed at 300 won't last: buying the next one costs about the realm's market value, 1,827
        e = hide_engine(hide=dict(HIDE, minBuyout=300, numAuctions=2))
        self.assertEqual(e.buy_now(FISH), 1827)
        self.assertEqual(e.best_uses()[FISH]['doable_value'], 1827)
        e = hide_engine(hide=dict(HIDE, minBuyout=300, numAuctions=4))
        self.assertEqual(e.buy_now(FISH), 300)


class SecondOpinionValueTests(unittest.TestCase):
    """A craft that only pays at today's unusual prices gives its ingredients no crafted worth, as its row is kept out
    of Top picks (the user's yes, 2026-11-20). The real 13:22 prices: Cured Rugged Hide listed at 35g 91s, but its
    realm average is 28g 99s, the region's 26g 20s and it sells for 29g 45s."""

    def test_the_real_rugged_hide_prices(self):
        e = hide_engine(cured=CURED)
        best = e.best_uses()
        self.assertNotIn(FISH, best)                     # no crafted worth for the hide
        self.assertNotIn(MAT_AH, best)                   # nor for the salt
        r = e.no_crafted_worth[0]
        self.assertEqual(r['recipe'], 'Cured Rugged Hide')
        # today: 682,242 - 655,599 - 888 = 25,755 a craft; typical: the median of 289,868, 261,972 and 294,495 is
        # 289,868, x 0.95 = 275,374, x 2 = 550,748, minus the same 656,487: a loss of 105,739
        self.assertEqual((r['today'], r['typical']), (25755, 550748 - 656487))
        v = e.valuer(best).value(FISH)
        self.assertEqual((v.value, v.channel), (int(888 * 0.95), 'AH'))     # 8s 43c: sell it

    def test_data_health_lists_it(self):
        from wfm import anomalies
        e = hide_engine(cured=CURED)
        best = e.best_uses()
        e.item_values(e.valuer(best))
        held, summary = anomalies.check_values(e, best)
        self.assertEqual((held, summary['no_crafted_worth']), ([], 1))
        self.assertIn("Cured Rugged Hide (Cooking): makes 2g 57s 55c a craft at today's prices but loses 10g 57s 39c",
                      summary['no_crafted_worth_examples'][0])
        self.assertIn('Raw Spotted Yellowtail, Raw Meat', summary['no_crafted_worth_examples'][0])
        entry = anomalies.value_rule_check({'anomalies': {'findings': held, 'values': summary}})
        self.assertEqual(entry['status'], 'pass')
        self.assertIn('none came out above it', entry['detail'])
        self.assertIn("1 craft that only pays at today's unusual prices gives its ingredients no crafted worth", entry['detail'])


if __name__ == '__main__':
    unittest.main()
