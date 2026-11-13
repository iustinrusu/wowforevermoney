import tempfile
import unittest
from pathlib import Path

from wfm import profile


class ProfileTests(unittest.TestCase):
    def tsm_file(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / 'TradeSkillMaster.lua'
        p.write_text(text, encoding='utf-8')
        return p

    TSM = ('TradeSkillMasterDB = {\n'
           '["s@Testchar Alpha - Horde - PvP@internalData@money"] = 1696,\n'
           '["s@Testchar Alpha - Horde - PvP@internalData@playerProfessions"] = {\n'
           '["Cooking"] = {["level"] = 225, ["maxLevel"] = 225, ["isSecondary"] = true},\n'
           '["Leatherworking"] = {["level"] = 161, ["maxLevel"] = 225},\n},\n'
           '["s@Alt Beta - Horde - PvP@internalData@money"] = 70,\n'
           '["s@Alt Beta - Horde - PvP@internalData@playerProfessions"] = {\n'
           '["Enchanting"] = {["level"] = 2, ["maxLevel"] = 75},\n},\n'
           '["s@Ally Guy - Alliance - PvP@internalData@money"] = 99999,\n'
           '}\n')

    def test_tsm_only_guesses_main_and_merges_professions(self):
        chars = profile.read_tsm_characters(self.tsm_file(self.TSM))
        self.assertEqual(chars['Testchar Alpha']['money'], 1696)
        # the alt logged out last, but the main has far more profession skill
        prof = profile.build_profile({}, chars, {'Alt Beta': 200, 'Testchar Alpha': 100})
        self.assertEqual(prof['active'], 'Testchar Alpha')
        manual = {'auto_detect': True, 'professions': {'Fishing': 225, 'Skinning': 270, 'Cooking': 1}, 'level': 42}
        eff, det = profile.apply(manual, prof)
        # TSM has no Fishing/Skinning: keep them from manual; TSM's Cooking wins over the manual value
        self.assertEqual(eff['professions'], {'Fishing': 225, 'Skinning': 270, 'Cooking': 225, 'Leatherworking': 161})
        self.assertEqual(eff['level'], 42, 'no level in TSM data: manual value stays')
        self.assertEqual(det['gold'], round((1696 + 70) / 10000, 4), 'Horde characters only')
        self.assertEqual(eff['faction'], 'H')

    def test_bridge_is_authoritative(self):
        chars = profile.read_tsm_characters(self.tsm_file(self.TSM))
        bridge = {'lastCharacter': 'Testchar - Alpha', 'characters': {'Testchar - Alpha': {
            'name': 'Testchar', 'faction': 'Horde', 'level': 43, 'money': 12345,
            'professions': {'Fishing': {'rank': 230, 'max': 300}, 'Cooking': {'rank': 226, 'max': 300}}}}}
        prof = profile.build_profile(bridge, chars, {})
        self.assertEqual(prof['active'], 'Testchar Alpha', 'bridge name is matched to the TSM character')
        eff, det = profile.apply({'auto_detect': True, 'professions': {'Skinning': 270}, 'gold_scope': 'character'}, prof)
        self.assertEqual(eff['level'], 43)
        self.assertEqual(eff['professions'], {'Fishing': 230, 'Cooking': 226}, 'complete list replaces manual')
        self.assertEqual(eff['gold'], 1.2345)

    def test_auto_detect_off(self):
        prof = profile.build_profile({}, profile.read_tsm_characters(self.tsm_file(self.TSM)), {})
        eff, det = profile.apply({'auto_detect': False, 'level': 42, 'professions': {}}, prof)
        self.assertEqual(det, {})
        self.assertEqual(eff['level'], 42)


if __name__ == '__main__':
    unittest.main()
