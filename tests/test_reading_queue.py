"""The Wowhead reading queue (the user, 2026-11-20: "start with reading high interest, high level items and mobs first"):
items and mobs together, by the gold a day the app can't see yet, high levels first. Hand-worked numbers."""
import unittest
from types import SimpleNamespace

from tests.test_engine import MAT_AH, SETTINGS, make_world
from wfm import coverage
from wfm.engine import Engine

OPEN, DUNGEON = 361, 2017                  # Felwood; Stratholme (map 329: a dungeon)
FARM, RARE, READ, SHOWN = 900, 901, 902, 903


def spawns(zone, n):
    return {zone: [[10.0 + i, 20.0] for i in range(n)]}


def engine():
    w = make_world({MAT_AH: {'numAuctions': 50, 'minBuyout': 1000, 'marketValue': 1000, 'regionSale': 1000,
                             'regionSoldPerDay': 500}})
    w.gamedata.items[MAT_AH].item_level = 60
    w.gamedata.zone_continent = {OPEN: 1, DUNGEON: 329}
    w.gamedata.zones = {OPEN: 'Felwood', DUNGEON: 'Stratholme'}
    for npc, name, n in ((FARM, 'Toxic Thing', 20), (RARE, 'Named Croc', 1), (READ, 'Read Already', 20),
                         (SHOWN, 'Partly Known', 20)):
        w.questie.npcs[npc] = {'name': name, 'minLevel': 59, 'maxLevel': 60, 'spawns': spawns(OPEN, n)}
    return Engine(w, dict(SETTINGS, level=60, kills_per_hour=60))


# each mob: 0.5 Raw Meat a kill (worth 950 after the cut, the AH takes 100 a day at 20%), level 60, typical health
CREATURES = {str(n): {'name': 'x', 'levels': [59, 60], 'type': 7, 'health': 3960, 'coins': 0, 'items': {str(MAT_AH): 0.5}}
             for n in (FARM, RARE, READ, SHOWN)}


class ReadingQueueTests(unittest.TestCase):
    def queue(self, items=()):
        e = engine()
        shown = SimpleNamespace(kind='mob_spot', gph=10000, detail={'npc': SHOWN})       # 1g an hour known now
        return coverage.reading_queue(e, [shown], CREATURES, {}, {READ}, list(items), 0.2)

    def test_mobs_by_gold_the_app_cant_see(self):
        q = self.queue()
        ids = [r['id'] for r in q]
        self.assertNotIn(READ, ids)            # its own page is read
        self.assertNotIn(RARE, ids)            # one spawn point: a rare or named mob, not a farm
        # an hour: 60 kills (typical health at 60) x 0.5 = 30 meat, all within the 100 a day the AH takes: 950 each
        farm = next(r for r in q if r['id'] == FARM)
        self.assertEqual(farm['gold'], 30 * 950)
        shown = next(r for r in q if r['id'] == SHOWN)
        self.assertEqual(shown['gold'], 30 * 950 - 10000)          # minus what Forever data shows already
        self.assertEqual(ids[:2], [FARM, SHOWN])
        self.assertIn('the WoW Classic table suggests about 2.9g an hour (mostly Raw Meat)', farm['text'])

    def test_items_by_your_share_of_the_trade_and_level(self):
        row = {'item_id': MAT_AH, 'name': 'Raw Meat', 'market': 400000, 'missing': ['drops'], 'url': 'u'}
        q = self.queue([row])
        item = next(r for r in q if r['kind'] == 'item')
        self.assertEqual(item['gold'], 80000)                       # 40g traded a day x 20%
        self.assertEqual(item['score'], 80000 * 1.0)                # item level 60: in full
        self.assertEqual(q[0]['kind'], 'item')                      # 8g a day beats the mobs' 2.9g

    def test_level_weight(self):
        self.assertEqual(coverage.level_weight(60), 1.0)
        self.assertEqual(coverage.level_weight(30), 0.5)
        self.assertEqual(coverage.level_weight(5), 0.2)
        self.assertEqual(coverage.level_weight(70), 1.0)

    def test_dungeon_only_items_wait_for_the_dungeons_view(self):
        e = engine()
        e.q.npcs[950] = {'name': 'Boss', 'spawns': spawns(DUNGEON, 1)}
        e.q.items[MAT_AH] = {'npcDrops': [950]}
        self.assertTrue(coverage.dungeon_only(e, MAT_AH))
        e.q.npcs[951] = {'name': 'Outside', 'spawns': spawns(OPEN, 3)}
        e.q.items[MAT_AH] = {'npcDrops': [950, 951]}
        self.assertFalse(coverage.dungeon_only(e, MAT_AH))

    def test_data_health_entry(self):
        entry = coverage.queue_check(self.queue(), 60)
        self.assertEqual(entry['name'], 'Wowhead reading queue')
        self.assertTrue(entry['examples'][0].startswith('Mob: Toxic Thing (npc 900, level 59-60, Felwood)'))
        self.assertIn('https://www.wowhead.com/forever/npc=900', entry['examples'][0])


if __name__ == '__main__':
    unittest.main()
