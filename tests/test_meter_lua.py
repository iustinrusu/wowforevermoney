"""The farm meter (addon Meter.lua) run under Lua 5.1, WoW's Lua, with stand-ins for the game (addon_harness.lua).

Needs the lupa package (pip install lupa); skipped without it. Numbers worked out by hand in the comments.
"""
import unittest
from pathlib import Path

try:
    import lupa.lua51 as lua51
except ImportError:                       # optional: only for checking the addon
    lua51 = None

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / 'addon' / 'ForeverMoneyBridge'


@unittest.skipUnless(lua51, 'lupa is not installed (pip install lupa)')
class MeterTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((ROOT / 'tests' / 'addon_harness.lua').read_text(encoding='utf-8'))
        self.lua.execute((ADDON / 'Meter.lua').read_text(encoding='utf-8'))
        self.g = self.lua.globals()
        self.slash = self.g.SlashCmdList.FOREVERMONEYBRIDGE
        self.events = self.g.frames[1]

    def fire(self, *args):
        self.events.scripts['OnEvent'](self.events, *args)

    def loot(self, iid, name, n=1):
        self.fire('CHAT_MSG_LOOT', f'You receive loot: |cffffffff|Hitem:{iid}::::::::|h[{name}]|h|r'
                                   + (f'x{n}.' if n > 1 else '.'))

    def refresh(self):
        win = self.g.frames[2]
        win.scripts['OnUpdate'](win, 1.5)
        return win

    def test_every_addon_file_compiles_in_lua_51(self):
        check = self.lua.eval('function(s, n) local f, e = loadstring(s, n); return f ~= nil, e end')
        for f in ADDON.glob('*.lua'):
            ok, err = check(f.read_text(encoding='utf-8'), f.name)
            self.assertTrue(ok, err)

    def test_prices_from_tsm_in_game_or_the_vendor(self):
        self.slash('start')
        self.fire('LOOT_READY')
        self.loot(8150, 'Deeprock Salt', 3)    # TSM 313 - 5% = 297 (vendor 250): 3 x 297 = 891
        self.loot(8171, 'Rugged Hide')         # TSM 520 - 5% = 494 < vendor 500: 500
        self.loot(999, 'Soulbound Thing')      # TSM has none: vendor 77
        self.loot(7973, 'Big-mouth Clam')      # tooltip "<Right Click to Open>": 0 until opened
        win = self.refresh()
        self.assertEqual(win.kv[2].text, '|cffc7c7cf14s|r |cffeda55f68c|r')        # 891 + 500 + 77 = 1,468
        self.assertIn('1 container not opened yet', win.remind.text)
        self.assertIn('TSM in game', win.note.text)
        self.assertIn('2 at vendor price', win.note.text)
        self.g.TSM_API = None                  # without TSM: vendor prices only
        self.slash('stop')
        self.slash('start')
        self.loot(8150, 'Deeprock Salt', 3)
        win = self.refresh()
        self.assertEqual(win.kv[2].text, '|cffc7c7cf7s|r |cffeda55f50c|r')         # 3 x 250
        self.assertIn('TSM is not loaded', win.note.text)

    def test_xp_total_an_hour_and_the_next_level(self):
        g = self.g
        self.slash('start')                                            # 1,000 of 50,000 at level 40
        g.XP = 5000; self.fire('PLAYER_XP_UPDATE', 'player')           # +4,000
        g.XP = 49000; self.fire('PLAYER_XP_UPDATE', 'player')          # +44,000
        g.LEVEL, g.XPMAX, g.XP = 41, 60000, 2500                       # level up: 1,000 to finish 40, 2,500 into 41
        self.fire('PLAYER_LEVEL_UP', 41); self.fire('PLAYER_XP_UPDATE', 'player')
        self.slash('pause'); g.XP = 7500; self.fire('PLAYER_XP_UPDATE', 'player'); self.slash('resume')   # not counted
        g.XP = 8500; self.fire('PLAYER_XP_UPDATE', 'player')           # +1,000
        g.NOW = 1000 + 1800                                            # half an hour
        win = self.refresh()
        self.assertTrue(win.kv[4].text.startswith('52,500'))           # 4,000 + 44,000 + 3,500 + 1,000
        self.assertIn('105,000 an hour', win.kv[4].text)
        self.assertEqual(win.kv[5].text, 'about 29 min at this pace')  # 51,500 left at 105,000 an hour = 29.4 min
        self.slash('stop')
        s = g.ForeverMoneyBridgeDB.meter.sessions[1]
        self.assertEqual((s.xp, s.xpPerHour, s.level), (52500, 105000, 41))

    def test_max_level_shows_no_xp(self):
        self.g.LEVEL = 60
        self.slash('start')
        self.assertIn('max level', self.refresh().kv[4].text)

    def test_auto_uses_the_apps_prices_while_fresh(self):
        # the default: the app's values while under 12 hours old, else TSM in game (decided at /gea start)
        self.g.ForeverMoneyBridge_Prices = self.lua.eval('{made = 1795000000 - 7200, items = {[8150] = 5000}, containers = {}}')
        self.slash('start')
        self.loot(8150, 'Deeprock Salt')
        win = self.refresh()
        self.assertEqual(win.kv[2].text, '|cffc7c7cf50s|r')              # the app's 5,000
        self.assertIn("the app's, from 2.0 h ago", win.note.text)
        self.slash('stop')
        self.g.ForeverMoneyBridge_Prices = self.lua.eval('{made = 1795000000 - 13 * 3600, items = {[8150] = 5000}, containers = {}}')
        self.slash('start')
        self.loot(8150, 'Deeprock Salt')
        win = self.refresh()
        self.assertEqual(win.kv[2].text, '|cffc7c7cf2s|r |cffeda55f97c|r')   # 13 h old: TSM, 313 - 5% = 297
        self.assertIn("the app's are 13 h old", win.note.text)
        self.slash('stop')
        self.assertEqual(self.g.ForeverMoneyBridgeDB.meter.sessions[1].prices, 'tsm')
        self.assertEqual(self.g.ForeverMoneyBridgeDB.meter.sessions[2].prices, 'app')

    def test_fold_to_one_line_and_back(self):
        g = self.g
        self.slash('start')
        win = g.frames[2]
        self.assertEqual((win.fold.text, win.title.text), ('–', 'Gold Ever After'))
        self.assertEqual(win.title.width, 320 - 164)                      # stops short of Pause, Stop and "–"
        self.loot(8150, 'Deeprock Salt', 40)                               # 40 x 297 = 11,880 = 1g 18s 80c
        g.NOW = 1000 + 1800                                                # half an hour: 23,760 an hour
        win.left, win.top = 812.5, 640.25                                  # where the window is now
        self.slash('min')
        self.assertTrue(g.ForeverMoneyBridgeDB.meter.collapsed)
        self.assertEqual((win.h, win.bounds[2], win.bounds[4]), (34, 34, 34))   # the title bar only
        self.assertEqual([p.shown for p in (win.body, win.pause, win.stop)], [False] * 3)
        self.assertEqual((win.fold.text, win.title.width), ('+', 320 - 46))
        sep = ' |cff777777·|r '
        self.assertEqual(win.title.text, '|cffffd7001g|r |cffc7c7cf18s|r' + sep + '|cffaaaaaa2g 37s an hour|r' + sep
                         + '|cffaaaaaa30 min|r')                           # no copper once there is gold
        # anchored at its top left corner, where it was: folding doesn't move the title bar
        self.assertEqual([win.point[i] for i in (1, 3, 4, 5)], ['TOPLEFT', 'BOTTOMLEFT', 812.5, 640.25])
        pos = g.ForeverMoneyBridgeDB.meter.pos
        self.assertEqual([pos[i] for i in (1, 2, 3, 4)], ['TOPLEFT', 812.5, 640.25, 'BOTTOMLEFT'])
        # folded, it keeps counting; paused shows on the line
        self.loot(8171, 'Rugged Hide')                                     # +500: 12,380 = 1g 23s 80c
        self.slash('pause')
        self.assertEqual(self.refresh().title.text, '|cffffd7001g|r |cffc7c7cf23s|r' + sep
                         + '|cffaaaaaa2g 47s an hour|r' + sep + '|cffaaaaaa30 min, paused|r')   # 24,760 an hour
        self.slash('resume')
        self.slash('min')                                                  # open again, as it was
        self.assertFalse(g.ForeverMoneyBridgeDB.meter.collapsed)
        self.assertEqual((win.h, win.bounds[2], win.bounds[4]), (340, 290, 600))
        self.assertEqual([p.shown for p in (win.body, win.pause, win.stop)], [True] * 3)
        self.assertEqual((win.fold.text, win.title.text), ('–', 'Gold Ever After'))
        self.assertEqual(win.kv[2].text, '|cffffd7001g|r |cffc7c7cf23s|r |cffeda55f80c|r')
        self.slash('pause')
        self.assertEqual(self.refresh().kv[1].text, '30:00  |cffffd100paused|r')
        # remembered: the next session opens the way the last one was left
        self.slash('min')
        self.slash('stop')
        self.slash('start')
        self.assertEqual((win.h, win.body.shown, win.fold.text), (34, False, '+'))
        self.assertEqual(self.refresh().title.text, '|cffeda55f0c|r' + sep + '|cffaaaaaa0 s|r')

    def test_opens_folded_at_the_saved_corner(self):
        g = self.g
        g.ForeverMoneyBridgeDB = self.lua.eval(
            '{meter = {collapsed = true, w = 300, h = 400, pos = {"TOPLEFT", 120, 900, "BOTTOMLEFT"}}}')
        self.slash('start')
        win = g.frames[2]
        self.assertEqual((win.w, win.h, win.left, win.top, win.body.shown), (300, 34, 120, 900, False))
        self.slash('min')
        self.assertEqual((win.h, g.ForeverMoneyBridgeDB.meter.h), (400, 400))   # the open height is kept

    def test_old_saved_position_moves_to_the_top_left_corner(self):
        # before 1.6.3 the position was whatever WoW anchored the moved window at, e.g. its bottom right corner
        g = self.g
        g.ForeverMoneyBridgeDB = self.lua.eval('{meter = {pos = {"BOTTOMRIGHT", -238, 121}}}')
        self.slash('start')
        win = g.frames[2]
        first = win.points[1]
        self.assertEqual([first[i] for i in (1, 3, 4, 5)], ['BOTTOMRIGHT', 'BOTTOMRIGHT', -238, 121])
        pos = g.ForeverMoneyBridgeDB.meter.pos
        self.assertEqual([pos[i] for i in (1, 2, 3, 4)], ['TOPLEFT', 500, 700, 'BOTTOMLEFT'])

    def test_hide_and_show_keep_counting(self):
        g = self.g
        self.slash('start')
        win = g.frames[2]
        self.slash('hide')
        self.assertFalse(win.shown)
        self.loot(8150, 'Deeprock Salt', 3)                                # 3 x 297 = 891, counted while hidden
        self.slash('show')
        self.assertTrue(win.shown)
        self.assertEqual(win.kv[2].text, '|cffc7c7cf8s|r |cffeda55f91c|r')
        self.slash('stop')
        self.slash('show')
        self.assertIn('not running', g.printed[len(g.printed)])
        self.assertFalse(win.shown)

    def test_min_before_start_and_the_help(self):
        g = self.g
        self.slash('min')
        self.assertTrue(g.ForeverMoneyBridgeDB.meter.collapsed)
        self.assertIn('opens folded to one line from now on', g.printed[len(g.printed)])
        self.slash('')
        self.assertIn('/gea min (fold the window to one line and back), /gea hide, /gea show', g.printed[len(g.printed)])

    def test_price_source_can_be_the_app(self):
        self.g.ForeverMoneyBridge_Prices = self.lua.eval('{made = 1795000000 - 7200, items = {[8150] = 5000}, containers = {}}')
        self.slash('prices app')
        self.slash('start')
        self.loot(8150, 'Deeprock Salt')
        self.loot(8171, 'Rugged Hide')         # not in the app's table: TSM / vendor, 500
        win = self.refresh()
        self.assertEqual(win.kv[2].text, '|cffc7c7cf55s|r')              # 5,000 + 500
        self.assertIn("the app's, from 2.0 h ago", win.note.text)
        self.assertEqual(self.g.ForeverMoneyBridgeDB.meter.prices, 'app')


if __name__ == '__main__':
    unittest.main()
