"""TargetKit (extras/TargetKit, our addon outside the app): what each of its three buttons chooses, run in Lua 5.1
through lupa with tests/targetkit_harness.lua standing in for WoW. The names here are made up."""
import unittest
from pathlib import Path

try:
    import lupa.lua51 as lua51
except ImportError:          # pip install lupa
    lua51 = None

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / 'extras' / 'TargetKit'
MOUSEOVER = '/cast [@mouseover,harm,nodead] Sap\n/stopmacro [@mouseover,harm,nodead]'


@unittest.skipUnless(lua51, 'lupa is not installed (pip install lupa)')
class TargetKitTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((ROOT / 'tests' / 'targetkit_harness.lua').read_text(encoding='utf-8'))
        run = self.lua.eval('function(src) local f = assert(loadstring(src, "TargetKit.lua")); f("TargetKit", {}) end')
        run((KIT / 'TargetKit.lua').read_text(encoding='utf-8'))
        self.g = self.lua.globals()
        self.events = self.g.frames[1]                  # made when the file loads; the buttons at login
        self.n = 0
        self.fire('PLAYER_LOGIN')

    def fire(self, *args):
        self.events.scripts['OnEvent'](self.events, *args)

    def unit(self, token, name='Defias Thug', plate=True, **kw):
        """A unit the addon can see under `token` (with a nameplate unless plate=False)."""
        self.n += 1
        fields = dict(name=name, guid=f'Creature-0-1-2-3-{self.n}-0000{self.n:04d}', reach=3, enemy=True,
                      type=7, reaction=2, y=400 + self.n if plate else None)
        fields.update(kw)
        t = self.lua.table_from({k: v for k, v in fields.items() if v is not None})
        self.g.UNITS[token] = t
        if plate:
            self.lua.eval('table.insert')(self.g.PLATES, token)
        return t

    def press(self, button):
        """Press one of the three macros: PreClick writes the macro, the click runs it, PostClick puts it back."""
        b = self.g[button]
        b.scripts['PreClick'](b, 'LeftButton', True)
        text = b.attrs['macrotext']
        if not self.g.COMBAT:
            b.scripts['PostClick'](b, 'LeftButton', True)
        return text

    def slash(self, msg):
        self.g.SlashCmdList.TARGETKIT(msg)

    def said(self, text):
        return any(text in line for line in self.g.printed.values())

    # --- the macros the addon makes ---
    def test_the_three_macros_are_made_once_and_click_on_key_down(self):
        macros = {m.name: m.body for m in self.g.MACROS.values()}
        self.assertEqual(macros, {
            'TK Find': '/click TargetKitFind LeftButton 1',
            'TK Pickpocket': '#showtooltip Pick Pocket\n/click TargetKitPick LeftButton 1',
            'TK Sap': '#showtooltip Sap\n/click TargetKitSap LeftButton 1'})
        self.assertTrue(self.g.TargetKitDB.macrosMade)
        self.g.KEYDOWN = False                          # "act on key down" turned off: plain /click
        self.fire('CVAR_UPDATE', 'ActionButtonUseKeyDown')
        self.assertEqual(self.g.MACROS[3].body, '#showtooltip Sap\n/click TargetKitSap')
        self.assertEqual(len(self.g.MACROS), 3)

    # --- TK Sap ---
    def test_sap_takes_the_closest_enemy_player_in_sap_range_before_a_closer_npc(self):
        self.unit('nameplate1', 'Defias Pathstalker', reach=1)
        self.unit('nameplate2', 'Shadowfang', player=True, reach=2, y=300)
        self.unit('nameplate3', 'Nightstep', player=True, reach=2, y=200)     # lower on screen: nearer
        self.unit('nameplate4', 'Farstrider', player=True, reach=5)
        self.assertEqual(self.press('TargetKitSap'), MOUSEOVER + '\n/target nameplate3\n/cast Sap')

    def test_sap_skips_who_it_cannot_sap(self):
        self.unit('nameplate1', 'In Combat', player=True, reach=1, combat=True)
        self.unit('nameplate2', 'Dead One', player=True, reach=1, dead=True)
        self.unit('nameplate3', 'Sapped One', player=True, reach=1, sapped=True)
        self.unit('nameplate4', 'Wolf', reach=1, type=1)                        # a beast
        self.unit('nameplate5', 'Friend', player=True, reach=1, enemy=False)
        self.unit('nameplate6', 'Defias Pathstalker', reach=2)                  # the NPC in Sap range
        text = self.press('TargetKitSap')
        self.assertEqual(text, MOUSEOVER + '\n/cleartarget [dead][noharm][noplayer]\n/targetenemyplayer [noexists]'
                               '\n/target [noexists] nameplate6\n/targetenemy [noexists]\n/cast Sap')

    def test_sap_with_no_player_in_sight_lets_the_game_find_a_revealed_stealther(self):
        """A rogue the game has just revealed has no nameplate: only the game's own /targetenemyplayer reaches it."""
        self.unit('nameplate1', 'Farstrider', player=True, reach=4)            # a player, but out of Sap range
        text = self.press('TargetKitSap')
        self.assertIn('/targetenemyplayer [noexists]', text)
        self.assertNotIn('nameplate1', text)
        self.assertTrue(text.startswith(MOUSEOVER))

    def test_in_combat_the_fixed_macro_runs(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)
        fixed = self.g.TargetKitSap.attrs['macrotext']
        self.fire('PLAYER_REGEN_DISABLED')
        self.g.COMBAT = True
        self.assertEqual(self.press('TargetKitSap'), fixed)                     # nothing may change it now
        self.assertIn('/targetenemyplayer [noexists]', fixed)

    # --- TK Pickpocket ---
    def test_pickpocket_saps_then_robs_the_closest_humanoid_npc(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)              # players have no pockets to pick
        self.unit('nameplate2', 'Wolf', reach=1, type=1)
        self.unit('nameplate3', 'Defias Guard', reach=1, combat=True)
        self.unit('nameplate4', 'Defias Thug', reach=2)
        self.unit('nameplate5', 'Defias Miner', reach=3)
        self.assertEqual(self.press('TargetKitPick'), '/target nameplate4\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_moves_on_and_finishes_a_half_done_one(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.unit('nameplate2', 'Defias Miner', reach=2)
        self.assertIn('/target nameplate1', self.press('TargetKitPick'))
        self.g.UNITS.target = thug
        thug.sapped = True                              # Sap landed, Pick Pocket was still on cooldown
        self.g.NOW += 1.5
        self.assertEqual(self.press('TargetKitPick'), '/cast Pick Pocket')
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)
        self.g.NOW += 1.5
        self.assertEqual(self.press('TargetKitPick'), '/target nameplate2\n/cast Sap\n/cast Pick Pocket')

    def test_robbed_but_not_sapped_gets_sapped(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.press('TargetKitPick')
        self.g.UNITS.target = thug
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)         # robbed, the Sap didn't happen
        self.assertEqual(self.press('TargetKitPick'), '/cast Sap')

    def test_one_already_sapped_is_only_robbed(self):
        self.unit('nameplate1', 'Defias Thug', reach=1, sapped=True)
        self.assertEqual(self.press('TargetKitPick'), '/target nameplate1\n/cast Pick Pocket')

    def test_no_pockets_to_pick_means_skip_it(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.g.UNITS.target = thug
        self.fire('UI_ERROR_MESSAGE', 51, 'No pockets to pick')
        self.assertEqual(self.press('TargetKitPick'), '/targetenemy [noharm][dead]\n/cast Sap\n/cast Pick Pocket')

    # --- TK Find ---
    def test_find_goes_closest_first_then_the_next_on_each_press(self):
        self.slash('add thug')
        self.unit('nameplate1', 'Defias Thug', reach=5)
        self.unit('nameplate2', 'Defias Thug', reach=2)
        self.unit('nameplate3', 'Riverpaw Thug', reach=4)                      # part of a name is enough
        self.unit('nameplate4', 'Defias Miner', reach=1)                       # not on the list
        presses = [self.press('TargetKitFind') for _ in range(4)]
        self.assertEqual(presses, ['/target nameplate2', '/target nameplate3', '/target nameplate1',
                                   '/target nameplate2'])                      # round again, closest first
        self.g.NOW += 9                                                        # a pause: start from the closest
        self.press('TargetKitFind')
        self.assertEqual(self.press('TargetKitFind'), '/target nameplate3')

    def test_find_skips_dead_mobs_but_not_dead_players_or_friendly_npcs(self):
        self.slash('add Baron')
        self.unit('target', 'Baron Mob', plate=False, dead=True, reaction=2, reach=1)       # hostile: a mob
        self.unit('focus', 'Baron Beast', plate=False, dead=True, reaction=4, reach=1)      # neutral: could be one
        self.unit('mouseover', 'Baron Guard', plate=False, dead=True, reaction=5, reach=3, enemy=False)
        self.unit('party1', 'Baronfriend', plate=False, dead=True, player=True, reach=4, enemy=False)
        presses = {self.press('TargetKitFind') for _ in range(3)}
        self.assertEqual(presses, {'/target mouseover', '/target party1'})

    def test_find_by_name_when_none_is_in_sight(self):
        self.slash('add Thug')
        self.slash('add Baron Silverlaine')
        self.assertEqual(self.press('TargetKitFind'), '/cleartarget\n/target [noexists] Thug\n'
                                                      '/target [noexists] Baron Silverlaine\n/cleartarget [dead,noplayer]')

    def test_find_with_an_empty_list_says_how_to_fill_it(self):
        self.assertEqual(self.press('TargetKitFind'), '')
        self.assertTrue(self.said('your find list is empty. /tkit add <name>'))

    def test_the_find_list_commands(self):
        self.unit('target', 'Mor\'Ladim', plate=False)
        self.slash('add')                                                       # your target's name
        self.slash('add Thug')
        self.slash('add thug')
        self.assertTrue(self.said('Thug is already on the find list'))
        self.slash('remove THUG')
        self.assertEqual(list(self.g.TargetKitDB.find.values()), ["Mor'Ladim"])
        self.slash('clear')
        self.assertEqual(len(self.g.TargetKitDB.find), 0)

    def test_the_addon_compiles_and_the_toc_loads_it(self):
        toc = (KIT / 'TargetKit.toc').read_text(encoding='utf-8')
        self.assertIn('## SavedVariables: TargetKitDB', toc)
        self.assertEqual([l for l in toc.splitlines() if l and not l.startswith('#')], ['TargetKit.lua'])


if __name__ == '__main__':
    unittest.main()
