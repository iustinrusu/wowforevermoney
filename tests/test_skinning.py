import unittest

from wfm import skinning

SNAP = {'items': {
    '2318': {'name': 'Light Leather', 'npcs': [
        {'npc': 1, 'name': 'Boar', 'count': 70, 'outof': 100, 'min_level': 16, 'max_level': 17, 'zones': [44, 40]},
        {'npc': 2, 'name': 'Raptor', 'count': 10, 'outof': 400, 'min_level': 30, 'max_level': 31, 'zones': [-3, 11]}]},
    '2319': {'name': 'Medium Leather', 'npcs': [
        {'npc': 2, 'name': 'Raptor', 'count': 300, 'outof': 400, 'min_level': 30, 'max_level': 31, 'zones': [-3, 11]},
        {'npc': 3, 'name': 'Yeti', 'count': 50, 'outof': 60, 'min_level': 50, 'max_level': 52, 'zones': [11]}]},
}}
VALUE = {2318: 600, 2319: 1000}


class Rules(unittest.TestCase):
    def test_classic_skill_rule(self):
        self.assertEqual([skinning.skill_needed(l) for l in (5, 10, 15, 20, 21, 42, 60)], [1, 1, 50, 100, 105, 210, 300])

    def test_mob_table_merges_items_per_npc(self):
        m = skinning.mobs(SNAP)
        self.assertEqual(m[2]['skinned'], 400)
        self.assertEqual(m[2]['items'], {2318: 0.025, 2319: 0.75})
        self.assertEqual(m[1]['items'], {2318: 0.7})

    def test_measured_pace_needs_ten_minutes(self):
        self.assertEqual(skinning.measured_pace({'Dustwallow Marsh': {'skinning': {'loots': 42, 'seconds': 1110}}})[0],
                         42 / (1110 / 3600))
        self.assertIsNone(skinning.measured_pace({'X': {'skinning': {'loots': 10, 'seconds': 300}}})[0])
        self.assertIsNone(skinning.measured_pace({})[0])


class Spots(unittest.TestCase):
    def spots(self, skill, level):
        return {s['zone_id']: s for s in skinning.spots(skinning.mobs(SNAP), lambda i, share=1.0: VALUE.get(i), lambda z: f'Z{z}', skill, level)}

    def test_value_per_skin_and_zones(self):
        s = self.spots(skill=275, level=42)
        self.assertEqual(s[44]['value'], 420)                      # 70% x 6s
        self.assertTrue(s[44]['doable'])
        # zone 11 (negative ids are skipped): raptor 0.025x600 + 0.75x1000 = 765; the yeti is too high to kill
        self.assertEqual(s[11]['value'], 765)
        self.assertEqual({m['name']: m['can_kill'] for m in s[11]['mobs']}, {'Yeti': False, 'Raptor': True})

    def test_weighted_by_how_often_mobs_were_skinned(self):
        s = self.spots(skill=300, level=60)                        # both mobs in zone 11 usable now
        yeti = 50 / 60 * 1000
        expected = (765 * 400 + int(yeti) * 60) / 460
        self.assertEqual(s[11]['value'], int(expected))

    def test_not_doable_without_skill(self):
        s = self.spots(skill=None, level=42)
        self.assertFalse(s[44]['doable'])
        self.assertEqual(self.spots(skill=50, level=42)[44]['skill_needed'], 70)      # level 17: (17-10) x 10


if __name__ == '__main__':
    unittest.main()
