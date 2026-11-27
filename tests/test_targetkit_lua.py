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
SAP_FIXED = MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/cast Sap'      # from scratch, players first (1.4.8)
SAP_FIXED_WORLD = MOUSEOVER + '\n/cleartarget\n/targetenemy\n/cast Sap'      # no enemy player around, outside PvP (1.5.5)
PICK_MOUSE = '/target [@mouseover,harm,nodead] mouseover'                  # TK Pickpocket's mouseover line (1.5.5)
MACRO = {'TKFind': 'TK Find', 'TKPick': 'TK Pickpocket', 'TKSap': 'TK Sap'}


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

    def tick(self, wait=0.5):
        """Half a second goes by and the addon looks (five times a second in game): it writes its choice into the
        three macros."""
        self.g.NOW += wait
        self.events.scripts['OnUpdate'](self.events, 1)

    def body(self, button):
        g = self.g
        return g.MACROS[g.GetMacroIndexByName(MACRO[button])].body

    def press(self, button, run=True):
        """Press one of the three macros: it runs as the last look wrote it (here without the lines' [conditions];
        run=False: the game doesn't run it), then 0.3 s pass. Returns the macro without its tooltip line and marker."""
        self.tick()
        text = self.body(button)
        if run:
            self.run_macro(text)
        self.g.NOW += 0.31
        self.g.RUN_TIMERS()
        return '\n'.join(l for l in text.split('\n') if not l.startswith(('#showtooltip', '/click TK'))
                         and l != PICK_MOUSE)

    def holds(self, conds):
        """A macro line's [conditions], the ones TargetKit writes: [a,b][c] is (a and b) or c; @unit, exists, dead,
        player, harm, each with no- for not. As on Forever (TargetKit 1.4.2's log), they see the target you had before
        the press, not one a line before them set or cleared."""
        if not conds:
            return True
        for group in re.findall(r'\[([^\]]*)\]', conds):
            unit, ok = 'target', True
            for c in (x.strip() for x in group.split(',') if x.strip()):
                if c.startswith('@'):
                    unit = c[1:]
                    continue
                neg = c.startswith('no')
                u = self.before if unit == 'target' else self.g.UNITS[unit]
                value = {'exists': u is not None, 'dead': bool(u and u.dead), 'player': bool(u and u.player),
                         'harm': bool(u and u.enemy)}[c[2:] if neg else c]
                ok = ok and (value != neg)
            if ok:
                return True
        return False

    def run_macro(self, text):
        g = self.g
        self.before = g.UNITS.target
        for line in text.split('\n'):
            cmd, _, rest = line.partition(' ')
            m = re.match(r'^((?:\[[^\]]*\])+)\s*', rest)
            conds = m.group(1) if m else ''
            rest = rest[m.end():] if m else rest
            if cmd == '/stopmacro':
                if self.holds(conds):
                    return
                continue
            if not self.holds(conds):
                continue
            if cmd == '/click':
                b = g[rest.split()[0]]
                b.Click(b)
            elif cmd == '/cleartarget':
                g.ClearTarget()
            elif cmd == '/target':
                g.TargetUnit(rest)
            elif cmd == '/targetexact':
                g.TargetUnit(rest, True)
            elif cmd == '/targetenemyplayer':
                g.TargetNearestEnemyPlayer()
            elif cmd == '/targetenemy':
                g.TargetNearestEnemy()
            elif cmd == '/targetfriend':
                g.TargetNearestFriend()
            elif cmd == '/cast':
                g.CastSpellByName(rest)

    def slash(self, msg):
        self.g.SlashCmdList.TARGETKIT(msg)

    def said(self, text):
        return any(text in line for line in self.g.printed.values())

    # --- the macros the addon makes ---
    def test_the_three_macros_are_made_once_and_hold_the_choice_themselves(self):
        """1.4.0: no /click on a secure button (the game never ran its macro): the macro on your bar is the choice."""
        macros = {m.name: m.body for m in self.g.MACROS.values()}
        self.assertEqual(macros, {
            'TK Find': '/click TKFindMark',                             # an empty find list
            'TK Pickpocket': '#showtooltip Pick Pocket\n/targetenemy [noharm][dead]\n' + PICK_MOUSE
                             + '\n/cast Sap\n/cast Pick Pocket\n/click TKPickMark',
            'TK Sap': '#showtooltip Sap\n' + SAP_FIXED_WORLD + '\n/click TKSapMark'})
        self.assertTrue(self.g.TargetKitDB.macrosMade)
        self.assertFalse([f for f in self.g.frames.values() if f.template == 'SecureActionButtonTemplate'])
        self.assertIsNone(self.g.TKSap)
        self.fire('PLAYER_LOGIN')                       # a relog makes none again
        self.assertEqual(len(self.g.MACROS), 3)

    # --- TK Sap ---
    def test_sap_takes_the_closest_enemy_player_in_sap_range_before_a_closer_npc(self):
        self.unit('nameplate1', 'Defias Pathstalker', reach=1)
        self.unit('nameplate2', 'Shadowfang', player=True, reach=2, y=300)
        self.unit('nameplate3', 'Nightstep', player=True, reach=2, y=200)     # lower on screen: nearer
        self.unit('nameplate4', 'Farstrider', player=True, reach=5)
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Nightstep\n/cast Sap')

    def test_sap_skips_who_it_cannot_sap(self):
        self.unit('nameplate1', 'In Combat', player=True, reach=1, combat=True)
        self.unit('nameplate2', 'Dead One', player=True, reach=1, dead=True)
        self.unit('nameplate3', 'Sapped One', player=True, reach=1, sapped=True)
        self.unit('nameplate4', 'Wolf', reach=1, type=1)                        # a beast
        self.unit('nameplate5', 'Friend', player=True, reach=1, enemy=False)
        self.unit('nameplate6', 'Defias Pathstalker', reach=2)                  # the NPC in Sap range
        text = self.press('TKSap')
        self.assertEqual(text, MOUSEOVER + '\n/targetexact Defias Pathstalker\n/cast Sap')   # outside PvP: the NPC
        self.g.INSTANCE = 'pvp'                                                 # in a battleground a player wins
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/targetenemyplayer\n/cast Sap')   # (now your target)

    def test_sap_with_no_player_in_sap_range_leaves_it_to_the_games_pick(self):
        """1.5.3: nobody in Sap range: the game's nearest enemy player from scratch, which caught a rogue fading in that
        TargetKit couldn't see (the user's Arathi Basin log). 1.5.1 named a player seen within 28 yd instead, which
        would have taken him over the rogue."""
        self.unit('nameplate1', 'Farstrider', player=True, reach=4)            # a player, but out of Sap range
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/cast Sap')

    def test_a_stealthed_player_comes_first_of_all(self):
        """1.5.3, the user: "ideally fading rogues should be highest priority out of all rules of targeting"."""
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)              # right next to you
        self.unit('nameplate2', 'Shadowfang', player=True, reach=3, stealthed=True)   # a rogue fading in, a bit off
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Shadowfang'
                                                          '\n/cast Sap')
        self.assertTrue(self.in_log('a stealthed enemy player, first of all: Shadowfang (nameplate2, 10 yd)'))

    def test_a_stealthed_target_is_kept(self):
        """Once the game's pick has caught the rogue, a closer player doesn't take his place."""
        self.unit('target', 'Shadowfang', plate=False, player=True, reach=3, stealthed=True)
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cast Sap')
        self.assertTrue(self.in_log('(your target: kept)'))

    def test_sap_counts_10_yd_as_sap_range_for_players(self):
        """The user's log: the game never answered Sap's range for players there; bands went melee, then 10 yd."""
        self.unit('nameplate1', 'Nightstep', player=True, reach=3)
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Nightstep\n/cast Sap')
        self.assertTrue(self.in_log('enemy player in Sap range: Nightstep (nameplate1, 10 yd)'))

    def test_your_target_as_the_closest_is_just_sapped(self):
        self.unit('target', 'Nightstep', plate=False, player=True, reach=1)
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cast Sap')

    def test_a_player_with_a_last_name_gets_the_first_name_then_first_and_last(self):
        """1.5.2, the user: "in forever players have "FirstName LastName" format". The game gives the last name in the
        realm field; 1.5.1 wrote "First-Last" (nobody's name) and the first name exactly (not the whole name). Now the
        looser "/target First" first, then "/targetexact First Last", which wins when the game takes it."""
        self.unit('nameplate1', 'Nightstep', player=True, reach=1, realm='Moonwell')    # Nightstep Moonwell
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/target Nightstep'
                                                          '\n/targetexact Nightstep Moonwell\n/cast Sap')
        self.assertEqual(self.g.UNITS.target.name, 'Nightstep')
        del self.g.UNITS.target
        self.unit('nameplate2', 'Nightstep', player=True, reach=5, realm='Duskwood')   # same first name
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer'
                                                          '\n/targetexact Nightstep Moonwell\n/cast Sap')

    def test_in_combat_the_fixed_macro_runs(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)
        self.tick()
        self.assertIn('/targetexact Nightstep', self.body('TKSap'))
        self.fire('PLAYER_REGEN_DISABLED')                     # just before combat locks the buttons
        self.g.COMBAT = True
        text = self.press('TKSap')                             # nothing may change it now
        self.assertIn('/cleartarget\n/targetenemy', text)
        self.assertNotIn('Nightstep', text)
        self.assertTrue(self.in_log('press: TK Sap: the fixed macro (in combat, or just before)'))

    def test_the_choice_is_written_into_the_macro_before_the_press(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.tick()
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Nightstep\n/cast Sap'
                                             '\n/click TKSapMark')

    def test_tk_find_is_rewritten_at_most_every_0_4_s_until_a_press(self):
        self.slash('add Defias')
        self.unit('nameplate1', 'Defias Thug', reach=3, enemy=False, reaction=5)
        self.tick()
        self.assertEqual(self.body('TKFind'), '/targetexact Defias Thug\n/click TKFindMark')
        edits = self.g.EDITS
        self.unit('nameplate2', 'Defias Miner', reach=2, enemy=False, reaction=5)    # nearer
        self.tick(wait=0.2)
        self.assertEqual(self.g.EDITS, edits)                              # too soon after the last
        self.assertIn('Defias Thug', self.body('TKFind'))
        self.tick(wait=0.3)
        self.assertIn('Defias Miner', self.body('TKFind'))
        edits = self.g.EDITS
        self.tick()
        self.assertEqual(self.g.EDITS, edits)                              # nothing changed: nothing written

    # --- 1.4.7, the user: "when stealthed and going past multiple enemies, if I press the button I instantly want to
    # sap and pickpocket the one next to me, I don't want to see a failure due to the old target still being selected"
    def test_pickpocket_leaves_a_half_done_one_you_walked_away_from(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.press('TKPick')
        self.assertEqual(self.g.UNITS.target.guid, thug.guid)
        thug.sapped = True                                                  # Pick Pocket was still on cooldown
        thug.reach = 4                                                      # walked on
        self.unit('nameplate2', 'Defias Miner', reach=1)                        # the one next to you now
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Miner\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_lets_go_of_a_far_target_with_nobody_to_rob_in_sight(self):
        self.unit('target', 'Defias Thug', plate=False, reach=5, combat=True)  # can't be robbed, and far
        self.tick()
        self.assertEqual(self.body('TKPick'), '#showtooltip Pick Pocket\n/cleartarget\n/targetenemy\n' + PICK_MOUSE
                                              + '\n/cast Sap\n/cast Pick Pocket\n/click TKPickMark')

    def test_pickpocket_in_a_camp_of_one_name_skips_the_one_just_robbed(self):
        """By name the game takes the closest of that name: the Defias Thug just robbed, next to you."""
        robbed = self.unit('nameplate1', 'Defias Thug', reach=1)
        fresh = self.unit('nameplate2', 'Defias Thug', reach=2)
        self.g.UNITS.target = robbed
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)         # robbed
        self.g.UNITS.target = None
        self.g.TAB = self.lua.table_from([robbed, fresh])
        self.g.UNITS.target = robbed
        self.assertEqual(self.press('TKPick'), '/targetenemy\n/cast Sap\n/cast Pick Pocket')   # Tab, not by name
        self.assertEqual(self.g.UNITS.target.guid, fresh.guid)
        self.g.NOW += 11                                                    # past the half-done rule's 10 s
        self.tick()
        self.assertEqual(self.body('TKPick'), '#showtooltip Pick Pocket\n' + PICK_MOUSE + '\n/cast Sap\n'
                                              '/cast Pick Pocket\n/click TKPickMark')   # your target, robbable, near
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-2', 921)         # robbed too
        self.unit('nameplate3', 'Defias Miner', reach=2)                        # another name in Sap range
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Miner\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_prefers_another_name_over_a_blocked_one(self):
        robbed = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.unit('nameplate2', 'Defias Thug', reach=2)
        self.unit('nameplate3', 'Defias Miner', reach=2)
        self.g.TargetKitDB.picked[robbed.guid] = self.g.WALL                   # robbed a moment ago
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Miner\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_takes_your_mouseover_enemy_over_its_own_choice(self):
        """1.5.5: in Alterac Valley the game hid the NPCs from TargetKit; hovering one and pressing robs that one."""
        self.unit('nameplate1', 'Defias Thug', reach=1)
        hovered = self.unit('mouseover', 'Defias Miner', plate=False, reach=2)
        self.tick()
        self.assertEqual(self.body('TKPick'), '#showtooltip Pick Pocket\n/targetexact Defias Thug\n' + PICK_MOUSE
                                              + '\n/cast Sap\n/cast Pick Pocket\n/click TKPickMark')
        self.run_macro(self.body('TKPick'))
        self.assertEqual(self.g.UNITS.target.guid, hovered.guid)               # the last line that finds wins

    def test_sap_outside_pvp_takes_the_nearest_enemy_mobs_too(self):
        """1.5.5, the user: "sap should also work on mobs too, not only real enemy players"."""
        self.unit('target', 'Defias Thug', plate=False, reach=5)               # far
        self.tick()
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + SAP_FIXED_WORLD + '\n/click TKSapMark')
        self.g.INSTANCE = 'pvp'                                                 # a battleground: players first
        self.tick()
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + SAP_FIXED + '\n/click TKSapMark')

    def test_pickpocket_is_rewritten_at_once_as_you_walk_past(self):
        self.unit('nameplate1', 'Defias Thug', reach=1)
        self.tick()
        self.assertIn('/targetexact Defias Thug', self.body('TKPick'))
        self.g.UNITS.nameplate1.reach = 4
        self.unit('nameplate2', 'Defias Miner', reach=1)
        self.tick(wait=0.05)                                               # well within 0.4 s
        self.assertIn('/targetexact Defias Miner', self.body('TKPick'))

    def test_sap_takes_a_player_in_melee_range_before_one_at_the_edge_of_sap_range(self):
        """1.5.0: Pick Pocket takes NPCs only, so for players melee range is asked with Sinister Strike."""
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)             # first in the steady order
        self.unit('nameplate2', 'Shadowfang', player=True, reach=1)            # right next to you
        self.assertEqual(self.press('TKSap'), MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Shadowfang\n/cast Sap')
        self.assertTrue(self.in_log('enemy player in Sap range: Shadowfang (nameplate2, melee range)'))

    def test_looks_are_timed_and_logged_every_5_minutes(self):
        """1.5.0, the user: "wouldnt this be slow to compute or drain performance?"."""
        self.unit('nameplate1', 'Defias Thug', reach=2)
        for _ in range(3):
            self.tick()
        self.g.NOW += 300
        self.tick()
        line = [l for l in self.logged() if 'perf:' in l][-1]
        self.assertRegex(line, r'perf: \d+ looks in the last 5 min, 0\.40 ms each on average, the longest 0\.40 ms')
        n = sum(1 for l in self.logged() if 'perf:' in l)
        self.fire('NAME_PLATE_UNIT_ADDED', 'nameplate1')
        self.fire('NAME_PLATE_UNIT_ADDED', 'nameplate1')                   # within 0.1 s: no second look
        self.assertEqual(sum(1 for l in self.logged() if 'perf:' in l), n)

    def test_sap_is_rewritten_at_once_when_a_player_comes_into_sap_range(self):
        """1.4.6: a rogue popping up next to you is in TK Sap's macro without the 0.4 s wait."""
        self.unit('nameplate1', 'Defias Thug', reach=2)
        self.tick()
        self.unit('nameplate2', 'Shadowfang', player=True, reach=2)
        self.fire('NAME_PLATE_UNIT_ADDED', 'nameplate2')                    # the game says so: a look at once
        self.assertIn('/targetexact Shadowfang', self.body('TKSap'))
        self.unit('nameplate3', 'Nightstep', player=True, reach=1)              # closer still
        self.tick(wait=0.05)                                               # well within 0.4 s
        self.assertIn('/targetexact Nightstep', self.body('TKSap'))

    def test_sap_lets_go_of_an_enemy_player_out_of_sap_range(self):
        """The user: "in case a stealthed rogue pops up next to me, it targets him even though I maybe have another
        target enemy player targeted that is farther away"."""
        self.unit('target', 'Farstrider', plate=False, player=True, reach=5)
        self.tick()
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + MOUSEOVER + '\n/cleartarget\n/targetenemyplayer'
                                             '\n/cast Sap\n/click TKSapMark')
        rogue = self.lua.table_from({'name': 'Shadowfang', 'guid': 'Player-2', 'enemy': True, 'player': True})
        self.g.NEAREST_PLAYER = rogue                                      # the game's nearest enemy player
        self.run_macro(self.body('TKSap'))
        self.assertEqual(self.g.UNITS.target.name, 'Shadowfang')
        self.g.UNITS.target = self.g.UNITS.world1 = self.lua.table_from(
            {'name': 'Farstrider', 'guid': 'Player-3', 'enemy': True, 'player': True, 'reach': 5})
        self.unit('nameplate1', 'Defias Pathstalker', reach=2)              # an NPC in Sap range
        self.tick()
        self.assertIn('\n/targetexact Defias Pathstalker\n/targetenemyplayer\n/cast Sap', self.body('TKSap'))

    def test_not_written_while_the_macros_window_is_open_and_hand_edits_are_put_back(self):
        self.g.MacroFrame = self.lua.eval('{ IsShown = function() return true end }')
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.tick()
        self.assertNotIn('Nightstep', self.body('TKSap'))
        self.g.MacroFrame = None
        self.tick()
        self.assertIn('Nightstep', self.body('TKSap'))
        i = self.g.GetMacroIndexByName('TK Sap')
        self.g.MACROS[i].body = '/say hi'                                  # edited by hand
        self.tick()
        self.assertIn('Nightstep', self.body('TKSap'))

    def test_a_deleted_macro_is_said_once_in_the_log(self):
        self.lua.eval('table.remove')(self.g.MACROS, self.g.GetMacroIndexByName('TK Sap'))
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.tick()
        self.tick()
        warns = [l for l in self.logged() if 'WARN: TK Sap: not in your macros (deleted?)' in l]
        self.assertEqual(len(warns), 1)
        self.slash('macros')
        self.assertIn('Nightstep', self.body('TKSap'))

    # --- TK Pickpocket ---
    def test_pickpocket_saps_then_robs_the_closest_humanoid_npc(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=1)              # players have no pockets to pick
        self.unit('nameplate2', 'Wolf', reach=1, type=1)
        self.unit('nameplate3', 'Defias Guard', reach=1, combat=True)
        self.unit('nameplate4', 'Defias Thug', reach=2)
        self.unit('nameplate5', 'Defias Miner', reach=3)
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Thug\n/cast Sap\n/cast Pick Pocket')

    def test_pickpocket_moves_on_and_finishes_a_half_done_one(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.unit('nameplate2', 'Defias Miner', reach=2)
        self.assertIn('/targetexact Defias Thug', self.press('TKPick'))
        self.g.UNITS.target = thug
        thug.sapped = True                              # Sap landed, Pick Pocket was still on cooldown
        self.g.NOW += 1.5
        self.assertEqual(self.press('TKPick'), '/cast Pick Pocket')
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)
        self.g.NOW += 1.5
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Miner\n/cast Sap\n/cast Pick Pocket')

    def test_robbed_but_not_sapped_gets_sapped(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.press('TKPick')
        self.g.UNITS.target = thug
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', 'Cast-1', 921)         # robbed, the Sap didn't happen
        self.assertEqual(self.press('TKPick'), '/cast Sap')

    def test_one_already_sapped_is_only_robbed(self):
        self.unit('nameplate1', 'Defias Thug', reach=1, sapped=True)
        self.assertEqual(self.press('TKPick'), '/targetexact Defias Thug\n/cast Pick Pocket')

    def test_no_pockets_to_pick_means_skip_it(self):
        thug = self.unit('nameplate1', 'Defias Thug', reach=1)
        self.g.UNITS.target = thug
        self.fire('UI_ERROR_MESSAGE', 51, 'No pockets to pick')
        self.assertEqual(self.press('TKPick'), '/targetenemy [noharm][dead]\n/cast Sap\n/cast Pick Pocket')

    # --- TK Find ---
    def find_presses(self, n):
        """Press TK Find n times: what each macro said, and whom it left targeted."""
        out = []
        for _ in range(n):
            out.append((self.press('TKFind'), self.g.UNITS.target and self.g.UNITS.target.guid))
        return out

    def test_find_goes_by_name_only_never_tab(self):
        """1.4.5 (the user: "seems it's still targeting other mobs other than the ones selected, if it's too messy let's
        just drop cycling"): only by name, so only what's on the list: the next name from the list in sight on each
        press; mobs that share a name: the closest."""
        self.slash('add thug')
        far = self.unit('nameplate1', 'Defias Thug', reach=5)
        near = self.unit('nameplate2', 'Defias Thug', reach=2)
        river = self.unit('nameplate3', 'Riverpaw Thug', reach=4)                # part of a name is enough
        miner = self.unit('nameplate4', 'Defias Miner', reach=1)                 # not on the list
        self.g.TAB = self.lua.table_from([near, miner, far, river])
        got = self.find_presses(4)
        self.assertEqual([m for m, _ in got], ['/targetexact Defias Thug', '/targetexact Riverpaw Thug',
                                               '/targetexact Defias Thug', '/targetexact Riverpaw Thug'])
        self.assertEqual([g for _, g in got], [near.guid, river.guid, near.guid, river.guid])
        self.assertFalse(self.in_log('TargetNearest'))                           # never the game's Tab
        self.assertNotIn(far.guid, [g for _, g in got])                          # the further one of a name: never
        self.assertNotIn(miner.guid, [g for _, g in got])

    def test_find_with_one_name_takes_the_closest_every_press(self):
        self.slash('add Zhevra Runner')
        a = self.unit('nameplate1', 'Zhevra Runner', reach=4, reaction=4)
        self.unit('nameplate2', 'Zhevra Runner', reach=6, reaction=4)
        self.unit('nameplate3', 'Sunscale Screecher', reach=3)
        self.assertEqual(self.find_presses(3), [('/targetexact Zhevra Runner', a.guid)] * 3)

    def test_find_skips_dead_mobs_but_not_dead_players_or_friendly_npcs(self):
        self.slash('add Baron')
        self.unit('target', 'Baron Mob', plate=False, dead=True, reaction=2, reach=1)       # hostile: a mob
        self.unit('focus', 'Baron Beast', plate=False, dead=True, reaction=4, reach=1)      # neutral: could be one
        self.unit('mouseover', 'Baron Guard', plate=False, dead=True, reaction=5, reach=3, enemy=False)
        self.unit('party1', 'Baronfriend', plate=False, dead=True, player=True, reach=4, enemy=False)
        self.assertEqual(self.press('TKFind'), '/targetexact Baron Guard')     # the closest that counts
        saw = [l for l in self.logged() if 'saw:' in l][-1]
        self.assertIn('Baron Mob (target): dead, and neutral or hostile, so it could be a mob', saw)
        self.assertIn('Baron Beast (focus): dead, and neutral or hostile', saw)
        self.assertEqual(self.g.UNITS.target.name, 'Baron Guard')
        self.assertEqual(self.press('TKFind'), '/target party1')               # the other name: by its token

    def test_find_by_name_when_none_is_in_sight(self):
        self.slash('add Thug')
        self.slash('add Baron Silverlaine')
        self.assertEqual(self.press('TKFind'), '/cleartarget\n/target Baron Silverlaine\n/target Thug')   # first last

    def test_find_with_an_empty_list_says_how_to_fill_it(self):
        self.assertEqual(self.press('TKFind'), '')
        self.assertTrue(self.in_log('press: your find list is empty. /tkit add <name>'))
        self.assertFalse(self.said('your find list is empty'))                 # the log only (1.4.1)

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
        self.assertIn('TargetKit rewrites their text as you play, so leave it as it is.', panel.bars.text)
        self.g.TargetKitMinimapButton.scripts['OnClick'](self.g.TargetKitMinimapButton)
        self.assertFalse(panel.shown)

    def test_a_key_with_shift_for_tk_sap(self):
        panel = self.open_window()
        self.set_key(3, 'LSHIFT', 'F', mods=('shift',))       # Shift alone waits for the key that goes with it
        self.assertEqual(self.g.TargetKitDB['keys'].TKSap, 'SHIFT-F')
        o = self.g.OVERRIDES['SHIFT-F']
        self.assertEqual((o.macro, o.priority), ('TK Sap', True))               # the key runs the macro
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
        self.assertEqual(self.g.OVERRIDES['G'].macro, 'TK Pickpocket')

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
        self.assertEqual(self.g.OVERRIDES['SHIFT-F'].macro, 'TK Sap')

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

    def test_add_my_target_says_so_when_the_game_hides_the_name(self):
        """1.5.6, the user: "Add my target does not work in alterac valley on Irondeep Troggs"."""
        panel = self.open_window()
        self.unit('target', self.g.SECRET, plate=False)                       # a name the game hides from addons
        panel.addTarget.scripts['OnClick'](panel.addTarget)
        self.assertIn("the game hides your target's name from addons here", panel.status.text)
        self.assertIn('Type the name instead', panel.status.text)
        self.assertEqual(len(self.g.TargetKitDB.find), 0)
        self.slash('add')
        self.assertTrue(self.said("the game hides your target's name from addons here"))
        self.slash('add Irondeep')                                            # typed: fine
        self.assertEqual(list(self.g.TargetKitDB.find.values()), ['Irondeep'])

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
        self.assertTrue(self.in_log('addon: TargetKit 1.5.6 loaded; act on key down 1, enemy nameplates 1, friendly'
                                    ' nameplates 0, soft enemy target 1, nameplate range 41; find list: 0 names'))
        self.assertTrue(self.in_log('macros: TK Sap: made, #showtooltip Sap / /cast [@mouseover,harm,nodead] Sap / '))
        self.assertTrue(self.in_log(' / /cast Sap / /click TKSapMark'))

    def test_a_press_logs_what_it_saw_why_and_the_macro(self):
        self.unit('nameplate1', 'Wolf', reach=1, type=1)
        self.unit('nameplate2', 'Nightstep', player=True, reach=2)
        self.unit('nameplate3', 'Bodyguard', player=True, reach=1, combat=True)
        self.press('TKSap')
        self.assertTrue(self.in_log('press: TK Sap: enemy player in Sap range: Nightstep (nameplate2, Sap range) -> '
                                    '/cast [@mouseover,harm,nodead] Sap / /stopmacro [@mouseover,harm,nodead] / '
                                    '/cleartarget / /targetenemyplayer / /targetexact Nightstep / /cast Sap'))
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
        self.g.C_NamePlate.GetNamePlateForUnit = self.lua.eval('function() error("boom") end')
        text = self.press('TKSap')
        self.assertIn('/cleartarget\n/targetenemy', text)                # the fixed macro
        self.press('TKSap')
        errors = [l for l in self.logged() if 'ERROR: TK Sap choosing' in l]
        self.assertGreaterEqual(len(errors), 2)
        self.assertIn('boom', errors[0])
        self.assertIn('(2 times so far)', errors[1])
        self.assertTrue(self.in_log('press: TK Sap: an error (logged), so the fixed macro'))
        self.assertFalse(self.said('an error in TK Sap choosing'))          # the log only (1.4.1)

    def test_what_the_game_blocks_is_logged(self):
        self.fire('ADDON_ACTION_BLOCKED', 'TargetKit', 'TargetUnit()')
        self.fire('ADDON_ACTION_BLOCKED', 'SomeOtherAddon', 'CastSpellByName()')
        self.assertTrue(self.in_log('ERROR: the game blocked TargetKit from TargetUnit() (ADDON_ACTION_BLOCKED)'))
        self.assertFalse(self.in_log('SomeOtherAddon'))
        self.assertFalse(self.said('the game blocked TargetKit'))

    def test_a_key_is_checked_after_it_is_set(self):
        self.open_window()
        self.set_key(3, 'F', mods=('shift',))
        self.assertTrue(self.in_log('keys: TK Sap on SHIFT-F'))
        self.g.SetOverrideBindingMacro = self.lua.eval('function() end')     # something else keeps the key
        panel = self.g.TargetKitPanel
        self.set_key(2, 'G')
        self.assertTrue(self.in_log("WARN: TK Pickpocket on G, but the key does nothing instead"))
        self.assertIn("TK Pickpocket's key G does something else (nothing)", panel.status.text)    # the window says
        self.assertFalse(self.said("does something else"))

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
        self.assertTrue(self.in_log('result: TK Sap: the game ran ClearTarget(), TargetNearestEnemyPlayer(),'
                                    ' TargetUnit(Nightstep, true), CastSpellByName(Sap);'
                                    ' target none -> Nightstep'))

    def test_a_choice_the_game_did_not_take_is_flagged(self):
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        takes = self.g.TargetUnit
        self.g.TargetUnit = self.lua.eval('function() end')                # the game doesn't take the /target line
        self.press('TKSap')
        self.press('TKSap')
        warns = [l for l in self.logged() if 'WARN: TK Sap: it chose enemy player in Sap range: Nightstep' in l]
        self.assertEqual(len(warns), 2)
        self.assertIn("but your target is none (the game didn't take the macro's target line)", warns[0])
        self.assertFalse(self.said("chose a target, but the game didn't target it"))   # the log only (1.4.1)
        self.g.TargetUnit = takes
        self.press('TKSap')                                                  # one the game takes: no warning
        self.assertEqual(len([l for l in self.logged() if 'WARN:' in l]), 2)

    def test_a_friendly_player_with_no_nameplate_is_targeted_by_name(self):
        """The user: "still cant target friendly saved targets with the macro" (friendly nameplates off). Seen as the
        soft friend target or mouseover, which may point elsewhere by the press (the mouse goes to the bar), so the
        macro names them."""
        self.slash('add Brakka')
        friend = self.unit('softfriend', 'Brakka', plate=False, player=True, enemy=False, reaction=5, reach=4)
        self.tick()
        self.assertEqual(self.body('TKFind'), '/targetexact Brakka\n/click TKFindMark')
        del self.g.UNITS.softfriend                                          # the soft target moved on
        self.g.UNITS.world1 = friend                                         # still there, out of the addon's sight
        self.run_macro(self.body('TKFind'))
        self.assertEqual(self.g.UNITS.target.name, 'Brakka')

    def test_a_long_find_list_stays_within_the_macro_limit(self):
        for i in range(40):
            self.slash(f'add Somebody With A Long Name {i}')
        self.tick()
        self.assertLessEqual(len(self.body('TKFind')), 255)
        self.assertTrue(self.body('TKFind').endswith('\n/target Somebody With A Long Name 0\n/click TKFindMark'))
        self.unit('nameplate1', 'Somebody With A Long Name 7', reach=2, enemy=False, reaction=5)
        self.assertEqual(self.press('TKFind'), '/targetexact Somebody With A Long Name 7')

    def test_find_says_when_nobody_on_the_list_is_near(self):
        self.slash('add Game')
        self.press('TKFind')
        self.assertTrue(self.in_log('result: TK Find: the game ran ClearTarget(), TargetUnit(Game);'
                                    ' target none -> none'))
        self.assertTrue(self.in_log('result: TK Find: nobody on your find list (Game) is near enough to target.'))
        self.unit('mouseover', 'Gamekeeper Ralf', plate=False, enemy=False, reaction=5)
        self.g.NOW += 5
        self.press('TKFind')
        self.assertTrue(self.in_log('result: TK Find: the game ran TargetUnit(Gamekeeper Ralf, true)'))
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
        self.assertEqual(self.press('TKFind'), '/cleartarget\n/target Game\n/target Gamebird\n'
                                               '/target Game Warden Ollie')

    def test_chat_stays_quiet_unless_turned_on(self):
        """1.4.1, the user: "chat debug menus should be hidden, I don't want to see them"."""
        self.slash('add Game')
        self.unit('nameplate1', 'Nightstep', player=True, reach=2)
        self.g.UnitCreatureType = self.lua.eval('function() error("boom") end')
        self.press('TKFind')                                                 # nobody near
        self.press('TKSap')                                                  # an error
        self.fire('ADDON_ACTION_BLOCKED', 'TargetKit', 'TargetUnit()')
        panel = self.open_window()
        panel.input.text = 'Thug'
        panel.input.scripts['OnEnterPressed'](panel.input)                   # the window answers on its bottom line
        self.assertEqual(panel.status.text, 'added Thug to the find list (2 on it). TK Find targets it, closest first.')
        self.assertEqual([l for l in self.g.printed.values() if 'TargetKit' in l],
                         ['|cff9ad0ffTargetKit|r added Game to the find list (1 on it). TK Find targets it, closest'
                          ' first.'])                                        # only the answer to what was typed
        self.slash('chat')
        self.assertTrue(self.g.TargetKitDB.chat)                             # kept through relogs
        self.g.NOW += 5
        self.press('TKFind')
        self.assertTrue(self.said('TK Find: nobody on your find list'))
        self.slash('chat')
        self.assertFalse(self.g.TargetKitDB.chat)

    # --- 1.4.2: what Forever's log showed (Zhevra Runners, and CorpseGlow's corpse nameplate) ---
    def test_nameplates_that_cannot_be_measured_are_no_error(self):
        """On Forever asking a nameplate where it is on screen is an error ("Can't measure restricted regions"); it
        made every look fail, so TK Find ran its fixed macro (1.4.2)."""
        self.g.C_NamePlate.GetNamePlateForUnit = self.lua.eval(
            'function() return { GetCenter = function() error("Can\'t measure restricted regions") end } end')
        self.slash('add Zhevra Runner')
        runners = [self.unit(f'nameplate{i}', 'Zhevra Runner', reach=5, enemy=True, reaction=4) for i in (1, 2, 3)]
        self.g.TAB = self.lua.table_from(runners)
        got = []
        for _ in range(4):
            self.press('TKFind')
            got.append(self.g.UNITS.target.guid)
        self.assertEqual(len(set(got)), 1)                                   # the closest each time (1.4.5)
        self.assertEqual(len([l for l in self.logged() if "doesn't let addons measure nameplates" in l]), 1)
        self.assertFalse(self.in_log('ERROR'))

    def test_no_macro_targets_a_nameplate_token(self):
        """Forever refuses "/target nameplateN" in a macro (1.4.3: the game ran it on every press, the target stayed
        none)."""
        self.slash('add Thug')
        self.unit('nameplate1', 'Defias Thug', reach=1)
        self.unit('nameplate2', 'Nightstep', player=True, reach=2)
        for button in MACRO:
            self.tick()
            self.assertNotIn('nameplate', self.body(button))
        self.g.TargetUnit('nameplate1')                                      # the harness refuses it too
        self.assertIsNone(self.g.UNITS.target)

    def test_by_name_doesnt_drop_a_target_you_already_have(self):
        """The fixed macro was "/cleartarget" then "/target [noexists] name": the condition saw the old target, so a
        press with a target only cleared it (the user: "second press unselects the first selection")."""
        self.slash('add Zhevra Runner')
        self.g.UNITS.world1 = self.lua.table_from({'name': 'Zhevra Runner', 'guid': 'Creature-9', 'enemy': True})
        self.unit('target', 'Sunscale Screecher', plate=False)                 # something else targeted
        for _ in range(3):
            self.run_macro(self.body('TKFind'))
            self.assertEqual(self.g.UNITS.target.name, 'Zhevra Runner')
            self.tick()

    def test_sap_keeps_a_target_only_while_it_is_known_to_be_in_sap_range(self):
        """1.4.8: kept only when TargetKit knows it's in Sap range; an NPC there gives way to a player the game finds."""
        self.g.INSTANCE = 'pvp'                                                 # a battleground: a player beats an NPC
        thug = self.unit('target', 'Defias Thug', plate=False, reach=2)
        self.press('TKSap')
        self.assertTrue(self.in_log(' is in Sap range, so it stays'))
        self.assertEqual(self.g.UNITS.target.name, 'Defias Thug')             # no enemy player near: it stays
        self.g.NEAREST_PLAYER = self.lua.table_from({'name': 'Nightstep', 'guid': 'Player-1', 'enemy': True,
                                                     'player': True})
        self.run_macro(self.body('TKSap'))
        self.assertEqual(self.g.UNITS.target.name, 'Nightstep')                # a player wins
        self.g.NEAREST_PLAYER = None
        self.g.UNITS.target = thug
        thug.reach = 4                                                      # you walked on
        self.tick()
        self.run_macro(self.body('TKSap'))
        self.assertIsNone(self.g.UNITS.target)                              # let go of; nobody the game finds

    def test_in_a_battleground_hidden_enemies_mean_the_nearest_enemy_player_every_press(self):
        """The user's log in a battleground: "attempted to index a table that cannot be indexed with secret keys", every
        look failed, and the macro kept a far enemy player: "Out of range" on every press."""
        far = self.unit('target', 'Farstrider', plate=False, player=True, reach=5, guid=self.g.SECRET)
        self.unit('nameplate1', 'Nightstep', player=True, reach=1, guid=self.g.SECRET)
        # 1.4.9, the user's next log: ids hidden, but names and range read fine. TargetKit knows them by name, so the
        # closest enemy player in Sap range is targeted by name (not the game's pick, which kept a far one)
        self.tick()
        self.assertFalse(self.in_log('ERROR'))
        self.assertTrue(self.in_log("the game hides some units' ids from addons here (nameplate1), so TargetKit knows them"
                                    " by name"))
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + MOUSEOVER + '\n/cleartarget\n/targetenemyplayer\n/targetexact Nightstep\n/cast Sap'
                                             '\n/click TKSapMark')
        self.run_macro(self.body('TKSap'))
        self.assertEqual(self.g.UNITS.target.name, 'Nightstep')
        self.g.UNITS.target = far
        in_range, interact = self.g.C_Spell.IsSpellInRange, self.g.CheckInteractDistance
        self.g.C_Spell.IsSpellInRange = self.lua.eval('function() return SECRET end')   # range hidden too
        self.g.CheckInteractDistance = self.lua.eval('function() return SECRET end')
        self.tick()
        self.assertFalse(self.in_log('ERROR'))
        self.assertEqual(self.body('TKSap'), '#showtooltip Sap\n' + SAP_FIXED + '\n/click TKSapMark')
        rogue = self.lua.table_from({'name': 'Shadowfang', 'guid': 'Player-2', 'enemy': True, 'player': True})
        self.g.NEAREST_PLAYER = rogue
        self.run_macro(self.body('TKSap'))
        self.assertTrue(self.in_log("your target Farstrider can't be measured here, so the game's nearest enemy player"
                                    " from scratch"))
        self.assertEqual(self.g.UNITS.target.name, 'Shadowfang')
        self.assertIsNot(self.g.UNITS.target, far)

    def test_the_addon_compiles_and_the_toc_loads_it(self):
        toc = (KIT / 'TargetKit.toc').read_text(encoding='utf-8')
        self.assertIn('## SavedVariables: TargetKitDB', toc)
        self.assertEqual([l for l in toc.splitlines() if l and not l.startswith('#')], ['TargetKit.lua'])


if __name__ == '__main__':
    unittest.main()
