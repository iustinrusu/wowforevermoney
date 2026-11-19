"""Biggest markets (markets.py) and the item-interactions report (interactions.py), worked out by hand."""
import unittest
from types import SimpleNamespace

from wfm import gamedata, interactions, markets
from wfm.gamedata import GameData, Item, Recipe


def item(iid, name, quality=1, cls=7):
    return Item(id=iid, name=name, quality=quality, item_level=10, req_level=0, sell_price=0, buy_price=0, stack=20,
                class_id=cls, subclass_id=0, bonding=0)


P = lambda sale, spd, listed=5: {'regionSale': sale, 'regionMarketValue': sale, 'regionSoldPerDay': spd,
                                 'regionSalePercent': 0.5, 'numAuctions': listed, 'minBuyout': sale}


class MarketsTests(unittest.TestCase):
    def test_ranked_by_gold_traded_with_sources_and_ways_in(self):
        items = {1: item(1, 'Arcanite Bar', 2), 2: item(2, 'Destiny', 4, cls=2), 3: item(3, 'Copper Bar'),
                 4: item(4, 'Rare Thing')}
        prices = {1: P(442400, 36.8), 2: P(1828400, 1.8), 3: P(228, 4091.0), 4: P(100000, 0.5)}
        craft = SimpleNamespace(kind='craft', title='Transmute: Arcanite', key='craft:17187', daily=200000,
                                profit_unit=200000, doable=False, needs='Learn Alchemy', gph=None)
        farm = SimpleNamespace(kind='gather', title='Farm Arcanite Bar', key='gather:1', daily=3397600, gph=None,
                               profit_unit=1, doable=True, needs='')    # your share of the market: not a way in
        rows = markets.build(prices, items, {1: ['Alchemy'], 3: ['Mining']}, lambda i: i == 3,
                             {2: {}, 3: {'npcDrops': []}}, set(), {1: [craft, farm]})
        # every item that sells, ranked by price x square root of sold a day: Arcanite 268g, Destiny 245g,
        # Rare Thing 7g (10g, 1 every 2 days), Copper Bar 1g 46s (2s 28c, 4,091 a day)
        self.assertEqual([r['name'] for r in rows], ['Arcanite Bar', 'Destiny', 'Rare Thing', 'Copper Bar'])
        self.assertEqual(rows[0]['score'], int(442400 * 36.8 ** 0.5))
        self.assertEqual(rows[0]['gold_a_day'], int(36.8 * 442400))                               # 1,628g a day
        self.assertFalse(rows[0]['yours'])                       # the craft needs Alchemy
        by_gold = markets.page(rows, 'gold')['rows']
        self.assertEqual([r['name'] for r in by_gold][:3], ['Arcanite Bar', 'Destiny', 'Copper Bar'])   # 1,628g, 329g, 93g
        p = markets.page(rows, 'score', 'noway', 0, 2)
        self.assertEqual((p['total'], p['all'], p['way'], len(p['rows'])), (3, 4, 1, 2))
        self.assertEqual(p['rows'][0]['rank'], 1)
        self.assertEqual(rows[0]['sources'], ['made by Alchemy'])
        self.assertEqual([(w['kind'], w['value'], w['per']) for w in rows[0]['ways']], [('craft', 200000, 'a day')])
        self.assertEqual(rows[1]['sources'], [])                 # a dungeon drop: nothing the app reads knows it
        self.assertEqual(rows[1]['ways'], [])
        self.assertIn('wowhead.com/forever/item=2', rows[1]['wowhead'])
        self.assertEqual(rows[3]['sources'], ['made by Mining', 'sold by a vendor'])


class InteractionsTests(unittest.TestCase):
    def test_counted_and_missing(self):
        gd = GameData(build='test')
        gd.items = {10: item(10, 'Greater Essence'), 11: item(11, 'Lesser Essence'), 12: item(12, 'Red Crystal'),
                    13: item(13, 'Book')}
        mk = lambda sid, prof, product, **kw: Recipe(spell_id=sid, name=f'S{sid}', profession=prof, skill_line=1,
                                                     product_id=product, product_count=1, reagents=[(11, 3)],
                                                     trivial_low=0, trivial_high=0, min_rank=1, **kw)
        gd.recipes = [mk(1, gamedata.NO_PROFESSION, 10, use_item=11), mk(2, 'Comprehension', 13),
                      mk(3, 'Leatherworking', 13, tool_id=99)]
        gd.other_creates = [(4, 'Red Transmutation', 12, 5, [(12, 5)], 'no player source in the game data (an NPC, object or quest casts it)')]
        prices = {12: P(1398, 123.8), 13: P(100, 0.2), 10: P(26999, 105.5)}
        rep = interactions.report(gd, prices)
        self.assertEqual(rep['kinds']['Using up or combining items (essences, Darkmoon cards)'], {'spells': 1, 'counted': 1})
        self.assertEqual(rep['kinds']['Recipes: Comprehension'], {'spells': 1, 'counted': 0})
        self.assertEqual(rep['kinds']['Using a tool you keep (Salt Shaker)'], {'spells': 1, 'counted': 1})
        self.assertEqual([m['product'] for m in rep['missing']], [12])        # the book barely sells: not listed
        self.assertEqual(rep['missing'][0]['gold_a_day'], int(123.8 * 1398))
        c = interactions.check(rep, lambda i: gd.items[i].name)
        self.assertEqual(c['status'], 'warn')
        self.assertIn('Red Crystal (12)', c['examples'][0])


if __name__ == '__main__':
    unittest.main()
