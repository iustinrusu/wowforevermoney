"""Starter price history: export and use before your own history begins."""
import unittest




class StarterHistoryTests(unittest.TestCase):
    def test_export_and_merge_before_your_own_history(self):
        import tempfile
        import time as _t
        from pathlib import Path
        from wfm.history import DAY, History
        now = 100 * DAY + 3600
        real = _t.time
        _t.time = lambda: now                    # record() folds and prunes by the clock
        try:
            with tempfile.TemporaryDirectory() as d:
                author = History(Path(d) / 'a.db')
                author.record('PvP', 98 * DAY + 100, {7: {'minBuyout': 500, 'numAuctions': 4, 'marketValue': 600}})
                author.record('PvP', 99 * DAY + 100, {7: {'minBuyout': 450, 'numAuctions': 2, 'marketValue': 590}})
                seed = Path(d) / 'seed.json.gz'
                self.assertEqual(author.export_seed(seed, realm='PvP', now=now), {'items': 1, 'candles': 2})
                mine = History(Path(d) / 'b.db')
                mine.seed_path = seed
                s = mine.series(7)                                  # nothing of your own: the starter days
                self.assertEqual([(x['ts'] // DAY, x['close'], x['starter']) for x in s],
                                 [(98, 500, True), (99, 450, True)])
                mine.record('PvP', 99 * DAY + 200, {7: {'minBuyout': 400, 'numAuctions': 3, 'marketValue': 580}})
                s = mine.series(7)                                  # your own from day 99: starter only before it
                self.assertEqual([(x['ts'] // DAY, bool(x.get('starter'))) for x in s], [(98, True), (99, False)])
        finally:
            _t.time = real
