"""TargetKit (extras/TargetKit, our addon outside the app): what each of its three buttons chooses, run in Lua 5.1
through lupa with tests/targetkit_harness.lua standing in for WoW. The names here are made up."""
import re
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
        self.run_file = run
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

    def press(self, button, run=True):
        """Press one of the three macros: PreClick writes the macro, the game runs its lines (here without their
        [conditions]; run=False: the game doesn't run it), PostClick logs what came of it and puts the macro back."""
        b = self.g[button]
        b.scripts['PreClick'](b, 'LeftButton', True)
        text = b.attrs['macrotext']
        if run:
            self.run_macro(text)
        b.scripts['PostClick'](b, 'LeftButton', True)
        return text

    def run_macro(self, text):
        g = self.g
        for line in text.split('\n'):
            cmd, _, rest = line.partition(' ')
            rest = re.sub(r'^\[[^\]]*\]\s*', '', rest)
            if cmd == '/cleartarget':
                g.ClearTarget()
            elif cmd == '/target':
                g.TargetUnit(rest)
            elif cmd == '/targetenemyplayer':
                g.TargetNearestEnemyPlayer()
            elif cmd == '/targetenemy':
                g.TargetNearestEnemy()
            elif cmd == '/cast':
                g.CastSpellByName(rest)

    def slash(self, msg):
        self.g.SlashCmdList.TARGETKIT(msg)

    def said(self, text):
        return any(text in line for line in self.g.printed.values())

    # --- the macros the addon makes ---
    def test_the_three_macros_are_made_once_and_click_on_key_down(self):
        macros = {m.name: m.body for m in self.g.MACROS.values()}
        self.assertEqual(macros, {
            'TK Find': '/click TKFind LeftButton 1',
            'TK Pickpocket': '#showtooltip Pick Pocket\n/click TKPick LeftButton 1',
            'TK Sap': '#showtooltip Sap\n/click TKSap LeftButton 1'})
        self.assertTrue(self.g.TargetKitDB.macrosMade)
        self.g.KEYDOWN = False                          # "act on key down" turned off: plain /click
        self.fire('CVAR_UPDATE', 'ActionButtonUseKeyDown')
        self.assertEqual(self.g.MACROS[3].body, '#showtooltip Sap\n/click TKSap')
        self.assertEqual(len(self.g.MACROS), 3)

    # --- TK Sap ---
    def test_sap_takes_the_closest_enemy_player_in_sap_range_before_a_closer_npc(self):
        self.unit('nameplate1', 'Defias Pathstalker', reach=1)
        self.unit('nameplate2', 'Shadowfang', player=True, reach=2, y=300)
        self.unit('nameplate3', 'Nightstep', player=True, reach=2, y=200)     # lower on screen: nearer
        self.unit('nameplate4', 'Farstrider', player=True, reach=5)
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/target nameplate3\n/cast Sap')

    def test_sap_skips_who_it_cannot_sap(self):
        self.unit('nameplate1', 'In Combat', player=True, reach=1, combat=True)
        self.unit('nameplate2', 'Dead One', player=True, reach=1, dead=True)
        self.unit('nameplate3', 'Sapped One', player=True, reach=1, sapped=True)
        self.unit('nameplate4', 'Wolf', reach=1, type=1)                        # a beast
        self.unit('nameplate5', 'Friend', player=True, reach=1, enemy=False)
        self.unit('nameplate6', 'Defias Pathstalker', reach=2)                  # the NPC in Sap range
        text = self.press('TKSap')
        self.assertEqual(text, MOUSEOVER + '\n/cleartarget [dead][noharm][noplayer]\n/targetenemyplayer [noexists]'
                               '\n/target [noexists] nameplate6\n/targetenemy [noexists]\n/cast Sap')

    def test_sap_with_no_player_in_sight_lets_the_game_find_a_revealed_stealther(self):
        """A rogue the game has just revealed has no nameplate: only the game's own /targetenemyplayer reaches it."""
        self.unit('nameplate1', 'Farstrider', player=True, reach=4)            # a player, but out of Sap range
        text = self.press('TKSap')
        self.assertIn('/targetenemyplayer [noexists]', text)
        self.assertNotIn('nameplate1', text)
        self.assertTrue(text.startswith(MOUSEOVER))

    def test_in_combat_the_fixed_macro_runs(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)
        fixed = self.g.TKSap.attrs['macrotext']
        self.fire('PLAYER_REGEN_DISABLED')
        self.g.COMBAT = True
        self.assertEqual(self.press('TKSap'), fixed)                     # nothing may change it now
        self.assertIn('/targetenemyplayer [noexists]', fixed)

    # --- TK Pickpocket ---
    def test_pickpocket_saps_then_robs_the_closest_humanoid_npc(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)              # players have no pockets to pick
        self.unit('nameplate2', 'Wolf', reach=1, type=1)
        self.unit('nameplate3', 'Defias Guard', reach=1, combat=True)
        self.unit('nameplate4', 'Defias Thug', reach=2)
        self.unit('nameplate5', 'Defias Miner', reach=3)
        self.assertEqual(self.press('TKPick'), '/target nameplate4\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_moves_on_and_finishes_a_half_done_one(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.unit('nameplate2', 'Defias Miner', reach=2)
        self.assertIn('/target nameplate1', self.press('TKPick'))
        self.g.UNITS.target = thug
        thug.sapped = True                              # Sap landed, Pick Pocket was still on cooldown
        self.g.NOW += 1.5
        self.assertEqual(self.press('TKPick'), '/cast Pick Pocket')
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)
        self.g.NOW += 1.5
        self.assertEqual(self.press('TKPick'), '/target nameplate2\n/cast Sap\n/cast Pick Pocket')

    def test_robbed_but_not_sapped_gets_sapped(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.press('TKPick')
        self.g.UNITS.target = thug
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)         # robbed, the Sap didn't happen
        self.assertEqual(self.press('TKPick'), '/cast Sap')

    def test_one_already_sapped_is_only_robbed(self):
        self.unit('nameplate1', 'Defias Thug', reach=1, sapped=True)
        self.assertEqual(self.press('TKPick'), '/target nameplate1\n/cast Pick Pocket')

    def test_no_pockets_to_pick_means_skip_it(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.g.UNITS.target = thug
        self.fire('UI_ERROR_MESSAGE', 51, 'No pockets to pick')
        self.assertEqual(self.press('TKPick'), '/targetenemy [noharm][dead]\n/cast Sap\n/cast Pick Pocket')

    # --- TK Find ---
    def test_find_goes_closest_first_then_the_next_on_each_press(self):
        self.slash('add thug')
        self.unit('nameplate1', 'Defias Thug', reach=5)
        self.unit('nameplate2', 'Defias Thug', reach=2)
        self.unit('nameplate3', 'Riverpaw Thug', reach=4)                      # part of a name is enough
        self.unit('nameplate4', 'Defias Miner', reach=1)                       # not on the list
        presses = [self.press('TKFind') for _ in range(4)]
        self.assertEqual(presses, ['/target nameplate2', '/target nameplate3', '/target nameplate1',
                                   '/target nameplate2'])                      # round again, closest first
        self.g.NOW += 9                                                        # a pause: start from the closest
        self.press('TKFind')
        self.assertEqual(self.press('TKFind'), '/target nameplate3')

    def test_find_skips_dead_mobs_but_not_dead_players_or_friendly_npcs(self):
        self.slash('add Baron')
        self.unit('target', 'Baron Mob', plate=False, dead=True, reaction=2, reach=1)       # hostile: a mob
        self.unit('focus', 'Baron Beast', plate=False, dead=True, reaction=4, reach=1)      # neutral: could be one
        self.unit('mouseover', 'Baron Guard', plate=False, dead=True, reaction=5, reach=3, enemy=False)
        self.unit('party1', 'Baronfriend', plate=False, dead=True, player=True, reach=4, enemy=False)
        presses = {self.press('TKFind') for _ in range(3)}
        self.assertEqual(presses, {'/target mouseover', '/target party1'})

    def test_find_by_name_when_none_is_in_sight(self):
        self.slash('add Thug')
        self.slash('add Baron Silverlaine')
        self.assertEqual(self.press('TKFind'), '/cleartarget\n/target [noexists] Thug\n'
                                                      '/target [noexists] Baron Silverlaine\n/cleartarget [dead,noplayer]')

    def test_find_with_an_empty_list_says_how_to_fill_it(self):
        self.assertEqual(self.press('TKFind'), '')
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

    # --- the window: keys for the macros and the find list (1.1.0) ---
    def open_window(self):
        button = self.g.TargetKitMinimapButton
        button.scripts['OnClick'](button)
        return self.g.TargetKitPanel

    def set_key(self, row, *keys, mods=()):
        """Click Set on a macro's row (1 TK Find, 2 TK Pickpocket, 3 TK Sap), then press keys, modifiers held."""
        panel = self.g.TargetKitPanel
        r = panel['keys'][row]
        r.set.scripts['OnClick'](r.set)
        for m in mods:
            self.g.MODS[m] = True
        c = panel.capture
        for k in keys:
            c.scripts['OnKeyDown'](c, k)
        for m in mods:
            self.g.MODS[m] = False

    def test_the_minimap_button_opens_and_closes_the_window(self):
        self.assertTrue(self.g.TargetKitMinimapButton.shown)
        panel = self.open_window()
        self.assertTrue(panel.shown)
        self.assertIn('put this line in a macro of your own: /click TKSap LeftButton 1', panel.bars.text)
        self.g.TargetKitMinimapButton.scripts['OnClick'](self.g.TargetKitMinimapButton)
        self.assertFalse(panel.shown)

    def test_a_key_with_shift_for_tk_sap(self):
        panel = self.open_window()
        self.set_key(3, 'LSHIFT', 'F', mods=('shift',))       # Shift alone waits for the key that goes with it
        self.assertEqual(self.g.TargetKitDB['keys'].TKSap, 'SHIFT-F')
        o = self.g.OVERRIDES['SHIFT-F']
        self.assertEqual((o.button, o.priority, o.mouse), ('TKSap', True, 'LeftButton'))
        self.assertFalse(panel.capture.shown)
        self.assertFalse(panel.capture.keyboard)
        self.assertEqual(panel['keys'][3].key.text, 'Shift-F')
        self.assertEqual(panel.status.text, 'TK Sap is on Shift-F now (it was Move Forward; it does that again if you'
                                            ' clear this key).')

    def test_alt_ctrl_shift_go_in_the_games_order(self):
        self.open_window()
        self.set_key(1, '3', mods=('shift', 'alt', 'ctrl'))
        self.assertEqual(self.g.TargetKitDB['keys'].TKFind, 'ALT-CTRL-SHIFT-3')

    def test_mouse_buttons_and_the_wheel(self):
        panel = self.open_window()
        c = panel.capture
        panel['keys'][2].set.scripts['OnClick'](panel['keys'][2].set)
        c.scripts['OnMouseDown'](c, 'Button4')
        self.assertEqual(self.g.TargetKitDB['keys'].TKPick, 'BUTTON4')
        panel['keys'][1].set.scripts['OnClick'](panel['keys'][1].set)
        self.g.MODS.ctrl = True
        c.scripts['OnMouseWheel'](c, -1)
        self.g.MODS.ctrl = False
        self.assertEqual(self.g.TargetKitDB['keys'].TKFind, 'CTRL-MOUSEWHEELDOWN')
        panel['keys'][3].set.scripts['OnClick'](panel['keys'][3].set)
        c.scripts['OnMouseDown'](c, 'LeftButton')                 # left and right click the interface: cancel
        self.assertIsNone(self.g.TargetKitDB['keys'].TKSap)
        self.assertEqual(panel.status.text, 'no key set.')

    def test_escape_cancels(self):
        panel = self.open_window()
        self.set_key(3, 'ESCAPE')
        self.assertIsNone(self.g.TargetKitDB['keys'].TKSap)
        self.assertFalse(panel.capture.shown)

    def test_one_key_one_macro(self):
        self.open_window()
        self.set_key(3, 'G')
        self.set_key(2, 'G')
        self.assertIsNone(self.g.TargetKitDB['keys'].TKSap)
        self.assertEqual(self.g.TargetKitDB['keys'].TKPick, 'G')
        self.assertEqual(self.g.OVERRIDES['G'].button, 'TKPick')

    def test_clear_gives_the_key_back(self):
        panel = self.open_window()
        self.set_key(3, 'F', mods=('shift',))
        panel['keys'][3].clear.scripts['OnClick'](panel['keys'][3].clear)
        self.assertIsNone(self.g.TargetKitDB['keys'].TKSap)
        self.assertIsNone(self.g.OVERRIDES['SHIFT-F'])
        self.assertEqual(panel.status.text, 'TK Sap has no key now; the key does what it did before.')
        self.assertFalse(panel['keys'][3].clear.enabled)

    def test_keys_come_back_after_a_relog(self):
        self.open_window()
        self.set_key(3, 'F', mods=('shift',))
        self.g.OVERRIDES = self.lua.table()                       # a /reload or relog drops override bindings
        first = len(self.g.frames) + 1
        self.run_file((KIT / 'TargetKit.lua').read_text(encoding='utf-8'))
        events = self.g.frames[first]
        events.scripts['OnEvent'](events, 'PLAYER_LOGIN')         # the saved file is kept
        self.assertEqual(self.g.OVERRIDES['SHIFT-F'].button, 'TKSap')

    def test_keys_cannot_change_in_combat(self):
        panel = self.open_window()
        self.g.COMBAT = True
        panel['keys'][3].set.scripts['OnClick'](panel['keys'][3].set)
        self.assertFalse(panel.capture.shown)
        self.assertEqual(panel.status.text, "keys can't change in combat; try again after it.")

    def test_the_find_list_in_the_window(self):
        panel = self.open_window()
        panel.input.text = 'Baron'
        panel.input.scripts['OnEnterPressed'](panel.input)
        self.assertEqual(panel.input.text, '')
        self.unit('target', 'Defias Pillager', plate=False)
        panel.addTarget.scripts['OnClick'](panel.addTarget)       # your target's name
        self.assertEqual(list(self.g.TargetKitDB.find.values()), ['Baron', 'Defias Pillager'])
        self.assertEqual([panel.rows[i].name.text for i in (1, 2, 3)], ['Baron', 'Defias Pillager', ''])
        self.assertFalse(panel.rows[3].remove.shown)
        panel.rows[1].remove.scripts['OnClick'](panel.rows[1].remove)
        self.assertEqual(list(self.g.TargetKitDB.find.values()), ['Defias Pillager'])
        panel.rows[1].remove.scripts['OnClick'](panel.rows[1].remove)
        self.assertIn('empty: type a name above', panel.rows[1].name.text)
        del self.g.UNITS.target
        panel.addTarget.scripts['OnClick'](panel.addTarget)
        self.assertEqual(panel.status.text, 'target something first, then click Add my target.')

    def test_a_long_find_list_scrolls(self):
        panel = self.open_window()
        for i in range(10):
            self.slash(f'add Name{i}')
        self.assertEqual(panel.rows[1].name.text, 'Name0')
        self.assertEqual(panel.more.text, 'scroll for more: 0 above, 2 below')
        panel.scripts['OnMouseWheel'](panel, -1)
        self.assertEqual(panel.rows[1].name.text, 'Name1')
        self.assertEqual(panel.more.text, 'scroll for more: 1 above, 1 below')
        for _ in range(5):
            panel.scripts['OnMouseWheel'](panel, -1)              # no further than the end
        self.assertEqual(panel.rows[8].name.text, 'Name9')

    def test_the_minimap_button_place_is_kept(self):
        button = self.g.TargetKitMinimapButton
        button.scripts['OnDragStart'](button)
        self.g.CURSOR = self.lua.eval('{1800, 1050}')             # straight above the minimap's centre
        button.scripts['OnUpdate'](button, 0.1)
        button.scripts['OnDragStop'](button)
        self.assertEqual(self.g.TargetKitDB.minimap.angle, 90)
        self.slash('minimap')
        self.assertFalse(button.shown)
        self.assertTrue(self.g.TargetKitDB.minimap.hide)

    # --- the log (1.2.0, the user: "logging should be explicit so we can catch issues") ---
    def logged(self):
        l = self.g.TargetKitDB.log
        return [l[i] for i in range(1, len(l) + 1)] if l else []

    def in_log(self, text):
        return any(text in line for line in self.logged())

    def test_login_logs_the_settings_that_matter_and_the_macros(self):
        self.assertTrue(self.in_log('addon: TargetKit 1.2.2 loaded; act on key down 1, enemy nameplates 1, friendly'
                                    ' nameplates 0, soft enemy target 1, nameplate range 41; find list: 0 names'))
        self.assertTrue(self.in_log('macros: TK Sap: made, #showtooltip Sap / /click TKSap LeftButton 1'))

    def test_a_press_logs_what_it_saw_why_and_the_macro(self):
        self.unit('nameplate1', 'Wolf', reach=1, type=1)
        self.unit('nameplate2', 'Nightstep', player=True, reach=2)
        self.unit('nameplate3', 'Bodyguard', player=True, reach=1, combat=True)
        self.press('TKSap')
        self.assertTrue(self.in_log('press: TK Sap: enemy player in Sap range: Nightstep (nameplate2, Sap range) -> '
                                    '/cast [@mouseover,harm,nodead] Sap / /stopmacro [@mouseover,harm,nodead] / '
                                    '/target nameplate2 / /cast Sap'))
        saw = [l for l in self.logged() if 'saw:' in l][-1]
        self.assertIn('Nightstep (nameplate2, Sap range)', saw)
        self.assertIn('Wolf (nameplate1): not humanoid (Sap takes humanoids)', saw)
        self.assertIn('Bodyguard (nameplate3): in combat (Sap needs it out of combat)', saw)

    def test_what_came_of_a_press_is_logged_for_2_seconds(self):
        target = self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.press('TKSap')
        self.g.UNITS.target = target
        self.fire('PLAYER_TARGET_CHANGED')
        self.fire('UI_ERROR_MESSAGE', 51, 'You must be in stealth.')
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 6770)
        self.g.NOW += 3
        self.fire('UI_ERROR_MESSAGE', 51, 'Out of range.')                 # later: not from that press
        self.assertTrue(self.in_log('result: TK Sap: target now Nightstep'))
        self.assertTrue(self.in_log('result: TK Sap: the game said: You must be in stealth.'))
        self.assertTrue(self.in_log('result: TK Sap: cast Sap on Nightstep'))
        self.assertFalse(self.in_log('Out of range.'))

    def test_an_error_is_logged_and_said_once_and_the_fixed_macro_runs(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.g.UnitCreatureType = self.lua.eval('function() error("boom") end')
        fixed = self.g.TKSap.attrs['macrotext']
        self.assertEqual(self.press('TKSap'), fixed)
        self.press('TKSap')
        errors = [l for l in self.logged() if 'ERROR: TK Sap press' in l]
        self.assertEqual(len(errors), 2)
        self.assertIn('boom', errors[0])
        self.assertTrue(self.in_log('press: TK Sap: an error (logged), so the fixed macro'))
        said = [l for l in self.g.printed.values() if 'an error in TK Sap press' in l]
        self.assertEqual(len(said), 1)

    def test_what_the_game_blocks_is_logged(self):
        self.fire('ADDON_ACTION_BLOCKED', 'TargetKit', 'TargetUnit()')
        self.fire('ADDON_ACTION_BLOCKED', 'SomeOtherAddon', 'CastSpellByName()')
        self.assertTrue(self.in_log('ERROR: the game blocked TargetKit from TargetUnit() (ADDON_ACTION_BLOCKED)'))
        self.assertFalse(self.in_log('SomeOtherAddon'))
        self.assertTrue(self.said('the game blocked TargetKit from TargetUnit()'))

    def test_a_key_is_checked_after_it_is_set(self):
        self.open_window()
        self.set_key(3, 'F', mods=('shift',))
        self.assertTrue(self.in_log('keys: TK Sap on SHIFT-F'))
        self.g.SetOverrideBindingClick = self.lua.eval('function() end')     # something else keeps the key
        self.set_key(2, 'G')
        self.assertTrue(self.in_log("WARN: TK Pickpocket on G, but the key does nothing instead"))
        self.assertTrue(self.said("TK Pickpocket's key G does something else"))

    def test_tkit_log_shows_the_last_lines_and_clears(self):
        self.slash('add Thug')
        self.slash('log 2')
        printed = [self.g.printed[i] for i in range(len(self.g.printed) - 2, len(self.g.printed) + 1)]
        self.assertIn('log, the last 2 of', printed[0])
        self.assertIn('window: added Thug to the find list', printed[2])
        self.slash('log clear')
        self.assertEqual(self.logged(), [])

    # --- what the game ran for a press (1.2.1) ---
    def test_a_press_logs_what_the_game_ran_and_where_the_target_went(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.press('TKSap')
        self.assertTrue(self.in_log('result: TK Sap: the game ran CastSpellByName(Sap), TargetUnit(nameplate1),'
                                    ' CastSpellByName(Sap); target none -> Nightstep'))

    def test_a_macro_the_game_did_not_run_is_flagged(self):
        self.slash('add Game')
        self.press('TKFind', run=False)
        self.press('TKFind', run=False)
        warns = [l for l in self.logged() if 'WARN: TK Find: the game did not run its macro' in l]
        self.assertEqual(len(warns), 2)
        self.assertIn('the click came with down=true; act on key down 1', warns[0])
        said = [l for l in self.g.printed.values() if "the game did not run TK Find's macro" in l]
        self.assertEqual(len(said), 1)                                       # said once

    def test_find_says_when_nobody_on_the_list_is_near(self):
        self.slash('add Game')
        self.press('TKFind')
        self.assertTrue(self.in_log('result: TK Find: the game ran ClearTarget(), TargetUnit(Game), ClearTarget();'
                                    ' target none -> none'))
        self.assertTrue(self.said('TK Find: nobody on your find list (Game) is near enough to target.'))
        self.unit('mouseover', 'Gamekeeper Ralf', plate=False, enemy=False, reaction=5)
        self.g.NOW += 5
        self.press('TKFind')
        self.assertTrue(self.in_log('target none -> Gamekeeper Ralf'))

    def test_a_partial_name_also_tries_the_full_names_seen(self):
        """The user put "Game" on the list for a unit named "Game something" (made-up names here)."""
        self.slash('add Game')
        self.unit('target', 'Game Warden Ollie', plate=False, enemy=False, reaction=5)
        self.fire('PLAYER_TARGET_CHANGED')                      # seen as your target once
        self.unit('mouseover', 'Gamebird', plate=False, enemy=False, reaction=5)
        self.fire('UPDATE_MOUSEOVER_UNIT')
        del self.g.UNITS.target
        del self.g.UNITS.mouseover                              # now neither is in sight
        self.assertEqual(self.press('TKFind'), '/cleartarget\n/target [noexists] Game Warden Ollie\n'
                                               '/target [noexists] Gamebird\n/target [noexists] Game\n'
                                               '/cleartarget [dead,noplayer]')

    def test_the_addon_compiles_and_the_toc_loads_it(self):
        toc = (KIT / 'TargetKit.toc').read_text(encoding='utf-8')
        self.assertIn('## SavedVariables: TargetKitDB', toc)
        self.assertEqual([l for l in toc.splitlines() if l and not l.startswith('#')], ['TargetKit.lua'])


if __name__ == '__main__':
    unittest.main()
