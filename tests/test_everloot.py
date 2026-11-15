"""Everloot drop rates: the parser, and the cross-check against Wowhead Forever counts (hand-worked numbers)."""
import json
import tempfile
import unittest
from pathlib import Path

from wfm import audit, everloot

LINEN, WOOL, COPPER = 2589, 2592, 2770
THUG, BANDIT, VEIN = 100, 101, 1731


def page(rates, offset=0, total=None):
    return {'dataAsOf': '2026-11-15T00:00:14Z', 'offset': offset, 'limit': 500, 'total': total or len(rates),
            'rates': rates}


PAGES = {'items': {
    str(LINEN): {'name': 'Linen Cloth', 'read': '2026-11-14', 'tabs': {
        'dropped-by': {'kind': 'npc', 'rows': [{'id': THUG, 'count': 300, 'outof': 1000},
                                               {'id': BANDIT, 'count': 100, 'outof': 1000}]},
        'skinned-from': {'kind': 'npc', 'rows': [{'id': THUG, 'count': 5, 'outof': 50}]}}},
    str(COPPER): {'name': 'Copper Ore', 'read': '2026-11-14', 'tabs': {
        'mined-from-object': {'kind': 'object', 'rows': [{'id': VEIN, 'count': 965, 'outof': 1000}]},
        'fished-in': {'kind': 'zone', 'rows': [{'id': 40, 'count': 3, 'outof': 900}]}}}}}


class ParserTests(unittest.TestCase):
    def test_pages_are_merged_and_odd_rows_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'drops_1.json').write_text(json.dumps(page([
                {'sourceNpcId': THUG, 'itemId': LINEN, 'kills': 100, 'drops': 31, 'reporters': 4},
                {'sourceObjectId': VEIN, 'itemId': COPPER, 'kills': 181, 'drops': 181, 'reporters': 5},
                {'sourceNpcId': THUG, 'itemId': WOOL, 'kills': 10, 'drops': 11},          # more drops than loots
                {'itemId': WOOL, 'kills': 10, 'drops': 1}], total=5)), encoding='utf-8')  # no source
            Path(d, 'drops_2.json').write_text(json.dumps(page([
                {'sourceNpcId': BANDIT, 'itemId': LINEN, 'kills': 40, 'drops': 4, 'sourceName': 'Bandit'}], 500, 5)),
                encoding='utf-8')
            Path(d, 'other.json').write_text('{}', encoding='utf-8')                       # not a drops page
            ev = everloot.load(Path(d))
        self.assertEqual(len(ev['rates']), 3)
        self.assertEqual(ev['bad'], 2)
        self.assertEqual(ev['files'], ['drops_1.json', 'drops_2.json'])
        self.assertEqual((ev['as_of'], ev['total']), ('2026-11-15', 5))
        self.assertEqual(ev['rates'][('npc', THUG, LINEN)], {'looted': 100, 'count': 31, 'reporters': 4, 'name': ''})
        self.assertEqual(ev['rates'][('object', VEIN, COPPER)]['count'], 181)
        self.assertEqual(ev['rates'][('npc', BANDIT, LINEN)]['name'], 'Bandit')

    def test_no_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(everloot.load(Path(d))['rates'], {})


class CompareTests(unittest.TestCase):
    def test_wowhead_counts_prefer_dropped_by(self):
        wh = everloot.wowhead_counts(PAGES)
        self.assertEqual(wh[('npc', THUG, LINEN)]['tab'], 'dropped-by')     # not the skinned-from row
        self.assertEqual(wh[('npc', THUG, LINEN)]['outof'], 1000)
        self.assertEqual(wh[('object', VEIN, COPPER)]['count'], 965)
        self.assertNotIn(('zone', 40, COPPER), wh)                          # fishing zones are not comparable

    def test_z_score_by_hand(self):
        # 30% of 1000 vs 10% of 1000: pooled 20%, se = sqrt(0.2 x 0.8 x 2/1000) = 0.017889; gap 0.2 -> 11.18
        self.assertAlmostEqual(everloot.z_score(300, 1000, 100, 1000), 0.2 / (0.2 * 0.8 * 2 / 1000) ** 0.5)
        self.assertEqual(everloot.z_score(1, 0, 1, 10), 0.0)

    def test_verdicts(self):
        ev = {'rates': {
            ('npc', THUG, LINEN): {'looted': 100, 'count': 31, 'reporters': 4, 'name': ''},     # 31% vs 30%: agree
            ('npc', BANDIT, LINEN): {'looted': 400, 'count': 120, 'reporters': 9, 'name': ''},  # 30% vs 10%: a gap
            ('object', VEIN, COPPER): {'looted': 20, 'count': 20, 'reporters': 2, 'name': ''},  # 20 loots: too few
            ('npc', 999, WOOL): {'looted': 500, 'count': 50, 'reporters': 3, 'name': ''}}}      # not on Wowhead
        c = everloot.compare(ev, PAGES)
        self.assertEqual(c['counts'], {'agree': 1, 'gap': 1, 'small': 1})
        self.assertEqual(c['pairs'][0]['source'], BANDIT)                    # gaps first
        self.assertEqual(c['pairs'][0]['verdict'], 'gap')
        # a big ratio from a moderate sample is still "agree" when it is within the noise: 45% of 33 vs 30% of 1000
        noisy = {'rates': {('npc', THUG, LINEN): {'looted': 33, 'count': 15, 'reporters': 4, 'name': ''}}}
        self.assertEqual(everloot.compare(noisy, PAGES)['pairs'][0]['verdict'], 'agree')

    def test_data_health_entry(self):
        ev = {'rates': {('npc', BANDIT, LINEN): {'looted': 400, 'count': 120, 'reporters': 9, 'name': ''}},
              'as_of': '2026-11-15'}
        names = {LINEN: 'Linen Cloth'}
        c = audit.everloot_check(ev, PAGES, lambda i: names.get(i, f'item {i}'))
        self.assertEqual(c['status'], 'warn')
        self.assertIn('CC BY-SA 4.0', c['detail'])
        self.assertIn('not used in any number', c['detail'])
        self.assertTrue(c['examples'][0].startswith('Far apart: Linen Cloth from mob 101: Wowhead Forever 10.0% of '
                                                    '1,000 loots (dropped-by), Everloot 30.0% of 400 loot windows'))
        self.assertEqual(audit.everloot_check({}, PAGES, str)['status'], 'info')


class FillTests(unittest.TestCase):
    def test_gaps_only_from_big_samples_and_wowhead_wins(self):
        mobs = {THUG: {'id': THUG, 'name': 'Thug', 'looted': 1000, 'items': {LINEN: 0.3}, 'counts': {LINEN: (300, 1000)},
                       'read': '2026-11-14', 'complete': False, 'small_sample': False}}
        ev = {'rates': {('npc', THUG, LINEN): {'looted': 100, 'count': 90, 'reporters': 3, 'name': ''},   # Wowhead has it
                        ('npc', THUG, WOOL): {'looted': 40, 'count': 10, 'reporters': 3, 'name': ''},     # a gap: filled
                        ('npc', BANDIT, WOOL): {'looted': 29, 'count': 9, 'reporters': 3, 'name': ''},    # too few loots
                        ('npc', 999, WOOL): {'looted': 60, 'count': 6, 'reporters': 3, 'name': 'Ghoul'},  # Everloot only
                        ('object', VEIN, COPPER): {'looted': 99, 'count': 99, 'reporters': 3, 'name': ''}}}
        touched = everloot.fill_mob_gaps(mobs, ev)
        self.assertEqual(touched, {THUG, 999})
        self.assertEqual(mobs[THUG]['items'], {LINEN: 0.3, WOOL: 0.25})
        self.assertEqual(mobs[THUG]['everloot_items'], {WOOL})
        self.assertEqual(mobs[THUG]['looted'], 1000)
        self.assertNotIn(BANDIT, mobs)
        self.assertEqual((mobs[999]['items'], mobs[999]['looted'], mobs[999]['small_sample']), ({WOOL: 0.1}, 60, False))


if __name__ == '__main__':
    unittest.main()
