"""Profession advisor: what each profession shows now and at full skill, from hand-made rows."""
import unittest
from types import SimpleNamespace

from wfm import advisor


def row(kind, title, gph=None, daily=0, prof=None, doable=True, needs='', flags=(), full=None):
    return SimpleNamespace(kind=kind, title=title, key=title, gph=gph, daily=daily, profession=prof, doable=doable,
                           needs=needs, flags=list(flags), detail={'daily_if_affordable': full if full is not None else daily})


class FakeEngine:
    def levelling(self, prof, skill, known=None, crafts=None):
        return {'total': 50000 if skill < 100 else -2000, 'crafts': 300, 'reached': 300, 'stuck_at': None,
                'learn_total': 0}


OPPS = [
    row('skin_spot', 'Skin in Barrens', gph=20000, prof='Skinning'),
    row('skin_spot', 'Skin in Badlands', gph=50000, prof='Skinning', doable=False, needs='Skinning 250 (you have 200)'),
    row('skin_spot', 'Skin in Winterspring', gph=90000, prof='Skinning', doable=False, needs='level 55+ (you are 42)'),
    row('skin_spot', 'Skin somewhere', gph=99000, prof='Skinning', flags=['small_sample']),
    row('mine_spot', 'Mine in Winterspring', gph=300000, prof='Mining', doable=False, needs='Learn Mining',
        flags=['classic_yields']),
    row('craft', 'Craft A', daily=3000, prof='Leatherworking'),
    row('craft', 'Craft B', daily=1000, prof='Leatherworking'),
    row('craft', 'Craft C', daily=0, prof='Leatherworking', doable=False, full=9000),
    row('craft', 'Craft Junk', daily=99999, prof='Leatherworking', flags=['hard_to_sell']),
    row('craft', 'Craft Pots', daily=0, prof='Alchemy', doable=False, full=20000),
    row('craft', 'Transmute A', daily=0, prof='Alchemy', doable=False, full=15000),
    row('craft', 'Transmute B', daily=0, prof='Alchemy', doable=False, full=12000),
]
OPPS[-2].detail['cooldown_group'] = OPPS[-1].detail['cooldown_group'] = 'Transmute - Alchemy'


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        out = advisor.build(FakeEngine(), OPPS, {'Skinning': 200, 'Leatherworking': 150})
        self.rows = {r['profession']: r for r in out['rows']}
        self.order = [r['profession'] for r in out['rows']]

    def test_gathering_now_and_full_skill(self):
        g = self.rows['Skinning']['gather']
        self.assertEqual(g['now']['gph'], 20000)                 # doable today
        self.assertEqual(g['full']['gph'], 50000)                # needs skill only; the level-55 zone and the small
        self.assertIn('2g 0s 0c an hour now; up to 5g 0s 0c', self.rows['Skinning']['verdict'])   # sample are left out

    def test_classic_only_gathering_is_labelled(self):
        m = self.rows['Mining']
        self.assertIsNone(m['gather']['full'])
        self.assertEqual(m['gather']['classic_full']['gph'], 300000)
        self.assertIn('WoW Classic', m['verdict'])

    def test_crafting_now_and_at_300_and_the_levelling_cost(self):
        lw = self.rows['Leatherworking']['craft']
        self.assertEqual(lw['now_daily'], 4000)                  # A + B; the hard-to-sell craft never counts
        self.assertEqual(lw['full_daily'], 9000 + 3000 + 1000)   # C once you have the skill, then A and B
        self.assertEqual(self.rows['Leatherworking']['levelling']['total'], -2000)
        self.assertIn('earns about', self.rows['Leatherworking']['verdict'])
        self.assertEqual(self.rows['Alchemy']['levelling']['total'], 50000)   # from skill 1
        self.assertNotIn('levelling', self.rows['Enchanting'])                 # enchantments: no path

    def test_a_shared_cooldown_counts_once(self):
        self.assertEqual(self.rows['Alchemy']['craft']['full_daily'], 20000 + 15000)    # not + 12000 as well

    def test_yours_first(self):
        self.assertEqual(set(self.order[:2]), {'Skinning', 'Leatherworking'})


if __name__ == '__main__':
    unittest.main()
