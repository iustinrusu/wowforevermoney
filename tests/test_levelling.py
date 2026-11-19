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


class RankTrainingTests(unittest.TestCase):
    """A3 (2026-11-19): the next profession rank is trained where the path needs it, with its cost."""

    def test_the_plan_pays_for_a_rank_where_it_is_needed(self):
        a = opt(1, (1, 400, 401, 402), 100)                         # orange all the way: 100 a point
        t = [{'at': 75, 'cost': 500, 'name': 'Journeyman'}]
        p = plan([a], 60, 90, training=t)
        self.assertEqual(p['total'], 30 * 100 + 500)
        self.assertEqual(p['train_total'], 500)
        # the step stops at 75 for the training, though the same recipe goes on after it
        self.assertEqual([(s['from'], s['to']) for s in p['steps']], [(60, 75), (75, 90)])
        self.assertNotIn('train', p['steps'][0])
        self.assertEqual(p['steps'][1]['train']['name'], 'Journeyman')
        self.assertEqual(p['steps'][1]['train']['cumulative'], 15 * 100 + 500)   # the total once it is paid
        self.assertEqual(p['steps'][1]['cumulative'], 30 * 100 + 500)
        self.assertEqual(sum(s['cost'] for s in p['steps']) + p['train_total'], p['total'])
        self.assertEqual([x['name'] for x in p['training']], ['Journeyman'])
        # a path that doesn't get there pays nothing
        stuck = plan([opt(1, (1, 70, 71, 72), 100)], 60, 90, training=t)
        self.assertEqual((stuck['stuck_at'], stuck['train_total']), (72, 0))         # grey at 72

    def _world(self):
        from tests.test_engine import MAT_VENDOR, PRODUCT, make_world
        from wfm.gamedata import Recipe
        r = Recipe(spell_id=500, name='Tasty Dish', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 2)], trivial_low=400, trivial_high=402, min_rank=1)
        w = make_world({}, [r])
        w.skillup.thresholds[500] = [2, 400, 401, 402]          # orange from 2 to 300 (an orange of 1 is "unknown")
        # SkillUpForever's tables for Cooking (line 185): a trainer to 150, a book to 225, a quest a side to 300
        w.skillup.rank_trainers = {185: [(150, 500, 50, 10)]}
        w.skillup.rank_books = {185: [(225, 16072, 10000, 125, 0)]}
        w.skillup.rank_quests = {185: [(300, 6610, 225, 35, 'A'), (300, 6611, 225, 35, 'H')]}
        # trainers and the most they teach: 100 (both factions) and 101 (Alliance) to 150, 102 only to 75
        w.skillup.profession_trainers = {185: [(100, 150), (101, 150), (102, 75)]}
        w.questie.npcs[102] = {'name': 'Novice Cook', 'friendlyToFaction': 'AH', 'zoneID': 1}
        return w

    def test_engine_ranks_with_fee_skill_level_and_who_teaches_them(self):
        from tests.test_engine import SETTINGS
        from wfm.engine import Engine
        e = Engine(self._world(), dict(SETTINGS, level=30))
        out = e.levelling('Cooking', 2, known={500}, target=300)
        tr = out['training']
        self.assertEqual([(t['name'], t['at'], t['cap'], t['how'], t['cost']) for t in tr],
                         [('Journeyman', 75, 150, 'trainer', 500), ('Expert', 150, 225, 'book', 10000),
                          ('Artisan', 225, 300, 'quest', 0)])
        self.assertEqual([p['name'] for p in tr[0]['trainers']], ['Horde Trader'])   # yours, and teaches to 150
        self.assertEqual((tr[0]['skill'], tr[0]['level'], tr[0]['level_short']), (50, 10, False))
        self.assertEqual((tr[1]['item_id'], tr[1]['source']), (16072, 'its list price (game files)'))
        self.assertEqual(tr[1]['book_name'], 'Item 16072')
        self.assertEqual(tr[2]['quest'], 6611)                       # the Horde's quest
        self.assertTrue(tr[2]['level_short'])                        # it asks for 35; you are 30
        self.assertFalse(tr[2]['forever_quest'])                     # QuestieDB doesn't have it here
        # with QuestieDB's Forever quest: its name, giver, skill and level win
        w = self._world()
        w.questie.quests = {6611: {'name': 'Clamlette Surprise', 'startedBy': [[100]], 'requiredSkill': [185, 230],
                                   'requiredLevel': 28}}
        art = Engine(w, dict(SETTINGS, level=30)).levelling('Cooking', 2, known={500})['training'][2]
        self.assertEqual((art['quest_name'], [g['name'] for g in art['givers']], art['skill'], art['level'],
                          art['level_short'], art['forever_quest']),
                         ('Clamlette Surprise', ['Horde Trader'], 230, 28, False, True))
        self.assertEqual(out['train_total'], 10500)
        self.assertEqual(sum(s['cost'] for s in out['steps']) + 10500, out['total'])
        self.assertEqual([s['train']['name'] for s in out['steps'] if 'train' in s], ['Journeyman', 'Expert', 'Artisan'])

    def test_a_rank_you_have_is_left_out(self):
        from tests.test_engine import SETTINGS
        from wfm.engine import Engine
        w = self._world()
        # your Cooking is 150 (SETTINGS): with a cap of 225 the addon read, you have Expert already
        mine = Engine(w, dict(SETTINGS, profession_caps={'Cooking': 225})).levelling('Cooking', 150, known={500})
        self.assertEqual([t['name'] for t in mine['training']], ['Artisan'])
        self.assertEqual(mine['cap'], 225)
        # no cap known: at exactly 150 you may still need it
        self.assertEqual([t['name'] for t in Engine(w, dict(SETTINGS)).levelling('Cooking', 150, known={500})['training']],
                         ['Expert', 'Artisan'])
        # planning from another skill: your cap doesn't count, a skill past a rank's start does
        other = Engine(w, dict(SETTINGS, profession_caps={'Cooking': 225})).levelling('Cooking', 100, known={500})
        self.assertEqual([t['name'] for t in other['training']], ['Expert', 'Artisan'])


    def test_without_rank_tables_the_path_still_says_where_it_stops(self):
        # SkillUpForever deleted (2026-11-19): no fee or place, nothing counted, but the stops at 75, 150, 225 stay
        from tests.test_engine import SETTINGS
        from wfm.engine import Engine
        w = self._world()
        w.skillup.rank_trainers, w.skillup.rank_books, w.skillup.rank_quests = {}, {}, {}
        out = Engine(w, dict(SETTINGS, level=30)).levelling('Cooking', 2, known={500})
        self.assertEqual([(t['name'], t['at'], t['how'], t['cost']) for t in out['training']],
                         [('Journeyman', 75, 'unknown', 0), ('Expert', 150, 'unknown', 0), ('Artisan', 225, 'unknown', 0)])
        self.assertEqual(out['train_total'], 0)
        self.assertFalse(any(t['level_short'] for t in out['training']))
        # rogue poisons have no ranks
        from wfm.gamedata import Recipe
        from tests.test_engine import MAT_VENDOR, PRODUCT
        w.gamedata.recipes.append(Recipe(spell_id=900, name='Poison', profession='Poisons', skill_line=40,
                                         product_id=PRODUCT, product_count=1, reagents=[(MAT_VENDOR, 1)],
                                         trivial_low=400, trivial_high=402, min_rank=1))
        w.skillup.thresholds[900] = [2, 400, 401, 402]
        self.assertEqual(Engine(w, dict(SETTINGS)).levelling('Poisons', 2, known={900})['training'], [])


class MaterialsAndPatternsTests(unittest.TestCase):
    def test_skillupforevers_recipe_items_in_both_formats(self):
        # SkillUpForever changed RecipeScrolls to {spell: {item, skill}}; the app read it as nothing until 2026-11-19
        from tests.test_engine import SETTINGS, make_world
        from wfm.engine import Engine
        w = make_world({}, [])
        w.skillup.recipe_scrolls = {2158: [2406, 65], 5000: 2163}          # new form, then the older {item: spell}
        idx = Engine(w, dict(SETTINGS))._spell_to_recipe_items
        self.assertEqual((idx[2158], idx[2163]), ([2406], [5000]))

    def test_yours_only_where_forever_data_says_your_gathering_gives_it(self):
        # 2026-11-19: by the item's kind, a skinner saw Ironfeather (a bird drop) and Cured Rugged Hide (made by
        # Leatherworking) marked "yours" on the Leatherworking path
        from tests.test_engine import SETTINGS, item, make_world
        from wfm.engine import Engine
        from wfm.gamedata import Recipe
        HIDE, FEATHER, CURED, HERB, ORE, BAR, CHEST_HERB, ODD, VEST, COAL, STEEL, SANSAM, WOOL = range(20, 33)
        w = make_world({}, [])
        for it in (item(HIDE, 'Rugged Hide', sub=6), item(FEATHER, 'Ironfeather', sub=6),
                   item(CURED, 'Cured Rugged Hide', sub=6), item(HERB, 'Peacebloom', sub=9),
                   item(ORE, 'Copper Ore', sub=7), item(BAR, 'Copper Bar', sub=7), item(CHEST_HERB, 'Bruiseweed', sub=9),
                   item(ODD, 'Frostsaber Leather', sub=6), item(VEST, 'Rugged Vest', cls=4, sell=50),
                   item(COAL, 'Coal', sub=7, buy=500), item(STEEL, 'Steel Bar', sub=7),
                   item(SANSAM, 'Golden Sansam', sub=9), item(WOOL, 'Wool Cloth', sub=5)):
            w.gamedata.items[it.id] = it
        w.gamedata.recipes = [
            Recipe(spell_id=600, name='Smelt Copper', profession='Mining', skill_line=186, product_id=BAR,
                   product_count=1, reagents=[(ORE, 1)], trivial_low=25, trivial_high=50, min_rank=1),
            Recipe(spell_id=601, name='Smelt Steel', profession='Mining', skill_line=186, product_id=STEEL,
                   product_count=1, reagents=[(BAR, 1), (COAL, 1)], trivial_low=25, trivial_high=50, min_rank=1),
            Recipe(spell_id=602, name='Cured Rugged Hide', profession='Leatherworking', skill_line=165,
                   product_id=CURED, product_count=1, reagents=[(HIDE, 1)], trivial_low=250, trivial_high=260,
                   min_rank=1),
            Recipe(spell_id=603, name='Rugged Vest', profession='Leatherworking', skill_line=165, product_id=VEST,
                   product_count=1, reagents=[(HIDE, 1), (FEATHER, 1), (CURED, 1), (ODD, 1), (WOOL, 1)], trivial_low=280,
                   trivial_high=300, min_rank=1)]
        w.skillup.thresholds[603] = [250, 280, 290, 300]
        w.questie.items.update({HERB: {'objectDrops': [900]}, ORE: {'objectDrops': [901]},
                                CHEST_HERB: {'objectDrops': [902]}, FEATHER: {'npcDrops': [5]},
                                COAL: {'vendors': [100]}})
        w.questie.objects.update({900: {'name': 'Peacebloom'}, 901: {'name': 'Copper Vein'},
                                  902: {'name': 'Battered Chest'}})
        # Wowhead Forever "Skinned from": sheep give Wool Cloth too
        w.forever_skinning = {'items': {str(HIDE): {'npcs': []}, str(WOOL): {'npcs': []}}, 'not_read': {}}
        w.gatherlite = {'types': {900: 'herb', 902: 'container', 903: 'herb'},     # 901 has no type: an ore node by its name
                        'names': {900: 'peacebloom', 902: 'battered_chest', 903: 'golden_sansam'}}
        e = Engine(w, dict(SETTINGS, professions={'Leatherworking': 250, 'Skinning': 250}))
        # Steel: your bar plus vendor Coal. Golden Sansam: QuestieDB lists only chests, GatherLite has its node
        self.assertEqual(e.gathered(), {HIDE: {'Skinning'}, HERB: {'Herbalism'}, ORE: {'Mining'}, BAR: {'Mining'},
                                        STEEL: {'Mining'}, SANSAM: {'Herbalism'}, WOOL: {'Skinning'}})
        prices = {m: {'numAuctions': 3, 'minBuyout': 100, 'marketValue': 100, 'regionSoldPerDay': 5}
                  for m in (HIDE, FEATHER, CURED, ODD, WOOL)}
        w.prices = prices
        e = Engine(w, dict(SETTINGS, professions={'Leatherworking': 250, 'Skinning': 250}))
        out = e.levelling('Leatherworking', 250, known={603}, target=255)
        own = {m['name']: m['own'] for m in out['steps'][0]['mats']}
        # cloth everyone farms from mobs: not "yours" because a skinner gets a little from sheep
        self.assertEqual(own, {'Rugged Hide': True, 'Ironfeather': False, 'Cured Rugged Hide': False,
                               'Frostsaber Leather': False, 'Wool Cloth': False})
        self.assertEqual(out['own_materials'], ['Skinning'])
        # "Farm" rows: mobs drop Ironfeather (no profession needed); no data at all: the item's kind, as before
        self.assertIsNone(e.gather_profession(FEATHER, w.gamedata.items[FEATHER]))
        self.assertEqual(e.gather_profession(ODD, w.gamedata.items[ODD]), 'Skinning')
        self.assertEqual(e.gather_profession(HERB, w.gamedata.items[HERB]), 'Herbalism')
        self.assertIsNone(e.gather_profession(WOOL, w.gamedata.items[WOOL]))
        # a herb only chests drop: not gathered as far as the data says; no mob drops it either, so the guess stays
        self.assertEqual(e.gather_profession(CHEST_HERB, w.gamedata.items[CHEST_HERB]), 'Herbalism')

    def test_a_pattern_no_one_is_selling_now_may_take_a_wait(self):
        from tests.test_engine import MAT_VENDOR, PRODUCT, SETTINGS, item, make_world
        from wfm.engine import Engine
        from wfm.gamedata import Recipe
        LISTED, UNLISTED = 40, 41
        a = Recipe(spell_id=700, name='Dish A', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        b = Recipe(spell_id=701, name='Dish B', profession='Cooking', skill_line=185, product_id=PRODUCT,
                   product_count=1, reagents=[(MAT_VENDOR, 1)], trivial_low=140, trivial_high=180, min_rank=1)
        w = make_world({LISTED: {'numAuctions': 2, 'minBuyout': 300, 'marketValue': 300},
                        UNLISTED: {'numAuctions': 0, 'marketValue': 400}}, [a, b])
        for it in (item(LISTED, 'Recipe: Dish A', cls=9), item(UNLISTED, 'Recipe: Dish B', cls=9)):
            w.gamedata.items[it.id] = it
        w.skillup.thresholds.update({700: [100, 140, 160, 180], 701: [100, 140, 160, 180]})
        e = Engine(w, dict(SETTINGS))
        e._spell_to_recipe_items.update({700: [LISTED], 701: [UNLISTED]})
        self.assertFalse(e.learn_cost(a)['wait'])
        self.assertEqual(e.learn_cost(b)['source'], 'market value (none listed now)')
        self.assertTrue(e.learn_cost(b)['wait'])
        # the path takes the cheaper, listed one: nothing to wait for; with only B, the step and the list say so
        self.assertEqual(e.levelling('Cooking', 100, target=110)['to_wait'], [])
        w.gamedata.recipes = [b]
        e = Engine(w, dict(SETTINGS))
        e._spell_to_recipe_items.update({701: [UNLISTED]})
        out = e.levelling('Cooking', 100, target=110)
        self.assertTrue(out['steps'][0]['learn_wait'])
        self.assertEqual(out['steps'][0]['learn'], 400)              # the price still counts
        self.assertEqual(out['to_wait'], [{'spell_id': 701, 'recipe': 'Dish B', 'from': 100}])
        # a recipe you know: nothing to buy, nothing to wait for
        self.assertEqual(e.levelling('Cooking', 100, known={701}, target=110)['to_wait'], [])


class GatherLiteTypesTests(unittest.TestCase):
    def test_node_types_from_insert_object_lines(self):
        from wfm.gatherlite import node_key, parse_nodes, parse_types
        text = '''InsertObject("ore", { 1731, 2055, 3763 }, "copper_vein", "Ore\\\\copper", { 1, 25, 50, 100 })
-- Herbs
InsertObject("herb", { 1617 }, "silverleaf", "Herb\\\\silverleaf", { 1, 25, 50, 100 }, { "stunted_silverleaf" })
InsertObject("container", { 2843, 1731 }, "battered_chest", "Container\\\\chest", { 0 })'''
        self.assertEqual(parse_types(text), {1731: 'ore', 2055: 'ore', 3763: 'ore', 1617: 'herb', 2843: 'container'})
        self.assertEqual(parse_nodes(text)[1617], ('herb', 'silverleaf'))
        self.assertEqual([node_key(n) for n in ("Khadgar's Whisker", 'Golden Sansam', "Arthas' Tears")],
                         ['khadgars_whisker', 'golden_sansam', 'arthas_tears'])


if __name__ == '__main__':
    unittest.main()
