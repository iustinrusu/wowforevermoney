"""ForeverRecipes (the main recipe source since 2026-11-19): reading its generated tables, SkillUpForever (optional)
filling its gaps."""
import tempfile
import unittest
from pathlib import Path

from wfm import foreverrecipes
from wfm.skillup import SkillUpData

# shaped like ForeverRecipes 1.17.1's Data/Recipes.lua and Data/Sources.lua (values from the user's install)
RECIPES = '''-- Generated from validated client build1.60.1.70938 and frozen reference facts; do not edit.
local _, ns = ...
ns.Recipes = {
[2835]={40,{0,175,200,225},{5173,1,3372,1},{2892,1.0},false,2734},
[19047]={165,{225,225,230,235},{8171,1,15409,1},{15407,2.0},false,2550},
[2149]={165,{1,40,55,70},{2318,2,2320,1},{2302,1.0},false,2560},
[9999]={165,{50,60,70,80},{2318,1},{2302,1.0},false,2560},
[7153]={197,{0,180,190,200},{4305,3},{5965,1.0},false,2560},
[7777]={197,{0,0,0,0},{4305,1},{5966,1.0},false,2560},
}
ns.RecipeMeta = {
[2835]={["levelRequired"]=30,["requirementKnown"]=true,["thresholdsKnown"]=true},
[19047]={["requirementKnown"]=true,["thresholdsKnown"]=true},
[2149]={["requirementKnown"]=true,["thresholdsKnown"]=true},
[9999]={["thresholdsKnown"]=true},
[7153]={["requirementKnown"]=false,["thresholdsKnown"]=true},
[7777]={["thresholdsKnown"]=false},
}
'''
SOURCES = '''local _, ns = ...
ns.Trainers = {
[2835]={{[1]=917,[2]=10000,[3]=130},{[1]=918,[2]=10000,[3]=130}},
[19047]={{[1]=7870,[2]=4300,[3]=250},{[1]=11097,[2]=5000,[3]=225}},
}
ns.AutomaticRecipes = {
[2149]=true,
}
ns.SourceMeta = {
[2158]={["limitedStockVendors"]={[2406]={[1300]=true,[1301]=true}}},
}
'''


DISENCHANT = '''local _, ns = ...
ns.DisenchantProfiles = {
[1]={{10938,0.2,1,2},{10940,0.8,1,2}},
[64]={{20725,1.0,1,1}},
[70]=false,
}
ns.DisenchantRules = {
[1]={2,-1,2,5,15,1,3},
[2]={4,0,2,10,10,70,4},
}
ns.DisenchantExcluded = {
[11287]=true,
}
ns.DisenchantItems = {
[647]={64},
[744]={false},
}
ns.DisenchantEligible = {
[647]=true,
[5000]=true,
}
'''


class ForeverRecipesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / 'Recipes.lua').write_text(RECIPES, encoding='utf-8')
        (d / 'Sources.lua').write_text(SOURCES, encoding='utf-8')
        (d / 'Disenchant.lua').write_text(DISENCHANT, encoding='utf-8')
        self.fr = foreverrecipes.load(d)

    def test_disenchant_tables(self):
        fr = self.fr
        dp = foreverrecipes.disenchant_profile
        self.assertEqual(dp(fr, 647, 2, 7, 4, 57), (64, 'ok'))                  # Destiny: its own entry, a Nexus Crystal
        self.assertEqual(foreverrecipes.disenchant_materials(fr, 64), [(20725, 1.0, 1, 1)])
        self.assertEqual(dp(fr, 744, 4, 0, 2, 20), (None, 'unsupported'))       # {false}: no estimate
        self.assertEqual(dp(fr, 11287, 2, 7, 2, 10), (None, 'excluded'))
        self.assertEqual(dp(fr, 5000, 2, 3, 2, 12), (1, 'ok'))                  # by the rules: a green weapon, ilvl 5-15
        self.assertEqual(dp(fr, 5000, 4, 0, 2, 10), (None, 'unsupported'))      # rule 2 points at an unsupported profile
        self.assertEqual(dp(fr, 5001, 2, 3, 2, 12), (None, 'unsupported'))      # not in the eligible list
        self.assertEqual(dp(fr, 5000, 7, 0, 2, 12), (None, 'ineligible'))       # not a weapon or armour
        self.assertEqual(dp(fr, 5000, 2, 3, 1, 12), (None, 'ineligible'))       # white quality

    def test_disenchant_skill_classic_rule(self):
        s = foreverrecipes.disenchant_skill
        self.assertEqual([s(2, 15), s(2, 21), s(3, 40), s(2, 60), s(2, 65), s(3, 70)], [1, 25, 100, 200, 225, 275])
        self.assertEqual((s(4, 57), s(4, 66)), (225, 300))

    def test_reads_the_tables(self):
        r = self.fr.recipes[19047]
        self.assertEqual((r['skill_line'], r['thresholds'], r['reagents'], r['product'], r['count']),
                         (165, [225, 225, 230, 235], [(8171, 1), (15409, 1)], 15407, 2.0))
        self.assertEqual(self.fr.trainers[2835][0], (917, 10000, 130))
        self.assertEqual(self.fr.automatic, {2149})
        self.assertEqual(self.fr.source_build, '1.60.1.70938')

    def test_forever_recipes_first_skillupforever_fills_gaps(self):
        # the user, 2026-11-19: "make skillupforever optional so I can delete the addon"
        su = SkillUpData(thresholds={19047: [1, 225, 230, 235], 2149: [1, 40, 55, 70], 9999: [55, 60, 70, 80],
                                     7777: [150, 160, 170, 180], 4242: [100, 120, 130, 140]},
                         trainer_fees={19047: [3870, 225], 4242: [500, 100]},
                         limited_stock={2406: {1300: 2}, 9000: {77: 3}})
        m = foreverrecipes.merged(su, self.fr)
        self.assertEqual(m.thresholds[19047], [225, 225, 230, 235])      # the app guessed 185 (yellow - 40)
        self.assertEqual(m.thresholds[2835], [130, 175, 200, 225])       # poisons: orange 0 -> the trainer's skill
        self.assertEqual(m.level_required, {2835: 30})
        self.assertEqual(m.trainer_fees[2835], [10000, 130])             # the cheapest trainer
        self.assertEqual(m.trainer_fees[19047], [4300, 250])             # ForeverRecipes' fee first (the full price)
        self.assertEqual(m.thresholds[9999], [55, 60, 70, 80])           # its required skill unknown: SkillUpForever's
        self.assertEqual(m.from_skillup, {9999, 7777})
        self.assertEqual(m.thresholds[2149], [1, 40, 55, 70])            # orange 1 is real (a starting recipe)
        self.assertEqual(m.thresholds[7153], [0, 180, 190, 200])         # unknown to both: the engine estimates it
        self.assertNotIn(7153, m.requirement_known)
        self.assertEqual(m.thresholds[7777], [150, 160, 170, 180])       # colours unknown to ForeverRecipes
        self.assertEqual(m.requirement_known, {19047, 2835, 2149, 9999, 7777})
        self.assertNotIn(4242, m.thresholds)                             # only SkillUpForever lists it: left out
        self.assertEqual(m.from_forever_recipes, {19047, 2835, 2149, 9999, 7153})
        # stock: SkillUpForever's count where it has one, else 1 a restock; its other vendors stay
        self.assertEqual(m.limited_stock, {2406: {1300: 2, 1301: 1}, 9000: {77: 3}})
        self.assertEqual(su.thresholds[19047], [1, 225, 230, 235])        # the inputs are not changed
        self.assertEqual(su.limited_stock[2406], {1300: 2})
        self.assertNotIn(2835, su.thresholds)

    def test_forever_recipes_alone(self):
        # SkillUpForever deleted: the same recipes, every required skill ForeverRecipes knows, pattern stock limits
        m = foreverrecipes.merged(None, self.fr)
        self.assertEqual(sorted(m.thresholds), [2149, 2835, 7153, 9999, 19047])
        self.assertEqual(m.thresholds[9999], [0, 60, 70, 80])
        self.assertEqual(m.requirement_known, {19047, 2835, 2149})
        self.assertEqual(m.trainer_fees, {2835: [10000, 130], 19047: [4300, 250]})
        self.assertEqual(m.limited_stock, {2406: {1300: 1, 1301: 1}})
        self.assertEqual((m.rank_trainers, m.vendor_prices, m.from_skillup), ({}, {}, set()))

    def test_a_saved_copy_of_skillupforevers_tables(self):
        # kept for when the addon is deleted (2026-11-19): stock limits and rank fees go on working
        from wfm.skillup import load_copy, save_copy
        su = SkillUpData(thresholds={19047: [1, 225, 230, 235]}, trainer_fees={19047: [4300, 225]},
                         limited_stock={8846: {1300: 2}}, vendor_prices={3371: 4},
                         recipe_scrolls={2158: [2406, 65]}, rank_trainers={165: [(150, 500, 50, 10)]},
                         rank_quests={185: [(300, 6610, 225, 35, 'A')]}, profession_trainers={165: [(1385, 150)]},
                         source_build='1.60.1.70959')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'skillup_saved.json'
            self.assertTrue(save_copy(su, '2.4.0', path))
            back, info = load_copy(path)
            self.assertEqual(info['version'], '2.4.0')
            for f in ('thresholds', 'trainer_fees', 'limited_stock', 'vendor_prices', 'recipe_scrolls', 'rank_trainers',
                      'rank_quests', 'profession_trainers', 'source_build'):
                self.assertEqual(getattr(back, f), getattr(su, f), f)
            self.assertFalse(save_copy(su, '2.4.0', path))                # unchanged: the first date stays
            self.assertFalse(save_copy(SkillUpData(), None, path))        # nothing to save
            self.assertEqual(load_copy(Path(tmp) / 'none.json'), (None, {}))
            # merged with ForeverRecipes as if the addon were installed
            m = foreverrecipes.merged(back, self.fr)
            self.assertEqual(m.limited_stock[8846], {1300: 2})
            self.assertEqual(m.rank_trainers, {165: [(150, 500, 50, 10)]})

    def test_without_forever_recipes(self):
        su = SkillUpData(thresholds={19047: [1, 225, 230, 235], 1: [100, 120, 130, 140]})
        m = foreverrecipes.merged(su, None)
        self.assertEqual(m.thresholds, su.thresholds)
        self.assertEqual(m.requirement_known, {1})

    def test_compare_the_two_sources(self):
        su = SkillUpData(thresholds={19047: [1, 225, 230, 235], 9999: [50, 61, 70, 80]})
        c = foreverrecipes.compare(su, self.fr)
        self.assertEqual((c['both'], c['same']), (2, 1))
        self.assertEqual(c['diff'], [(9999, [61, 70, 80], [60, 70, 80])])
        self.assertEqual(c['only_forever_recipes'], [2149, 2835, 7153, 7777])



# where recipes come from: shaped like ForeverRecipes 1.17.1's Sources.lua and Npcs.lua (made-up NPC names)
WHERE_RECIPES = """local _, ns = ...
ns.Recipes = {
[2158]={165,{65,95,110,125},{2318,7,2320,2},{2307,1.0},2406,2560},
[3397]={165,{90,115,130,145},{2318,1},{3000,1.0},3734,2560},
}
ns.RecipeItems = {
[2158]={2406},
}
"""
WHERE_SOURCES = """local _, ns = ...
ns.Trainers = {
[3397]={{[1]=10,[2]=500,[3]=90},{[1]=11,[2]=500,[3]=90}},
}
ns.Sellers = {
[3734]={20,21},
}
ns.Drops = {
[2406]={{30,0.21},{31,0.41841}},
}
ns.OtherDrops = {
[2406]={{["name"]="Battered Chest"}},
}
ns.QuestRewards = {
[3734]={7,8},
}
ns.RecipeVendorCosts = {
[3734]={[20]="1600 copper",[21]="40 Merchant's Favor"},
}
ns.SourceMeta = {
[3397]={["limitedStockVendors"]={[3734]={[20]=true}}},
}
ns.RecipeItemBinding = {
[2406]="none",
[3734]="onPickup",
}
"""
WHERE_NPCS = """local _, ns = ...
ns.Npcs = {
[10]={"Hide Trainer","A",{[1]="Elwynn Forest",[2]=1429,[3]=41.8,[4]=67}},
[11]={"Pelt Trainer","H",{[1]="Durotar",[2]=1411,[3]=52,[4]=40,["approximate"]=true}},
[20]={"Pattern Seller",false,{[1]="Desolace",[2]=1443,[3]=40.4,[4]=79.2}},
[21]={"Favor Seller","A"},
[30]={"Bog Lurker",false,{[1]="Wetlands"}},
[31]={"Cave Prowler",false,{[1]="Durotar",[2]=1411,[3]=52.6,[4]=8.8,["approximate"]=true}},
}
ns.Quests = {
[7]={"The Lost Pattern"},
[8]={"Horde Errand"},
}
ns.QuestMeta = {
[7]={["name"]="The Lost Pattern",["requiredLevel"]=17,["side"]="Both",["starts"]={{["location"]={["zone"]="Hillsbrad Foothills"},["name"]="Old Tanner"}}},
[8]={["name"]="Horde Errand",["requiredLevel"]=20,["side"]="Horde"},
}
"""


class RecipeSourcesTests(unittest.TestCase):
    """Where each recipe is learned (the user, 2026-11-19: "all recipes in game, and where to get them or learn them")."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / 'Recipes.lua').write_text(WHERE_RECIPES, encoding='utf-8')
        (d / 'Sources.lua').write_text(WHERE_SOURCES, encoding='utf-8')
        (d / 'Npcs.lua').write_text(WHERE_NPCS, encoding='utf-8')
        self.fr = foreverrecipes.load(d)

    def test_drops_chests_and_find_how(self):
        s = foreverrecipes.sources(self.fr, 2158, 'A')
        self.assertEqual(s['items'], [2406])
        self.assertEqual([(r['name'], r['chance']) for r in s['dropped_by']],
                         [('Cave Prowler', 0.41841), ('Bog Lurker', 0.21)])        # in %, best first
        self.assertEqual(s['dropped_by'][0]['zone'], 'Durotar')
        self.assertEqual(s['other_drops'], [{'name': 'Battered Chest', 'chance': None, 'item': 2406}])
        self.assertTrue(s['tradeable'])
        self.assertEqual(foreverrecipes.find_how(s), 'drop')

    def test_trainers_vendors_and_quests_for_your_faction(self):
        s = foreverrecipes.sources(self.fr, 3397, 'A')
        self.assertEqual([(t['name'], t['cost'], t['skill']) for t in s['trainers']], [('Hide Trainer', 500, 90)])
        self.assertEqual([(v['name'], v['copper'], v['cost_text'], v['limited']) for v in s['sold_by']],
                         [('Pattern Seller', 1600, '1600 copper', True),            # gold first, then other currencies
                          ('Favor Seller', None, "40 Merchant's Favor", False)])
        self.assertEqual([(q['name'], q['level'], q['start'], q['zone']) for q in s['quests']],
                         [('The Lost Pattern', 17, 'Old Tanner', 'Hillsbrad Foothills')])   # the Horde one is left out
        self.assertFalse(s['tradeable'])
        h = foreverrecipes.sources(self.fr, 3397, 'H')
        self.assertEqual([t['name'] for t in h['trainers']], ['Pelt Trainer'])
        self.assertEqual([v['name'] for v in h['sold_by']], ['Pattern Seller'])
        self.assertEqual(len(h['quests']), 2)
        self.assertEqual(foreverrecipes.sources(self.fr, 9999, 'A')['items'], [])
        self.assertEqual(foreverrecipes.find_how(foreverrecipes.sources(self.fr, 9999, 'A')), '')
        self.assertIsNone(foreverrecipes.sources(None, 3397))


if __name__ == '__main__':
    unittest.main()
