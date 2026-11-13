import base64
import tempfile
import unittest
import zlib
from pathlib import Path

import cbor2

from wfm.lua import parse_assignments, parse_value
from wfm.questie import load_drop_rates, load_questie
from wfm.tooltips import parse_tooltip
from wfm.tsm import b32, parse_appdata


class TsmTests(unittest.TestCase):
    def test_base32(self):
        self.assertEqual(b32('F4'), 15 * 32 + 4)
        self.assertEqual(b32('1RC'), 1 * 1024 + 27 * 32 + 12)
        self.assertEqual(b32('0'), 0)

    def test_matches_tsm_ingame_tooltip(self):
        # Raw Spotted Yellowtail, TSM in-game tooltip on 2026-11-13: Region Sale Avg 45c, Region Sale Rate 0.631,
        # Region Avg Daily Sold 563.798. Raw values: 45 = '1D', 563798 = 'H6IM', 631 = 'JN' (base 32).
        p = self._write('select(2, ...).LoadData("AUCTIONDB_REGION_SALE","Forever-EU",[[return {downloadTime=1,'
                        'fields={"itemString","regionSale","regionSoldPerDay","regionSalePercent"},data={{4603,1D,H6IM,JN}}}]])\n')
        row = parse_appdata(p).merged(None)[4603]
        self.assertEqual(row['regionSale'], 45)
        self.assertAlmostEqual(row['regionSoldPerDay'], 563.798)
        self.assertAlmostEqual(row['regionSalePercent'], 0.631)

    def _write(self, text):
        f = tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False, encoding='utf-8')
        f.write(text)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return Path(f.name)

    def test_parse_and_scale(self):
        p = self._write(
            'select(2, ...).LoadData("APP_INFO","Global",[[return {version="1",lastSync=1700000000}]])\n'
            'select(2, ...).LoadData("AUCTIONDB_REGION_SALE","Forever-EU",[[return {downloadTime=1700000100,'
            'fields={"itemString","regionSale","regionSoldPerDay","regionSalePercent"},data={{789,1RC,GOM,8L}}}]]) --x\n'
            'select(2, ...).LoadData("AUCTIONDB_NON_COMMODITY_DATA","PvP-Horde",[[return {downloadTime=1700000200,'
            'fields={"itemString","minBuyout","numAuctions","marketValueRecent"},'
            'data={{789,F4,11,F4},{"i:789::i1",1,1,1},{"i:555::i1",A,1,A}}}]])\n'
            'select(2, ...).LoadData("AUCTIONDB_NON_COMMODITY_DATA","PvE-Alliance",[[return {downloadTime=1,'
            'fields={"itemString","minBuyout","numAuctions","marketValueRecent"},data={{789,1,1,1}}}]])\n')
        pd = parse_appdata(p)
        self.assertEqual(pd.app_info['lastSync'], 1700000000)
        self.assertEqual(pd.region(), 'Forever-EU')
        self.assertEqual(pd.realms(), ['PvE-Alliance', 'PvP-Horde'])
        m = pd.merged('PvP-Horde')
        self.assertEqual(m[789]['regionSale'], 1900)
        self.assertAlmostEqual(m[789]['regionSoldPerDay'], (16 * 1024 + 24 * 32 + 22) / 1000)
        self.assertAlmostEqual(m[789]['regionSalePercent'], (8 * 32 + 21) / 1000)
        self.assertEqual(m[789]['minBuyout'], 484, 'the variant row must not overwrite the plain item')
        self.assertEqual(m[789]['numAuctions'], 33)
        self.assertEqual(m[555]['minBuyout'], 10, 'a variant with no plain row is kept')
        self.assertEqual(pd.merged('PvE-Alliance')[789]['minBuyout'], 1, 'other realm selectable')


class LuaTests(unittest.TestCase):
    def test_values(self):
        v = parse_value('{1, 2.5, -3, 0x10, "a\\"b\\n", \'c\', [[long\nstr]], true, false, nil, {x = 1}}')
        self.assertEqual(v, [1, 2.5, -3, 16, 'a"b\n', 'c', 'long\nstr', True, False, None, {'x': 1}])

    def test_mixed_table_and_comments(self):
        v = parse_value('{ -- comment\n [5] = "five", ["k"] = { [1] = 2 }, name = "x", --[[ block ]] 7 }')
        self.assertEqual(v['k'], [2])
        self.assertEqual(v[5], 'five')
        self.assertEqual(v['name'], 'x')
        self.assertEqual(v[1], 7)

    def test_assignments(self):
        text = ('local _, ns = ...\n-- c\nns.Thresholds = {\n\t[18245] = { 275, 315, 335, 355 }, -- Lobster Stew\n}\n'
                'MyDB = {\n["zones"] = {\n["Tanaris"] = {\n["c"] = 3,\n["fish"] = {\n[4603] = 2,\n},\n},\n},\n}\n')
        a = parse_assignments(text)
        self.assertEqual(a['Thresholds'][18245], [275, 315, 335, 355])
        self.assertEqual(a['MyDB']['zones']['Tanaris']['fish'][4603], 2)


class QuestieTests(unittest.TestCase):
    def test_decode_baked_toc(self):
        def b64(obj, compress=False):
            raw = cbor2.dumps(obj)
            return base64.b64encode(zlib.compress(raw) if compress else raw).decode()

        name_row = b64({1: b'Refreshing Spring Water', 9: 5, 'p': 2 ** 13})
        vendors = b64({1: 151, 2: 152})
        long_val = b64({1: b'Daniel Bartlett', 4: 30, 5: 30, 9: 1497, 13: b'H', 14: b'General Trade Supplier'})
        lines = ['## Interface: 16001', '## X-Item-IDS: ' + b64([159], compress=True),
                 '## X-Item-159-S: ' + name_row, '## X-Item-159-14: ' + vendors,
                 '## X-Npc-4561-S: ~2~', '## X-Npc-4561-S-1: ' + long_val[:10], '## X-Npc-4561-S-2: ' + long_val[10:],
                 'src\\config.lua']
        with tempfile.TemporaryDirectory() as d:
            toc = Path(d) / 'QuestieDB_Forever.toc'
            toc.write_text('\n'.join(lines), encoding='utf-8')
            db = load_questie(toc)
            drops = Path(d) / 'drops.lua'
            drops.write_text('X.wowheadData = [[return {\n    [159] = { -- Water\n        [6] = 10.99,\n        [38] = 9.5,\n    },\n}]]')
            rates = load_drop_rates(drops)
        self.assertEqual(db.items[159]['name'], 'Refreshing Spring Water')
        self.assertEqual(db.items[159]['vendors'], [151, 152])
        self.assertEqual(db.npcs[4561]['name'], 'Daniel Bartlett', 'chunked values are reassembled')
        self.assertEqual(db.npcs[4561]['friendlyToFaction'], 'H')
        self.assertEqual(rates, {159: {6: 10.99, 38: 9.5}})


class TooltipTests(unittest.TestCase):
    def test_sell_price_and_fields(self):
        html = ('<table><tr><td><b class="q2">Stout Battlehammer</b><span class="q"><br>Item Level 22</span><br>Binds when equipped'
                '</td></tr></table><table><tr><td>Requires Level 17<br><div class="whtt-sellprice">Sell Price: '
                '<span class="moneysilver">19</span> <span class="moneycopper">69</span></div></td></tr></table>')
        info = parse_tooltip({'name': 'Stout Battlehammer', 'quality': 2, 'tooltip': html})
        self.assertEqual(info['sell_price'], 1969)
        self.assertEqual(info['req_level'], 17)
        self.assertEqual(info['item_level'], 22)
        self.assertEqual(info['bonding'], 2)
        gold = parse_tooltip({'name': 'x', 'tooltip': '<div class="whtt-sellprice">Sell Price: <span class="moneygold">2</span> '
                                                      '<span class="moneycopper">5</span></div>'})
        self.assertEqual(gold['sell_price'], 20005)
        self.assertEqual(parse_tooltip({'name': 'x', 'tooltip': 'no price'})['sell_price'], 0)


if __name__ == '__main__':
    unittest.main()
