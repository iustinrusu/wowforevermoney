"""Classic fishing tables (cMaNGOS) and the Forever blend, checked against hand-worked numbers."""
import gzip
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from wfm import classicdb, fishing
from wfm.classicdb import ClassicFishing, expected_items, extract, parse_tuples, success_chance
from wfm.engine import Engine
from wfm.gamedata import GameData, Item
from wfm.questie import QuestieDB
from wfm.skillup import SkillUpData

A, B, J, N, P, Q, W, Z = 11, 12, 13, 14, 15, 16, 17, 18     # yellowtail, eel, boot, Forever fish, trunk, quest, squid, deep fish


def e(item, chance, group=0, minref=1, maxcount=1, cond=0):
    return {'item': item, 'chance': chance, 'group': group, 'minref': minref, 'maxcount': maxcount, 'condition': cond,
            'comment': ''}


class SqlTests(unittest.TestCase):
    def test_parse_tuples(self):
        rows = list(parse_tuples(r"VALUES (1,-2.5,'it\'s (fine)',NULL),(2,3e2,'a\\b',0);", 6))
        self.assertEqual(rows, [[1, -2.5, "it's (fine)", None], [2, 300.0, 'a\\b', 0]])

    def test_extract_applies_updates_and_keeps_only_fishing(self):
        dump = '\n'.join([
            "INSERT INTO `fishing_loot_template` VALUES (440,11000,100,1,-11000,1,0,'Tanaris'),(38,6317,25,0,1,1,0,'Loch');",
            "INSERT INTO `reference_loot_template` VALUES (11000,11,60,1,1,1,0,'Yellowtail'),(11000,13,0,1,1,1,0,'Boot'),"
            "(11000,77,5,0,-12000,1,0,'nested'),(12000,12,100,0,1,1,5,'Eel'),(99999,1,1,0,1,1,0,'unrelated');",
            "INSERT INTO `skill_fishing_base_level` VALUES (440,205),(16,330),(38,-20);",
            "INSERT INTO `conditions` VALUES (5,12,35,0,0,0,0,'Event 35'),(6,2,1,1,0,0,0,'unused');",
            "INSERT INTO `game_event` VALUES (35,1,525600,256320,0,0,'Winter Season Fishing'),(36,1,525600,269280,0,0,'Summer');",
            "INSERT INTO `game_event_time` VALUES (35,'2010-09-23 01:00:00','2030-12-31 22:59:59');",
            "INSERT INTO `gameobject_template` VALUES (180685,25,1,'Floating Wreckage',0,0,0,1,4,17518,2,4"
            + ',0' * 20 + ",0,0,0,0,''),(31,2,6,'Old Lion Statue',84,4,0,0.63,43,73,0,0" + ',0' * 20 + ",0,0,0,0,''),"
            "(180184,25,1,'School of Fish',0,0,0,1,3,1415,10,0" + ',0' * 20 + ",0,0,0,0,'');",
            "INSERT INTO `gameobject_loot_template` VALUES (17518,15,60,1,1,1,0,'Trunk'),(1415,2447,100,0,1,3,0,'Peacebloom'),"
            "(73,1,100,0,1,1,0,'statue loot');",
        ])
        update = ("-- comment ; with a semicolon\nDELETE FROM `skill_fishing_base_level` WHERE `entry` IN (16, 38);\n"
                  "INSERT INTO `skill_fishing_base_level` (`entry`, `skill`) VALUES\n(16, 205), -- Azshara\n(1477, 205);\n"
                  "UPDATE `fishing_loot_template` SET `chance`=1 WHERE `entry`=440;\n")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'dump.sql.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as fh:
                fh.write(dump)
            up = Path(d) / '0001_fish.sql'
            up.write_text(update, encoding='utf-8')
            cf = extract(path, [up])
        self.assertEqual(cf.skill, {440: 205, 16: 205, 1477: 205}, 'update deleted 38, replaced 16, added 1477')
        self.assertEqual(sorted(cf.refs), [11000, 12000], 'only references fishing reaches, nested included')
        self.assertEqual(list(cf.pools), [180685], 'type-25 objects with catches only')
        self.assertEqual(cf.pools[180685]['restock'], [2, 4])
        self.assertEqual(list(cf.conditions), [5])
        self.assertEqual(cf.events[35]['start'], '2010-09-23 01:00:00')
        self.assertEqual(cf.source['updates'], ['0001_fish.sql'])
        self.assertEqual(len(cf.warnings), 1, 'the UPDATE statement is reported, not silently ignored')
        exp = expected_items(cf.loot[440], cf.refs)
        self.assertAlmostEqual(exp[11]['count'], 0.60)
        self.assertAlmostEqual(exp[13]['count'], 0.40)
        self.assertAlmostEqual(exp[12]['count'], 0.05)
        self.assertEqual(exp[12]['conditions'], {5})


class LootMathTests(unittest.TestCase):
    def test_groups_references_and_quest_items(self):
        refs = {7: [e(Z, 50, 1), e(J, 0, 1)]}
        entries = [e(A, 30, 1), e(B, 20, 1), e(J, 0, 1), e(N, 0, 1),     # equal-chance entries share the 50% left
                   e(Q, -100), e(0, 10, 0, minref=-7, maxcount=2),         # quest item; reference rolled twice
                   e(P, 50, 0, minref=2, maxcount=4)]                       # 2-4 of them, half the time
        exp = expected_items(entries, refs)
        self.assertAlmostEqual(exp[A]['count'], 0.30)
        self.assertAlmostEqual(exp[N]['count'], 0.25)
        self.assertAlmostEqual(exp[J]['count'], 0.25 + 0.10 * 2 * 0.5)
        self.assertAlmostEqual(exp[Z]['count'], 0.10 * 2 * 0.5)
        self.assertTrue(exp[Q]['quest'])
        self.assertAlmostEqual(exp[P]['count'], 0.5 * 3)

    def test_overfull_group_is_scaled(self):
        exp = expected_items([e(A, 80, 1), e(B, 70, 1)], {})
        self.assertAlmostEqual(exp[A]['count'] + exp[B]['count'], 1.0)

    def test_classic_getaway_formula(self):
        # mangos-classic GameObject.cpp: success if skill >= zone skill and roll(1-100) <= skill - zone skill + 5
        self.assertAlmostEqual(success_chance(225, 205), 0.25)
        self.assertEqual(success_chance(225, 130), 1.0)
        self.assertEqual(success_chance(200, 205), 0.0)

    def test_seasons_follow_the_classic_schedule(self):
        cf = ClassicFishing(events={35: {'name': 'Winter Season Fishing', 'occurence': 525600, 'length': 256320,
                                         'start': '2010-09-23 01:00:00'}})
        nov = time.mktime(time.strptime('2026-11-13', '%Y-%m-%d'))
        jun = time.mktime(time.strptime('2026-06-01', '%Y-%m-%d'))
        self.assertTrue(cf.event_status(35, nov)[0])
        self.assertFalse(cf.event_status(35, jun)[0])
        self.assertAlmostEqual(cf.event_status(35, nov)[1], 256320 / 525600)
        self.assertEqual(cf.event_status(99, nov), (None, 0.5))


def world(angler=None, activity=None, wowhead=None):
    gd = GameData(build='test')
    for iid, name, sell in [(A, 'Raw Spotted Yellowtail', 100), (B, 'Stonescale Eel', 400), (J, 'Old Boot', 10),
                            (N, 'Forever Fish', 50), (P, 'Iron Bound Trunk', 300), (W, 'Raw Winter Squid', 200),
                            (Z, 'Deep Fish', 900)]:
        gd.items[iid] = Item(id=iid, name=name, quality=1, item_level=1, req_level=0, sell_price=sell, buy_price=0,
                             stack=20, class_id=7, subclass_id=8, bonding=0)
    gd.zones = {440: 'Tanaris', 1000: 'Steamwheedle Port', 1001: 'Lost Rigger Cove', 2000: 'Gadgetzan',
                357: 'Feralas', 1112: 'Jademir Lake', 618: 'Winterspring'}
    gd.zone_parent = {440: 0, 1000: 440, 1001: 440, 2000: 440, 357: 0, 1112: 357, 618: 0}
    gd.zone_continent = {k: 1 for k in gd.zones}
    cf = ClassicFishing(
        loot={440: [e(A, 60, 1), e(J, 0, 1)],          # inland: yellowtail 60%, boot 40%
              1000: [e(B, 50, 1), e(A, 0, 1)],         # coast: eel 50%, yellowtail 50%
              1001: [e(B, 50, 1), e(A, 0, 1)],         # same table -> same spot
              2000: [e(0, 10, 0, minref=-90)],         # stub: only a seasonal squid
              357: [e(A, 100, 1)],
              1112: [e(Z, 100, 1)],                    # a lake that needs 330
              618: [e(Z, 100, 1)]},
        refs={90: [e(W, 100, 0, cond=1)]},
        skill={440: 205, 1000: 205, 1001: 205, 357: 205, 1112: 330, 618: 330},
        conditions={1: {'type': 12, 'value1': 35, 'comment': ''}},
        events={35: {'name': 'Winter Season Fishing', 'occurence': 525600, 'length': 256320, 'start': '2010-09-23 01:00:00'}},
        pools={180685: {'name': 'Floating Wreckage', 'loot_id': 1, 'loot': [e(P, 60, 1), e(J, 0, 1)], 'restock': [2, 4]}})
    return SimpleNamespace(gamedata=gd, prices={}, questie=QuestieDB(), skillup=SkillUpData(), angler=angler,
                           classic_fishing=cf, forever_fishing=wowhead or {},
                           profile={'activity': activity or {}})


SETTINGS = {'gold': 1, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'min_sold_per_day': 0.5,
            'professions': {'Fishing': 225}, 'preferred': ['Fishing'], 'casts_per_hour': 200}
TANARIS_LOG = {'zones': {'Tanaris': {'c': 100, 'k': 60, 'e': 20, 'fish': {B: 30, A: 25, N: 3, P: 2}},
                         'Mulgore': {'c': 0, 'k': 0, 'e': 0, 'fish': []}}}


def spots_by_key(opps):
    return {o.key: o for o in opps}


class SpotTests(unittest.TestCase):
    def test_spots_group_subzones_with_the_same_table(self):
        gd = world().gamedata
        spots = fishing.build_spots(world().classic_fishing, gd, now=time.mktime(time.strptime('2026-11-13', '%Y-%m-%d')))
        tanaris = spots[440]
        self.assertEqual([s.areas for s in tanaris], [[440], [2000], [1000, 1001]])
        self.assertEqual(tanaris[0].label(True), 'Tanaris (rest of the zone)')
        self.assertEqual(tanaris[2].names, ['Lost Rigger Cove', 'Steamwheedle Port'])
        self.assertEqual(tanaris[2].label(True), 'Tanaris: Lost Rigger Cove +1 more')
        self.assertEqual(tanaris[1].skill, 205, 'subzone without its own skill uses the zone skill')
        self.assertAlmostEqual(tanaris[1].coverage, 0.10, msg='winter: squid in season')

    def test_blend_with_your_catches(self):
        opps = spots_by_key(Engine(world(TANARIS_LOG), dict(SETTINGS)).fishing_spots({}))
        coast = opps['fish:zone:440']
        self.assertEqual(coast.title, 'Fish in Tanaris')
        self.assertNotIn('fish:440:1000', opps, 'the matched Classic table is folded into the Forever row')
        # matched to the coast (explains 55 of 60 catches); w = 60 / (60 + 30) = 2/3
        d = coast.detail
        self.assertEqual(d['classic_spot'], 'Tanaris: Lost Rigger Cove +1 more')
        self.assertAlmostEqual(d['weight'], 0.667, places=3)
        value = 0.5 * 400 + (2 / 3 * 25 / 60 + 1 / 3 * 0.5) * 100 + (2 / 3 * 3 / 60) * 50 + (2 / 3 * 2 / 60) * 300
        self.assertEqual(coast.profit_unit, int(value))
        self.assertEqual(d['classic_value'], 250)
        self.assertEqual(d['observed_value'], int(0.5 * 400 + 25 / 60 * 100 + 3 / 60 * 50 + 2 / 60 * 300))
        # catches/hour = 200 casts x 80/100 landed x 60/80 kept here
        self.assertEqual(d['catches_per_hour'], 120)
        self.assertEqual(coast.gph, round(value * 120))
        self.assertEqual(d['keep_source'], 'your got-away rate here')
        self.assertEqual([f['item_id'] for f in d['new_in_forever']], [N], 'the trunk is pool loot, not new')
        self.assertIn('forever_change', coast.flags)
        self.assertNotIn('classic_unconfirmed', coast.flags)
        self.assertEqual(d['confirmed_by'], ['your catches'])

    def test_classic_only_spots_stay_out_of_top_picks(self):
        r = Engine(world(TANARIS_LOG), dict(SETTINGS)).run()
        opps = spots_by_key(r['opportunities'])
        inland = opps['fish:440:440']
        self.assertEqual(inland.title, 'Classic table: Tanaris (rest of the zone)')
        self.assertIn('classic_unconfirmed', inland.flags)
        self.assertEqual(inland.profit_unit, 64)                 # 60% x 100 + 40% x 10
        self.assertIn('fish:zone:440', r['top']['hourly'])
        self.assertNotIn('fish:440:440', r['top']['hourly'])

    def test_small_samples_stay_out_of_top_picks(self):
        # A dozen catches with a couple of lucky trunks can make a zone look 3x better than it is.
        log = {'zones': {'Tanaris': {'c': 20, 'k': 12, 'e': 0, 'fish': {B: 6, A: 6}}}}
        r = Engine(world(log), dict(SETTINGS)).run()
        row = spots_by_key(r['opportunities'])['fish:zone:440']
        self.assertEqual(row.detail['confirmed_by'], ['your catches'])
        self.assertIn('small_sample', row.flags)
        self.assertNotIn('fish:zone:440', r['top']['hourly'])

    def test_wowhead_forever_zone_counts(self):
        wh = {'Tanaris': {'fished': 100, 'items': {A: 70, J: 30}, 'checked': '2026-11-13', 'url': 'u'}}
        opps = spots_by_key(Engine(world(wowhead=wh), dict(SETTINGS)).fishing_spots({}))
        row = opps['fish:zone:440']
        self.assertEqual(row.detail['confirmed_by'], ['Wowhead Forever'])
        self.assertIn('wowhead_forever', row.flags)
        self.assertEqual(row.detail['classic_spot'], 'Tanaris (rest of the zone)', 'yellowtail + boot = the inland table')
        self.assertNotIn('fish:440:440', opps)
        self.assertIn('fish:440:1000', opps, 'the coast stays a Classic-only row')
        w = 100 / 130
        self.assertEqual(row.profit_unit, int((w * 0.7 + (1 - w) * 0.6) * 100 + (w * 0.3 + (1 - w) * 0.4) * 10))
        # Wowhead has no cast data: with no logs of your own, the got-away rate falls back to the Classic formula
        self.assertAlmostEqual(row.detail['keep'], 0.25)
        self.assertIn('classic_getaway', row.flags)
        self.assertEqual(row.detail['caught'], 0)
        self.assertEqual(row.detail['forever_catches'], 100)

    def test_got_away_rate_sources(self):
        opps = spots_by_key(Engine(world(TANARIS_LOG), dict(SETTINGS)).fishing_spots({}))
        feralas = opps['fish:357:357']                            # unvisited, same Classic zone skill as Tanaris
        self.assertAlmostEqual(feralas.detail['keep'], 0.75)
        self.assertIn('zone-skill 205', feralas.detail['keep_source'])
        winterspring = opps['fish:618:618']                       # 330 > 225: Classic says nothing bites
        self.assertFalse(winterspring.doable)
        self.assertIsNone(winterspring.gph)
        self.assertEqual(winterspring.needs, 'Fishing 330 (Classic zone skill)')
        self.assertIn('classic_getaway', winterspring.flags)
        self.assertEqual(winterspring.detail['gph_if_skilled'], int(900 * 200 * 0.8))

    def test_log_is_not_forced_onto_a_spot_that_does_not_explain_it(self):
        # Regression: a Feralas log of mostly pool loot plus a few lake fish was matched to a skill-330 lake,
        # whose Classic fish then looked catchable at 225 and topped the list.
        log = {'zones': {'Feralas': {'c': 40, 'k': 30, 'e': 1, 'fish': {P: 20, Z: 3, N: 5, A: 2}}}}
        opps = spots_by_key(Engine(world(log), dict(SETTINGS)).fishing_spots({}))
        mine = opps['fish:zone:357']
        self.assertEqual(mine.title, 'Fish in Feralas')
        self.assertIsNone(mine.detail['classic_spot'])
        self.assertEqual(mine.detail['weight'], 1.0)
        self.assertEqual([f['item_id'] for f in mine.detail['new_in_forever']], [N])
        lake = opps['fish:357:1112']
        self.assertFalse(lake.doable, 'your got-away rate in the zone does not carry over to a spot you never matched')
        self.assertEqual(lake.detail['caught'], 0)
        self.assertEqual(opps['fish:357:357'].detail['caught'], 0)

    def test_forever_only_zone_with_timed_log(self):
        activity = {'Riverglades': {'fishing': {'loots': 50, 'seconds': 1800, 'items': {N: 50}}}}
        o = spots_by_key(Engine(world(None, activity), dict(SETTINGS)).fishing_spots({}))['fish:log:Riverglades']
        self.assertIn('forever_only', o.flags)
        self.assertIn('measured', o.flags)
        self.assertEqual(o.profit_unit, 50)
        self.assertEqual(o.detail['catches_per_hour'], 100)
        self.assertEqual(o.gph, 5000)

    def test_two_addons_logging_the_same_catches_are_not_added(self):
        activity = {'Tanaris': {'fishing': {'loots': 70, 'seconds': 900, 'items': {B: 40, A: 30}}}}
        obs = fishing.observations(TANARIS_LOG, activity)['Tanaris']
        self.assertEqual(obs.caught, 70, 'the bigger log wins, never the sum')
        self.assertEqual(obs.items, {B: 40, A: 30})
        self.assertEqual((obs.casts, obs.escaped), (100, 20), 'casts and getaways still come from ForeverAngler')
        self.assertEqual(obs.sources, ['ForeverAngler', 'ForeverMoneyBridge'])


if __name__ == '__main__':
    unittest.main()
