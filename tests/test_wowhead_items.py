"""Wowhead Forever pages read by hand (wfm/wowhead_items.py), node yields from them (nodes.combine), coverage, and
the importer for pages read out of the Wowhead tab. Names and numbers are made up; rates are worked out by hand."""
import json
import tempfile
import unittest
from pathlib import Path

from wfm import coverage, nodes, wowhead_items as wi

RUNE, CLOTH, ORE, STONE, GEM, HIDE = 20520, 4338, 3858, 7912, 1705, 4235
VEIN, POOL = 2040, 180682
MOB_A, MOB_B = 10901, 4825


def row(i, count, outof, **kw):
    return {'id': i, 'count': count, 'outof': outof, **kw}


def page(name, tabs, read='2026-11-14', url=None):
    return {'name': name, 'url': url or 'https://www.wowhead.com/forever/item=1', 'read': read, 'tabs': tabs}


def cloth_page(read='2026-11-14'):
    return page('Mageweave Cloth', {
        'dropped-by': {'kind': 'npc', 'total': 5, 'classic': 1, 'rows': [
            row(MOB_A, 30, 100, name='Mob A', minlevel=40, maxlevel=41, location=[33], stack={'1': 75, '2': 25}),
            row(MOB_B, 4, 40, name='Mob B', location=[17]),
            row(99, 2, 6, name='Barely seen')]},                       # 6 loots: left out
        'comments': {'rows': [{'id': 1}]},                                # not a source tab
    }, read=read)


class CleanAndMergeTests(unittest.TestCase):
    def test_keeps_source_tabs_and_drops_tiny_samples(self):
        data, saved, problems = wi.merge({}, {str(CLOTH): cloth_page()})
        self.assertEqual((saved, problems), ([f'item={CLOTH}'], []))
        tab = data['items'][str(CLOTH)]['tabs']['dropped-by']
        self.assertEqual([r['id'] for r in tab['rows']], [MOB_A, MOB_B])  # most looted first
        self.assertEqual((tab['total'], tab['classic'], tab['small']), (5, 1, 1))
        self.assertNotIn('comments', data['items'][str(CLOTH)]['tabs'])

    def test_old_pages_without_kind_use_the_tab_name(self):
        p = page('Heavy Hide', {'skinned-from': {'total': 1, 'classic': 0, 'rows': [row(MOB_A, 5, 50)]}})
        data, _, _ = wi.merge({}, {str(HIDE): p})
        self.assertEqual(data['items'][str(HIDE)]['tabs']['skinned-from']['kind'], 'npc')

    def test_a_bad_field_skips_the_whole_page(self):
        bad = cloth_page()
        bad['tabs']['dropped-by']['rows'][0]['count'] = '30'
        for key, p in ((str(CLOTH), bad), ('item=7', page('X', {}, url='https://evil.example/x')),
                       ('spell=5', page('X', {})), (str(RUNE), {**page('X', {}), 'read': 'today'})):
            data, saved, problems = wi.merge({}, {key: p})
            self.assertEqual(saved, [], key)
            self.assertEqual(len(problems), 1, key)

    def test_a_newer_read_is_never_replaced_by_an_older_one(self):
        data, _, _ = wi.merge({}, {str(CLOTH): cloth_page('2026-11-14')})
        data, saved, problems = wi.merge(data, {f'item={CLOTH}': cloth_page('2026-11-01')})
        self.assertEqual(saved, [])
        self.assertIn('newer read', problems[0])
        data, saved, _ = wi.merge(data, {str(CLOTH): cloth_page('2026-11-20')})
        self.assertEqual(data['items'][str(CLOTH)]['read'], '2026-11-20')

    def test_object_and_npc_pages_have_their_own_sections(self):
        data, saved, _ = wi.merge({}, {f'object={VEIN}': page('Mithril Deposit', {'contains': {'kind': 'item', 'rows': [
            row(ORE, 90, 100)]}}), f'npc={MOB_A}': page('Mob A', {'drops': {'kind': 'item', 'rows': [row(CLOTH, 30, 100)]}})})
        self.assertEqual(sorted(saved), [f'npc={MOB_A}', f'object={VEIN}'])
        self.assertEqual((wi.page_ids(data, 'objects'), wi.page_ids(data, 'npcs'), wi.page_ids(data)), ({VEIN}, {MOB_A}, set()))

    def test_save_and_load_round_trip(self):
        data, _, _ = wi.merge({}, {str(CLOTH): cloth_page(), f'object={VEIN}': page('Vein', {'contains': {
            'kind': 'item', 'rows': []}})})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'pages.json'
            wi.save(data, path)
            back = wi.load(path)
            self.assertEqual(back['items'], data['items'])
            self.assertEqual(back['objects'], data['objects'])
            self.assertIn('Classic Era', back['_about'])


class TableTests(unittest.TestCase):
    def setUp(self):
        self.data, _, _ = wi.merge({}, {
            str(CLOTH): cloth_page(),
            str(ORE): page('Mithril Ore', {'mined-from-object': {'kind': 'object', 'rows': [row(VEIN, 160, 200, name='Mithril Deposit')]}}),
            str(STONE): page('Solid Stone', {'mined-from-object': {'kind': 'object', 'rows': [row(VEIN, 50, 200, stack={'1': 50, '3': 50})]}}),
        })

    def test_mob_drops_per_kill(self):
        mobs = wi.mob_drops(self.data)
        # 30 of 100 loots had it; stacks of 1 (75%) and 2 (25%) -> 1.25 each: 0.3 x 1.25 = 0.375 per kill
        self.assertAlmostEqual(mobs[MOB_A]['items'][CLOTH], 0.375)
        self.assertEqual((mobs[MOB_A]['looted'], mobs[MOB_A]['small_sample'], mobs[MOB_A]['zones']), (100, False, [33]))
        self.assertAlmostEqual(mobs[MOB_B]['items'][CLOTH], 0.1)
        self.assertTrue(mobs[MOB_B]['small_sample'])                   # 40 loots < 50
        self.assertFalse(mobs[MOB_A]['complete'])

    def test_object_yields_from_item_pages(self):
        vein = wi.object_yields(self.data)[VEIN]
        self.assertAlmostEqual(vein['items'][ORE], 0.8)                 # 160 / 200
        self.assertAlmostEqual(vein['items'][STONE], 0.5)               # 50 / 200 x average stack 2
        self.assertFalse(vein['complete'])

    def test_a_node_page_replaces_what_item_pages_said(self):
        data, _, _ = wi.merge(self.data, {f'object={VEIN}': page('Mithril Deposit', {'contains': {'kind': 'item', 'rows': [
            row(ORE, 290, 300), row(GEM, 6, 300)]}})})
        vein = wi.object_yields(data)[VEIN]
        self.assertTrue(vein['complete'])
        self.assertEqual(set(vein['items']), {ORE, GEM})               # the stone rows from item pages are gone
        self.assertEqual(vein['looted'], 300)
        self.assertEqual(wi.covered_by_objects(data), {ORE, GEM})

    def test_skinning_rows_join_the_skinning_snapshot(self):
        data, _, _ = wi.merge({}, {str(HIDE): page('Heavy Hide', {'skinned-from': {'kind': 'npc', 'rows': [
            row(MOB_A, 20, 400, name='Mob A', minlevel=30, maxlevel=31, location=[400])]}})})
        snap = {'items': {'783': {'name': 'Light Hide', 'npcs': []}}, 'not_read': {str(HIDE): 'Heavy Hide', '8167': 'Turtle Scale'}}
        out = wi.merge_skinning(snap, data)
        self.assertEqual(set(out['items']), {'783', str(HIDE)})
        self.assertEqual(out['not_read'], {'8167': 'Turtle Scale'})
        self.assertEqual(out['items'][str(HIDE)]['npcs'][0], {'npc': MOB_A, 'name': 'Mob A', 'count': 20, 'outof': 400,
                                                               'min_level': 30, 'max_level': 31, 'zones': [400]})
        self.assertEqual(snap['not_read'], {str(HIDE): 'Heavy Hide', '8167': 'Turtle Scale'}, 'input left alone')

    def test_skinning_rows_are_combined_mob_by_mob(self):
        data, _, _ = wi.merge({}, {str(HIDE): page('Heavy Hide', {'skinned-from': {'kind': 'npc', 'rows': [
            row(MOB_A, 25, 500), row(99, 3, 30)]}}, read='2026-11-14')})
        snap = {'items': {str(HIDE): {'name': 'Heavy Hide', 'checked': '2026-11-13', 'npcs': [
            {'npc': MOB_A, 'name': 'Mob A', 'count': 20, 'outof': 400, 'min_level': 30, 'max_level': 31, 'zones': [400]},
            {'npc': MOB_B, 'name': 'Mob B', 'count': 9, 'outof': 300, 'min_level': 30, 'max_level': 31, 'zones': [400]}]}}}
        npcs = {r['npc']: r for r in wi.merge_skinning(snap, data)['items'][str(HIDE)]['npcs']}
        self.assertEqual(set(npcs), {MOB_A, MOB_B, 99})                 # nothing lost
        self.assertEqual((npcs[MOB_A]['count'], npcs[MOB_A]['outof']), (25, 500))   # the newer read wins


class NodeCombineTests(unittest.TestCase):
    def test_forever_replaces_classic_item_by_item(self):
        classic = {ORE: 2.4, STONE: 0.9, GEM: 0.06}
        items, src = nodes.combine(classic, {'items': {ORE: 0.8}, 'complete': False}, 3.0, ORE)
        self.assertAlmostEqual(items[ORE], 2.4)                         # 0.8 per gather x 3 gathers (Classic)
        self.assertEqual(src, {ORE: 'forever', STONE: 'classic', GEM: 'classic'})

    def test_a_complete_node_page_drops_the_classic_table(self):
        items, src = nodes.combine({ORE: 2.4, STONE: 0.9}, {'items': {ORE: 0.9, GEM: 0.02}, 'complete': True}, 2.0, ORE)
        self.assertEqual(set(items), {ORE, GEM})
        self.assertAlmostEqual(items[GEM], 0.04)
        self.assertEqual(set(src.values()), {'forever'})

    def test_nothing_known_counts_one_of_its_herb_or_ore(self):
        self.assertEqual(nodes.combine({}, None, 1.0, ORE), ({ORE: 1.0}, {ORE: 'assumed'}))


class MobFarmingTests(unittest.TestCase):
    """Engine.mob_spots: one row per mob from "Dropped by" counts, plus a skin you can take; kills/hour from Settings."""

    def world(self):
        from tests.test_engine import item, make_world
        w = make_world({})
        w.gamedata.items[CLOTH] = item(CLOTH, 'Mageweave Cloth', sell=250)        # worth 250c (vendor) to us
        w.gamedata.items[HIDE] = item(HIDE, 'Heavy Hide', sell=400)
        w.forever_pages, _, _ = wi.merge({}, {str(CLOTH): page('Mageweave Cloth', {'dropped-by': {'kind': 'npc', 'rows': [
            row(MOB_A, 30, 100, minlevel=40, maxlevel=41, location=[33], stack={'1': 75, '2': 25}),
            row(MOB_B, 40, 80, minlevel=50, maxlevel=51, location=[33], classification=1)]}})})
        w.forever_skinning = {'items': {str(HIDE): {'npcs': [{'npc': MOB_A, 'name': 'Mob A', 'count': 50, 'outof': 100,
                                                              'min_level': 40, 'max_level': 41, 'zones': [33]}]}}}
        w.questie.npcs[MOB_A] = {'name': 'Jungle Stalker', 'minLevel': 40, 'maxLevel': 41, 'zoneID': 33}
        return w

    def rows(self, **settings):
        from tests.test_engine import SETTINGS
        from wfm.engine import Engine
        e = Engine(self.world(), dict(SETTINGS, level=40, kills_per_hour=60, **settings))
        return e, {o.detail['npc']: o for o in e.mob_spots({})}

    def test_value_per_kill_with_and_without_a_skin(self):
        e, rows = self.rows(professions={'Skinning': 300})
        cloth, hide = e.fish_value(CLOTH, {}), e.fish_value(HIDE, {})
        a = rows[MOB_A]
        # 30 of 100 kills, 1.25 a drop -> 0.375 cloth a kill; skinned: 50 of 100 skins gave a hide -> 0.5 a skin
        self.assertEqual(a.profit_unit, int(0.375 * cloth + 0.5 * hide))
        self.assertEqual(a.gph, int((0.375 * cloth + 0.5 * hide) * 60))
        self.assertEqual(a.title, 'Kill Jungle Stalker in ' + e.gd.zones.get(33, 'zone 33'))
        self.assertTrue(a.doable)
        self.assertIn('drops_partial', a.flags)
        _, rows = self.rows(professions={})
        self.assertEqual(rows[MOB_A].profit_unit, int(0.375 * cloth))               # no Skinning: drops only
        self.assertIn('skin_extra', rows[MOB_A].flags)

    def test_elites_and_mobs_far_above_you_stay_out_of_top_picks(self):
        from wfm.engine import Engine
        e, rows = self.rows()
        b = rows[MOB_B]
        self.assertFalse(b.doable)                                                  # level 51, you are 40
        self.assertIn('elite', b.flags)
        self.assertIsNone(b.gph)                    # can't be killed 60 times an hour: value per kill only
        self.assertGreater(b.profit_unit, 0)
        self.assertFalse(Engine._hourly_ok(b))
        self.assertTrue(Engine._hourly_ok(rows[MOB_A]))

    def test_a_floor_never_sets_your_time_value(self):
        # only some drops are counted (no coins, gray items), so mob rows stay out of "what an hour is worth"
        e, _ = self.rows()
        e.run()
        self.assertEqual(e.time_value_source, 'default')


class SkinningFromItemPagesTests(unittest.TestCase):
    def test_a_mob_of_unknown_level_is_not_doable(self):
        from wfm import skinning
        table = {7: {'npc': 7, 'name': 'Thicket Lurker', 'min_level': 0, 'max_level': 0, 'zones': [16732],
                     'skinned': 500, 'items': {HIDE: 0.5}},
                 8: {'npc': 8, 'name': 'Known Boar', 'min_level': 30, 'max_level': 31, 'zones': [16732],
                     'skinned': 400, 'items': {HIDE: 0.4}}}
        spot = skinning.spots(table, lambda i: 100, str, 300, 60)[0]
        mobs = {m['npc']: m for m in spot['mobs']}
        self.assertFalse(mobs[7]['can_kill'] or mobs[7]['can_skin'])
        self.assertTrue(mobs[8]['can_kill'] and mobs[8]['can_skin'])
        self.assertEqual((spot['min_level'], spot['max_level'], spot['value']), (30, 31, 40))   # only the known mob


class CoverageTests(unittest.TestCase):
    def test_node_pages_cover_mining_but_not_mob_drops(self):
        kinds = {'mining', 'drops'}
        self.assertEqual(coverage.covered_kinds(ORE, kinds, set(), set(), set(), {ORE}), {'mining'})
        self.assertEqual(coverage.covered_kinds(ORE, kinds, set(), set(), {ORE}, set()), kinds)


class ImportTests(unittest.TestCase):
    """Pages read out of the Wowhead tab, saved with `python -m wfm.wowhead_items import <file>`."""

    def test_compact_rows_are_expanded(self):
        p = page('Mageweave Cloth', {'dropped-by': {'kind': 'npc', 'total': 2, 'classic': 0, 'small': 3, 'rows': [
            [MOB_A, 30, 100, 40, 41, 33, 1, {'1': 75, '2': 25}], [MOB_B, 4, 40, None, None, [17, 18]]]}})
        data, saved, problems = wi.merge({}, {f'item={CLOTH}': p})
        self.assertEqual(problems, [])
        rows = data['items'][str(CLOTH)]['tabs']['dropped-by']['rows']
        self.assertEqual(rows[0], {'id': MOB_A, 'count': 30, 'outof': 100, 'minlevel': 40, 'maxlevel': 41,
                                   'classification': 1, 'location': [33], 'stack': {'1': 75.0, '2': 25.0}})
        self.assertEqual(rows[1], {'id': MOB_B, 'count': 4, 'outof': 40, 'location': [17, 18]})
        self.assertEqual(data['items'][str(CLOTH)]['tabs']['dropped-by']['small'], 3)

    def test_import_file_merges_and_saves(self):
        with tempfile.TemporaryDirectory() as d:
            src, target = Path(d) / 'batch.json', Path(d) / 'pages.json'
            src.write_text(json.dumps({str(CLOTH): cloth_page(), 'item=1': {'tabs': 'x'}}), encoding='utf-8')
            saved, problems, total = wi.import_file(src, target)
            self.assertEqual((saved, len(problems), total['items']), ([f'item={CLOTH}'], 1, 1))
            self.assertIn(str(CLOTH), wi.load(target)['items'])


if __name__ == '__main__':
    unittest.main()
