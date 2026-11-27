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


def load_addon(*files):
    """A Lua 5.1 runtime with the harness, then the addon files in .toc order, each given the addon's name and one
    shared table, as WoW does."""
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.execute((ROOT / 'tests' / 'addon_harness.lua').read_text(encoding='utf-8'))
    run = lua.eval('function(src, name, ns) local f = assert(loadstring(src, name)); f("ForeverMoneyBridge", ns) end')
    ns = lua.table()
    lua.globals().ADDON_NS, lua.globals().RUN_FILE = ns, run        # for a /reload (MeterTests.reload)
    for name in files:
        run((ADDON / name).read_text(encoding='utf-8'), name, ns)
    return lua


@unittest.skipUnless(lua51, 'lupa is not installed (pip install lupa)')
class MeterTests(unittest.TestCase):
    def setUp(self):
        self.lua = load_addon('ForeverMoneyBridge.lua', 'Meter.lua')
        self.g = self.lua.globals()
        self.slash = self.g.SlashCmdList.FOREVERMONEYBRIDGE
        self.events = self.g.frames[2]      # frames[1] is the loot log's

    def fire(self, *args):
        self.events.scripts['OnEvent'](self.events, *args)

    def loot(self, iid, name, n=1):
        self.fire('CHAT_MSG_LOOT', f'You receive loot: |cffffffff|Hitem:{iid}::::::::|h[{name}]|h|r'
                                   + (f'x{n}.' if n > 1 else '.'))

    def refresh(self):
        win = self.g.frames[getattr(self, 'win_at', 3)]
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
        win = g.frames[3]
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
        win = g.frames[3]
        self.assertEqual((win.w, win.h, win.left, win.top, win.body.shown), (300, 34, 120, 900, False))
        self.slash('min')
        self.assertEqual((win.h, g.ForeverMoneyBridgeDB.meter.h), (400, 400))   # the open height is kept

    def test_old_saved_position_moves_to_the_top_left_corner(self):
        # before 1.6.3 the position was whatever WoW anchored the moved window at, e.g. its bottom right corner
        g = self.g
        g.ForeverMoneyBridgeDB = self.lua.eval('{meter = {pos = {"BOTTOMRIGHT", -238, 121}}}')
        self.slash('start')
        win = g.frames[3]
        first = win.points[1]
        self.assertEqual([first[i] for i in (1, 3, 4, 5)], ['BOTTOMRIGHT', 'BOTTOMRIGHT', -238, 121])
        pos = g.ForeverMoneyBridgeDB.meter.pos
        self.assertEqual([pos[i] for i in (1, 2, 3, 4)], ['TOPLEFT', 500, 700, 'BOTTOMLEFT'])

    def test_hide_and_show_keep_counting(self):
        g = self.g
        self.slash('start')
        win = g.frames[3]
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

    def test_debug_and_the_help_say_which_version_runs(self):
        toc = (ADDON / 'ForeverMoneyBridge.toc').read_text(encoding='utf-8')
        version = toc.split('## Version:')[1].split()[0]
        self.slash('debug')
        self.assertIn(f'Gold Ever After|r {version} debug on', self.g.printed[len(self.g.printed)])
        self.slash('')
        self.assertIn(f'Gold Ever After|r {version}: /gea start', self.g.printed[len(self.g.printed)])

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


    # --- containers opened from your bags (1.6.4: the right-click hook stopped firing with the 25 Nov 2026 patch) ---
    def said(self, text):
        return any(text in line for line in self.g.printed.values())

    def pick_junkbox(self):
        """Pick Pocket a mob, which gives a Heavy Junkbox: it counts nothing until opened."""
        self.fire('UNIT_SPELLCAST_SUCCEEDED', 'player', None, 921)
        self.fire('LOOT_READY')
        self.loot(16885, 'Heavy Junkbox')
        self.fire('LOOT_CLOSED')
        self.g.BAGS[0][3] = self.lua.eval('{id = 16885, guid = "Item-0-0-00000ABC"}')

    def open_junkbox(self, sources, locked=True, has_loot=True, wait=6):
        """Lockpicked, then right-clicked: the box is locked while its window is open. No UseContainerItem call."""
        box = self.g.BAGS[0][3]
        box.locked, box.hasLoot = locked, has_loot
        self.g.LOOT_SOURCES = self.lua.eval('{%s}' % ', '.join(f'[{i + 1}] = "{v}"' for i, v in enumerate(sources) if v))
        self.g.LOOT_SLOTS = self.lua.eval('{{nil, 0}, {"|Hitem:8150::|h", 2}}')     # slot 1: the coins
        self.g.NOW += wait
        self.fire('LOOT_READY')
        self.loot(8150, 'Deeprock Salt', 2)                                          # 2 x 297 = 594
        self.fire('LOOT_CLOSED')

    def test_a_junkbox_opened_is_found_by_the_loot_windows_own_source(self):
        self.slash('debug')
        self.slash('start')
        self.pick_junkbox()
        self.assertIn('1 container not opened yet', self.refresh().remind.text)
        self.open_junkbox([None, 'Item-0-0-00000ABC'])        # no source on the coins slot, the box's GUID on slot 2
        win = self.refresh()
        self.assertEqual(win.remind.text, '')
        self.assertTrue(self.said('loot window: containers from item 16885 (found by source)'))
        self.assertEqual(win.kv[2].text, '|cffc7c7cf5s|r |cffeda55f94c|r')        # the salt inside counts
        self.slash('stop')
        self.assertEqual(self.g.ForeverMoneyBridgeDB.meter.sessions[1]['items'][8150], 2)

    def test_the_box_is_found_by_the_lock_when_the_window_gives_no_source(self):
        self.slash('debug')
        self.slash('start')
        self.pick_junkbox()
        self.open_junkbox([])                                  # no source on any slot
        self.assertEqual(self.refresh().remind.text, '')
        self.assertTrue(self.said('loot window: containers from item 16885 (found by locked)'))

    def test_no_source_and_nothing_openable_locked_is_mob_loot(self):
        # an item you are moving is locked too: without a source, only an openable item counts as the box
        self.slash('debug')
        self.slash('start')
        self.pick_junkbox()
        self.open_junkbox([], has_loot=False)
        self.assertIn('1 container not opened yet', self.refresh().remind.text)
        self.assertTrue(self.said('loot window: mobs'))

    def test_the_old_bag_hook_still_counts_when_it_fires(self):
        self.slash('debug')
        self.slash('start')
        self.pick_junkbox()
        self.g.HOOKS.UseContainerItem(0, 3)                   # right-clicked, and the hook fired
        self.open_junkbox(['Item-0-0-00000FFF'], locked=False, wait=1)   # a GUID no bag slot has: the hook names it
        self.assertEqual(self.refresh().remind.text, '')
        self.assertTrue(self.said('loot window: containers from item 16885 (found by used)'))

    def test_a_hook_older_than_3_seconds_is_not_the_box(self):
        self.slash('debug')
        self.slash('start')
        self.pick_junkbox()
        self.g.HOOKS.UseContainerItem(0, 3)
        self.open_junkbox(['Item-0-0-00000FFF'], locked=False, wait=4)
        self.assertIn('1 container not opened yet', self.refresh().remind.text)
        self.assertTrue(self.said('loot window: containers (which box: not found)'))

    def test_a_box_that_left_your_bags_leaves_the_reminder(self):
        # opened in a way none of the above could tell: once it's gone from your bags it's not "not opened yet"
        self.slash('start')
        self.pick_junkbox()
        self.g.BAGS[0][3] = None
        self.fire('BAG_UPDATE_DELAYED')                        # within 2 s of looting it: the bag may not hold it yet
        self.assertIn('1 container not opened yet', self.refresh().remind.text)
        self.g.NOW += 3
        self.fire('BAG_UPDATE_DELAYED')
        self.assertEqual(self.refresh().remind.text, '')


    # --- a running session through a /reload or logout (1.6.5) ---
    def reload(self, away=20):
        """/reload or log out and in: PLAYER_LOGOUT, Meter.lua runs again (its memory gone, the saved file kept),
        PLAYER_LOGIN. `away` seconds pass in between."""
        self.fire('PLAYER_LOGOUT')
        self.g.NOW += away
        self.g.WALL += away
        self.g.RUN_FILE((ADDON / 'Meter.lua').read_text(encoding='utf-8'), 'Meter.lua', self.g.ADDON_NS)
        self.events = self.g.frames[len(self.g.frames)]
        self.slash = self.g.SlashCmdList.FOREVERMONEYBRIDGE
        self.win_at = len(self.g.frames) + 1             # the window it opens again (its buttons come after it)
        self.fire('PLAYER_LOGIN')

    def test_a_session_carries_on_after_a_reload(self):
        self.slash('start')
        self.loot(8150, 'Deeprock Salt', 3)                # 3 x 297 = 891
        self.g.NOW += 600
        self.reload()
        self.assertIsNone(self.g.ForeverMoneyBridgeDB.meter.running['Player-0-00000001'])   # taken back out
        win = self.refresh()
        self.assertTrue(win.shown)
        self.assertEqual(win.kv[1].text, '10:00')           # the 20 s of the reload don't count
        self.assertEqual(win.kv[2].text, '|cffc7c7cf8s|r |cffeda55f91c|r')
        self.assertIn('carried on with your session (10 min so far)', self.g.printed[len(self.g.printed)])
        self.loot(8150, 'Deeprock Salt', 2)                # + 2 x 297 = 1,485 in all
        self.g.NOW += 600
        self.slash('stop')
        s = self.g.ForeverMoneyBridgeDB.meter.sessions[1]
        self.assertEqual((s.minutes, s['items'][8150], s.value), (20, 5, 1485))
        self.assertEqual(len(self.g.ForeverMoneyBridgeDB.meter.sessions), 1)

    def test_a_pause_stays_a_pause_and_a_hidden_window_hidden(self):
        self.slash('start')
        self.g.NOW += 300
        self.slash('pause')
        self.slash('hide')
        self.g.NOW += 1000                                  # paused: not counted
        self.reload()
        win = self.refresh()
        self.assertFalse(win.shown)
        self.assertEqual(win.kv[1].text, '5:00  |cffffd100paused|r')
        self.assertEqual(win.pause.text, 'Resume')
        self.slash('resume')
        self.g.NOW += 60
        self.assertEqual(self.refresh().kv[1].text, '6:00')

    def test_after_more_than_30_minutes_it_is_saved_as_it_stood(self):
        self.slash('start')
        self.loot(8150, 'Deeprock Salt', 3)
        self.g.NOW += 600
        self.reload(away=31 * 60)
        self.assertIn('you logged out 31 min ago with a session running, so it ends there', ''.join(
            self.g.printed.values()))
        s = self.g.ForeverMoneyBridgeDB.meter.sessions[1]
        self.assertEqual((s.minutes, s.value, s.ended), (10, 891, 1795000000))   # ended at the logout
        self.assertIn('not running', (self.slash('show'), self.g.printed[len(self.g.printed)])[1])

    def test_no_session_running_means_nothing_carried_on(self):
        self.slash('start')
        self.slash('stop')
        self.reload()
        self.assertIsNone(self.g.ForeverMoneyBridgeDB.meter.running['Player-0-00000001'])
        self.assertEqual(len(self.g.ForeverMoneyBridgeDB.meter.sessions), 1)

    def test_another_characters_session_waits_for_them(self):
        self.g.ForeverMoneyBridgeDB = self.lua.eval(
            '{meter = {running = {["Player-0-00000002"] = {saved = 1795000000, elapsed = 60, money = 5, items = {}}}}}')
        self.reload()
        self.assertEqual(self.g.ForeverMoneyBridgeDB.meter.running['Player-0-00000002'].elapsed, 60)
        self.assertIsNone(self.g.ForeverMoneyBridgeDB.meter.sessions)

    def test_gold_loading_in_after_a_login_is_not_loot(self):
        self.slash('start')
        self.reload()
        self.g.MONEY += 1000000                              # your gold arriving after the login
        self.fire('PLAYER_MONEY')
        self.fire('CHAT_MSG_MONEY', 'You loot 3 Silver')
        self.g.NOW += 6
        self.fire('CHAT_MSG_MONEY', 'You loot 5 Silver')
        self.g.MONEY += 500
        self.fire('PLAYER_MONEY')
        self.assertEqual(self.refresh().kv[3].text, '|cffc7c7cf5s|r')

@unittest.skipUnless(lua51, 'lupa is not installed (pip install lupa)')
class LootLogTests(unittest.TestCase):
    """The loot log (ForeverMoneyBridge.lua): what each container you open gives, never as mob or fishing loot."""

    def setUp(self):
        self.lua = load_addon('ForeverMoneyBridge.lua')
        self.g = self.lua.globals()
        self.events = self.g.frames[1]
        self.g.BAGS[0][5] = self.lua.eval('{id = 16885, guid = "Item-0-0-00000ABC", locked = true, hasLoot = true}')
        self.g.LOOT_SLOTS = self.lua.eval('{{nil, 0}, {"|Hitem:8150::|h", 2}}')

    def fire(self, *args):
        self.events.scripts['OnEvent'](self.events, *args)

    def test_a_junkbox_opened_without_the_bag_hook_is_logged_under_the_box(self):
        self.g.LOOT_SOURCES = self.lua.eval('{[2] = "Item-0-0-00000ABC"}')
        self.fire('LOOT_OPENED')
        box = self.g.ForeverMoneyBridgeDB.containers[16885]
        self.assertEqual((box.opened, box['items'][8150]), (1, 2))
        self.assertIsNone(self.g.ForeverMoneyBridgeDB.activity.Tanaris)          # not mob loot

    def test_by_the_lock_when_the_window_gives_no_source(self):
        self.g.LOOT_SOURCES = self.lua.eval('{}')
        self.fire('LOOT_OPENED')
        self.assertEqual(self.g.ForeverMoneyBridgeDB.containers[16885].opened, 1)

    def test_mob_loot_stays_mob_loot(self):
        self.fire('LOOT_OPENED')                                                   # a Creature source
        self.assertIsNone(self.g.ForeverMoneyBridgeDB.containers)
        self.assertEqual(self.g.ForeverMoneyBridgeDB.activity.Tanaris.mobs['items'][8150], 2)

if __name__ == '__main__':
    unittest.main()
