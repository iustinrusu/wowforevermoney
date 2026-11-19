"""ForeverRecipes (second recipe source): reading its generated tables and filling SkillUpForever's holes."""
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
}
ns.RecipeMeta = {
[2835]={["levelRequired"]=30,["requirementKnown"]=true,["thresholdsKnown"]=true},
[19047]={["requirementKnown"]=true,["thresholdsKnown"]=true},
[2149]={["requirementKnown"]=true,["thresholdsKnown"]=true},
[9999]={["thresholdsKnown"]=true},
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

    def test_fills_skillupforevers_holes_and_keeps_what_it_knows(self):
        # SkillUpForever: Cured Rugged Hide's orange unknown (stored 1), no poisons, 2149 known exactly
        su = SkillUpData(thresholds={19047: [1, 225, 230, 235], 2149: [1, 40, 55, 70], 9999: [55, 60, 70, 80]},
                         trainer_fees={19047: [4300, 225]})
        m = foreverrecipes.merged(su, self.fr)
        self.assertEqual(m.thresholds[19047], [225, 225, 230, 235])      # the app guessed 185 (yellow - 40)
        self.assertEqual(m.thresholds[2835], [130, 175, 200, 225])       # poisons: orange 0 -> the trainer's skill
        self.assertEqual(m.level_required, {2835: 30})
        self.assertEqual(m.trainer_fees[2835], [10000, 130])             # the cheapest trainer
        self.assertEqual(m.trainer_fees[19047], [4300, 225])             # SkillUpForever's own fee stays
        self.assertEqual(m.thresholds[9999], [55, 60, 70, 80])           # SkillUpForever knows it: it stays first
        self.assertEqual(m.thresholds[2149], [1, 40, 55, 70])            # orange 1 is real (a starting recipe)
        self.assertIn(2149, m.requirement_known)
        self.assertEqual(m.from_forever_recipes, {19047, 2835, 2149})
        self.assertEqual(su.thresholds[19047], [1, 225, 230, 235])        # the input is not changed
        self.assertNotIn(2835, su.thresholds)

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
        self.assertEqual(c['only_forever_recipes'], [2149, 2835])


if __name__ == '__main__':
    unittest.main()
