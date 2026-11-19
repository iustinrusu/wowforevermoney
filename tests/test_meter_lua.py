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
