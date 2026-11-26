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

    def test_newest_snapshot_of_a_character_wins(self):
        """The same character saved twice by the addon (the realm name it read changed): the newest entry wins,
        whatever order the file lists them in. Found 2026-11-26: the app showed level 52 for a level-60 character."""
        chars = profile.read_tsm_characters(self.tsm_file(self.TSM))
        old = {'name': 'Testchar', 'realm': 'CAMWOW EU5 Realm 4 PvP', 'faction': 'Horde', 'level': 52, 'money': 100,
               'updated': 1795199111}
        new = {'name': 'Testchar', 'realm': '', 'faction': 'Horde', 'level': 60, 'money': 900, 'updated': 1795685643}
        for order in (('Testchar - ', new), ('Testchar - CAMWOW EU5 Realm 4 PvP', old)), \
                     (('Testchar - CAMWOW EU5 Realm 4 PvP', old), ('Testchar - ', new)):
            bridge = {'lastCharacter': 'Testchar - ', 'characters': dict(order)}
            prof = profile.build_profile(bridge, chars, {})
            self.assertEqual(prof['active'], 'Testchar Alpha')
            self.assertEqual(len([n for n in prof['characters'] if n.startswith('Testchar')]), 1, 'one character, not two')
            eff, det = profile.apply({'auto_detect': True, 'gold_scope': 'character'}, prof)
            self.assertEqual(det['level'], 60)
            self.assertEqual(eff['gold'], 0.09)

    def test_auto_detect_off(self):
        prof = profile.build_profile({}, profile.read_tsm_characters(self.tsm_file(self.TSM)), {})
        eff, det = profile.apply({'auto_detect': False, 'level': 42, 'professions': {}}, prof)
        self.assertEqual(det, {})
        self.assertEqual(eff['level'], 42)


if __name__ == '__main__':
    unittest.main()


class KnownCraftsTests(unittest.TestCase):
    def test_recipes_each_character_knows_from_tsm(self):
        db = {'f@Horde - PvP@internalData@crafts': {
                  'c:3275': {'name': 'Linen Bandage', 'players': {'Testchar Alpha': {'maxRecipeQuality': 1}}},
                  'c:2152': {'name': 'Light Armor Kit', 'players': {'Testchar Alpha': {}, 'Alt Beta': {}}},
                  'oddkey': {'players': {'Alt Beta': {}}}},
              's@Testchar Alpha - Horde - PvP@internalData@money': 5}
        self.assertEqual(profile.known_crafts(db), {'Testchar Alpha': {3275, 2152}, 'Alt Beta': {2152}})
        self.assertEqual(profile.known_crafts({}), {})


class MeterPricesTests(unittest.TestCase):
    def test_prices_table_and_install_keeps_it(self):
        with tempfile.TemporaryDirectory() as d:
            addons = Path(d, 'AddOns')
            src = Path(d, 'src'); src.mkdir()
            for name, text in (('ForeverMoneyBridge.toc', '## Version: 1.5.0\n'), ('Prices.lua', 'ForeverMoneyBridge_Prices = {made=0, items={}}\n'),
                               ('Checks.lua', 'ForeverMoneyBridge_Checks = {}\n')):
                Path(src, name).write_text(text, encoding='utf-8')
            profile.install_addon(src, addons, log=lambda m: None)
            self.assertTrue(profile.write_prices(addons, {2589: 95, 4306: 0, 2592: 140}, 1_800_000_000))
            text = (addons / 'ForeverMoneyBridge' / 'Prices.lua').read_text(encoding='utf-8')
            self.assertIn('ForeverMoneyBridge_Prices = {made=1800000000, items={[2589]=95,[2592]=140}, containers={}}', text)
            self.assertTrue(profile.write_prices(addons, {2589: 95, 2592: 140}, 1_800_000_000, {7973}))
            self.assertIn('containers={[7973]=true}', (addons / 'ForeverMoneyBridge' / 'Prices.lua').read_text(encoding='utf-8'))
            self.assertFalse(profile.write_prices(addons, {2589: 95, 2592: 140}, 1_800_000_999, {7973}))   # same values
            Path(src, 'Meter.lua').write_text('-- new file', encoding='utf-8')
            profile.install_addon(src, addons, log=lambda m: None)                               # an update
            self.assertIn('[2589]=95', (addons / 'ForeverMoneyBridge' / 'Prices.lua').read_text(encoding='utf-8'))
            self.assertTrue((addons / 'ForeverMoneyBridge' / 'Meter.lua').exists())
