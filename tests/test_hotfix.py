"""The client hotfix cache decoder: layout inference from overlapping records, field grading, item overlay."""
import csv
import random
import struct
import tempfile
import unittest
from pathlib import Path

from wfm import gamedata, hotfix

COLS = ['ID', 'Display_lang', 'SellPrice', 'ItemLevel', 'Bonding', 'Flags_0', 'BuyPrice', 'VendorStackCount',
        'LockID', 'PageID']


def blob(r):
    # binary order differs from the table's for the last two (PageID before LockID), like the real client data
    return (r['Display_lang'].encode() + b'\0' + struct.pack('<i', r['SellPrice']) + struct.pack('<h', r['ItemLevel'])
            + struct.pack('<b', r['Bonding']) + struct.pack('<i', r['Flags_0']) + struct.pack('<i', r['BuyPrice'])
            + struct.pack('<i', r['VendorStackCount']) + struct.pack('<b', r['PageID']) + struct.pack('<b', r['LockID']))


def write_cache(path, records, build=70938):
    out = bytearray(b'XFTH' + struct.pack('<II', 9, build) + bytes(32))
    for rid, r, status in records:
        data = blob(r) if r else b''
        out += b'XFTH' + struct.pack('<iIIIIII', 1, rid, 0, hotfix.TABLE_HASH['ItemSparse'], rid, len(data), status) + data
    Path(path).write_bytes(bytes(out))


class HotfixTests(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(5)
        self.client = {}
        for i in range(1, 201):
            self.client[i] = {'ID': i, 'Display_lang': f'Item {i}', 'SellPrice': rnd.randint(0, 90000),
                              'ItemLevel': rnd.randint(1, 300), 'Bonding': rnd.randint(0, 3),
                              'Flags_0': rnd.choice([0, 4, 0x10]), 'BuyPrice': rnd.randint(0, 50000),
                              'VendorStackCount': rnd.choice([1, 5]), 'LockID': 0,
                              'PageID': rnd.randint(1, 100) if i <= 5 else 0}   # 5 letters with a page
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.csv = Path(self.d.name) / 'ItemSparse.csv'
        with open(self.csv, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            for r in self.client.values():
                w.writerow(r)
        new = {'Display_lang': 'Mithril Bound Trunk', 'SellPrice': 2, 'ItemLevel': 45, 'Bonding': 1,
               'Flags_0': 4, 'BuyPrice': 1000, 'VendorStackCount': 5, 'LockID': 0, 'PageID': 0}
        changed = dict(self.client[50], SellPrice=self.client[50]['SellPrice'] + 7)      # a server price change
        records = [(i, r, 1) for i, r in self.client.items() if i != 50] + [(50, changed, 1), (21228, new, 1),
                                                                             (99999, None, 3)]
        self.cache = Path(self.d.name) / 'DBCache.bin'
        write_cache(self.cache, records)

    def test_infers_layout_grades_fields_and_decodes(self):
        layout_file = Path(self.d.name) / 'layout.json'
        h = hotfix.load_item_hotfixes(self.cache, self.csv, layout_file)
        widths = {c: (k, s) for c, k, s in h.layout}
        self.assertEqual(widths['SellPrice'][1], 4)
        self.assertEqual(widths['ItemLevel'][1], 2)
        self.assertEqual(widths['Bonding'][1], 1)
        self.assertIn('LockID', h.unreliable, 'reads the page byte on letters: must not be trusted')
        self.assertIn('PageID', h.unreliable)
        self.assertNotIn('LockID', h.rows[21228])
        self.assertEqual(h.rows[21228]['Display_lang'], 'Mithril Bound Trunk')
        self.assertEqual(h.rows[21228]['SellPrice'], 2)
        self.assertEqual(h.rows[50]['SellPrice'], self.client[50]['SellPrice'] + 7, 'server changes win')
        self.assertEqual(h.changed_fields.get('SellPrice'), 1)
        self.assertEqual((h.new_items, h.updated_items), (1, 200))
        self.assertNotIn(99999, h.rows, 'deleted/empty records are skipped')
        self.assertTrue(h.inferred)
        again = hotfix.load_item_hotfixes(self.cache, self.csv, layout_file)
        self.assertFalse(again.inferred, 'the saved layout is verified and reused')
        self.assertEqual(again.rows[21228], h.rows[21228])

    def test_overlay_on_game_data(self):
        h = hotfix.load_item_hotfixes(self.cache, self.csv)
        gd = gamedata.GameData(build='1.60.1.70938')
        gd.item_classes[21228] = (15, 0)
        gd.items[50] = gamedata.Item(id=50, name='Item 50', quality=1, item_level=1, req_level=0, sell_price=1,
                                     buy_price=0, stack=1, class_id=7, subclass_id=0, bonding=0, locked=True)
        counts = gamedata.apply_hotfixes(gd, h.rows)
        trunk = gd.items[21228]
        self.assertEqual((trunk.name, trunk.sell_price, trunk.buy_price, trunk.class_id), ('Mithril Bound Trunk', 2, 200, 15))
        self.assertTrue(trunk.openable)
        self.assertFalse(trunk.partial)
        self.assertEqual(gd.items[50].sell_price, self.client[50]['SellPrice'] + 7)
        self.assertTrue(gd.items[50].locked, 'LockID is untrusted in the cache: keep the client value')
        self.assertEqual(counts['updated'], 1)


class InGameTests(unittest.TestCase):
    def test_your_client_overrides_and_scores_the_source(self):
        gd = gamedata.GameData(build='x')
        gd.items[833] = gamedata.Item(id=833, name='Lifestone', quality=3, item_level=55, req_level=50, sell_price=28000,
                                      buy_price=0, stack=1, class_id=4, subclass_id=0, bonding=2, source='server')
        gd.items[4339] = gamedata.Item(id=4339, name='Bolt of Mageweave', quality=1, item_level=45, req_level=0,
                                       sell_price=1250, buy_price=0, stack=20, class_id=7, subclass_id=5, bonding=0)
        info = {833: {'n': 'Lifestone', 'q': 3, 'l': 55, 'r': 50, 'k': 1, 's': 21415, 'b': 2, 't': 1},
                4339: {'n': 'Bolt of Mageweave', 'q': 1, 'l': 45, 'r': 0, 'k': 20, 's': 1250, 'b': 0, 't': 1},
                99: {'q': 1}}                                   # no name: the client hadn't loaded it, ignored
        self.assertEqual(gamedata.apply_ingame(gd, info), 2)
        self.assertEqual(gd.items[833].sell_price, 21415)
        self.assertEqual(gd.items[833].checked, {'against': 'server', 'differs': ['sell_price'], 'at': 1})
        self.assertEqual(gd.items[4339].checked['differs'], [])
        self.assertEqual(gd.items[4339].source, 'in-game')
        gamedata.apply_ingame(gd, info)                          # applying again keeps the first comparison
        self.assertEqual(gd.items[833].checked['against'], 'server')


if __name__ == '__main__':
    unittest.main()
