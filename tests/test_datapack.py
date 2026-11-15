"""Shared Wowhead data pack: sealed with a key, refused with a wrong key or damage, unlocked into an empty folder."""
import tempfile
import unittest
from pathlib import Path

from wfm import datapack


class DataPackTests(unittest.TestCase):
    def test_round_trip_wrong_key_and_damage(self):
        blob = datapack.seal(b'drop rates' * 50, 'friends-key')
        self.assertNotIn(b'drop rates', blob)                         # unreadable without the key
        self.assertEqual(datapack.open_sealed(blob, 'friends-key'), b'drop rates' * 50)
        with self.assertRaises(datapack.BadKey):
            datapack.open_sealed(blob, 'wrong-key')
        damaged = blob[:40] + bytes([blob[40] ^ 1]) + blob[41:]
        with self.assertRaises(datapack.BadKey):
            datapack.open_sealed(damaged, 'friends-key')

    def test_pack_then_unpack_on_a_friends_pc(self):
        with tempfile.TemporaryDirectory() as d:
            mine, theirs = Path(d, 'mine'), Path(d, 'theirs')
            mine.mkdir(); theirs.mkdir()
            (mine / 'wowhead_forever_items.json').write_text('{"items": {}}', encoding='utf-8')
            pack = Path(d, 'p.pack')
            self.assertTrue(datapack.pack('k', mine, pack))
            self.assertFalse(datapack.pack('k', mine, pack))           # same data: the file is left alone
            self.assertEqual(datapack.unpack('', theirs, pack), 'no data key set')
            self.assertEqual(datapack.unpack('nope', theirs, pack), 'wrong key, or the pack is damaged')
            self.assertEqual(datapack.unpack('k', theirs, pack), '1 of 1 files updated')
            self.assertEqual((theirs / 'wowhead_forever_items.json').read_text(encoding='utf-8'), '{"items": {}}')
            self.assertEqual(datapack.unpack('k', theirs, pack), 'up to date')


if __name__ == '__main__':
    unittest.main()
