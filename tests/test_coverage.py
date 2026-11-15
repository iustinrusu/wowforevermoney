"""Forever source coverage (wfm/coverage.py): which looted items lack Forever data, and the reading order."""
import unittest
from types import SimpleNamespace

from wfm import coverage
from wfm.gamedata import Item, Recipe


def item(iid, name, cls=7, sub=0):
    return Item(id=iid, name=name, quality=1, item_level=30, req_level=0, sell_price=1, buy_price=0, stack=20,
                class_id=cls, subclass_id=sub, bonding=0)


HIDE, CLOTH, ORE, BAR, THREAD, FISH, SQUID, GLOVES, ELIXIR = range(1, 10)
ITEMS = {HIDE: item(HIDE, 'Heavy Hide', sub=6), CLOTH: item(CLOTH, 'Silk Cloth', sub=5),
         ORE: item(ORE, 'Mithril Ore', sub=7), BAR: item(BAR, 'Mithril Bar', sub=7),
         THREAD: item(THREAD, 'Fine Thread', sub=5), FISH: item(FISH, 'Raw Yellowtail', sub=8),
         SQUID: item(SQUID, 'Raw Winter Squid', cls=0, sub=5), GLOVES: item(GLOVES, 'Fancy Gloves', cls=4, sub=2),
         ELIXIR: item(ELIXIR, 'Elixir', cls=0, sub=2)}
PRICES = {i: {'regionSoldPerDay': 10, 'regionSale': 100 * i} for i in ITEMS}
QUESTIE = {CLOTH: {'npcDrops': [1]}, ORE: {'objectDrops': [9]}, THREAD: {'vendors': [5]}, GLOVES: {'npcDrops': [2]}}
RECIPES = [Recipe(spell_id=1, name='Smelt Mithril', profession='Mining', skill_line=186, product_id=BAR,
                  product_count=1, reagents=[(ORE, 1)], trivial_low=1, trivial_high=2, min_rank=1),
           Recipe(spell_id=2, name='Squid', profession='Cooking', skill_line=185, product_id=ELIXIR,
                  product_count=1, reagents=[(SQUID, 1)], trivial_low=1, trivial_high=2, min_rank=1)]


class CoverageTests(unittest.TestCase):
    def run_audit(self, skinning=None, fishing=None, pages=()):
        return coverage.audit(ITEMS, PRICES, QUESTIE, RECIPES, skinning, fishing, set(pages), fish_hint={FISH, SQUID})

    def test_what_counts_as_looted_and_how(self):
        rows = {r['item_id']: r for r in self.run_audit()['queue']}
        self.assertEqual(rows[HIDE]['kinds'], ['skinning'])
        self.assertEqual(rows[CLOTH]['kinds'], ['drops'])
        self.assertEqual(rows[ORE]['kinds'], ['mining'])             # its node is the object
        self.assertEqual(rows[FISH]['kinds'], ['fishing'])           # meat, but in a fishing table
        self.assertEqual(rows[SQUID]['kinds'], ['fishing'])          # "food" in the data, but fished
        self.assertEqual(rows[GLOVES]['kinds'], ['drops'])
        for crafted_or_bought in (BAR, THREAD, ELIXIR):
            self.assertNotIn(crafted_or_bought, rows)

    def test_a_smelted_bar_found_in_chests_is_looted_from_objects_not_mined(self):
        q = {**QUESTIE, BAR: {'objectDrops': [77]}}                   # Truesilver Bar: smelted, and in chests
        rows = {r['item_id']: r for r in coverage.audit(ITEMS, PRICES, q, RECIPES, None, None, set(),
                                                        fish_hint={FISH, SQUID})['queue']}
        self.assertEqual(rows[BAR]['kinds'], ['objects'])

    def test_materials_first_then_by_traded_value(self):
        order = [r['item_id'] for r in self.run_audit()['queue']]
        self.assertEqual(order[-1], GLOVES, 'gear after every material')
        self.assertEqual(order[:2], [SQUID, FISH])                   # 700c and 600c x 10 a day

    def test_read_data_counts_as_covered(self):
        r = self.run_audit(skinning={'items': {str(HIDE): {}}}, fishing={'Tanaris': {'items': {FISH: 3}}},
                           pages=[CLOTH])
        missing = {x['item_id'] for x in r['queue']}
        self.assertFalse({HIDE, FISH, CLOTH} & missing)
        self.assertEqual((r['materials'], r['materials_covered']), (5, 3))
        self.assertEqual(r['by_kind']['skinning'], [1, 1])

    def test_a_page_without_forever_rows_leaves_the_queue_but_is_not_covered(self):
        # Mithril Ore's page read: "Mined from" had Forever rows. Silk Cloth's page read: "Dropped by" was all
        # Classic Era rows, so Wowhead has no Forever data yet: out of the reading queue, still not covered.
        r = coverage.audit(ITEMS, PRICES, QUESTIE, RECIPES, None, None, {ORE: {'mining'}, CLOTH: set()},
                           fish_hint={FISH, SQUID})
        queue = {x['item_id'] for x in r['queue']}
        waiting = {x['item_id']: x['missing'] for x in r['read_no_data']}
        self.assertNotIn(ORE, queue | set(waiting))
        self.assertEqual(waiting, {CLOTH: ['drops']})
        self.assertNotIn(CLOTH, queue)
        self.assertEqual(r['by_kind']['drops'][0], 0)

    def test_a_crafted_leather_whose_page_lists_no_source_is_left_out(self):
        # Cured Medium Hide, 2026-11-14: a leather (so "skinned" by its kind), made by a recipe, and its Wowhead
        # Forever page has no source tab at all: it is crafted, not looted. A fish with no tabs stays (zone pages).
        recipes = RECIPES + [Recipe(spell_id=3, name='Cure Hide', profession='Leatherworking', skill_line=165,
                                    product_id=HIDE, product_count=1, reagents=[(BAR, 1)], trivial_low=1,
                                    trivial_high=2, min_rank=1)]
        r = coverage.audit(ITEMS, PRICES, QUESTIE, recipes, None, None, {HIDE: set(), FISH: set()},
                           fish_hint={FISH, SQUID}, unlooted={HIDE, FISH})
        ids = {x['item_id'] for x in r['queue'] + r['read_no_data']}
        self.assertNotIn(HIDE, ids)
        self.assertIn(FISH, ids)

    def test_rarely_traded_items_are_left_out(self):
        prices = {**PRICES, HIDE: {'regionSoldPerDay': 0.2, 'regionSale': 500}}
        r = coverage.audit(ITEMS, prices, QUESTIE, RECIPES, None, None, fish_hint={FISH, SQUID})
        self.assertNotIn(HIDE, [x['item_id'] for x in r['queue']])

    def test_describe_is_a_plain_sentence(self):
        row = self.run_audit()['queue'][0]
        self.assertIn('no Forever data on how it is fished', coverage.describe(row))


if __name__ == '__main__':
    unittest.main()
