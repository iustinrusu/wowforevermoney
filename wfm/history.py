"""Price history in SQLite: one row per item each time TSM delivers a new realm scan.

TSM's data file only holds averages (14-day, recent, long-term), not a time series, so the app keeps its own.
A new install has none, so the app ships a starter history (data/market_seed.json.gz, daily candles made from the
author's snapshots, refreshed with `python -m wfm.history seed`): charts use it for days before your own history
of an item begins, marked "starter" and labelled with its realm and date.
Every snapshot is kept for FULL_DAYS; older days are folded into one daily candle per item (open, high, low,
close of the lowest listing, plus the day's average listings, realm average, region sale price and sold/day),
kept for KEEP_DAYS. Snapshots only exist for times the app was running.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager

from .paths import DATA

DAY = 86400
FULL_DAYS = 14       # every snapshot (about hourly) for two weeks
KEEP_DAYS = 365      # then one daily candle per item for a year
SERIES_COLS = ('ts', 'min_buyout', 'num_auctions', 'market', 'region_market', 'region_sale', 'sold_per_day')
SEED = DATA / 'market_seed.json.gz'
SEED_DAYS = 30       # the starter history keeps the last 30 days
_CANDLE = ('open', 'high', 'low', 'close', 'num_auctions', 'market', 'region_market', 'region_sale', 'sold_per_day')


def load_seed(path=None) -> dict:
    """The shipped starter history: {'made', 'realm', 'items': {item: [[day, open, high, low, close, listings,
    market, region_market, region_sale, sold_per_day], ...]}} or {} when missing."""
    try:
        with gzip.open(path or SEED, 'rt', encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get('items'), dict) else {}
    except (OSError, ValueError):
        return {}


class History:
    def __init__(self, path=None):
        self.path = path or (DATA / 'history.db')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS prices (
                    ts INTEGER NOT NULL, item INTEGER NOT NULL,
                    min_buyout INTEGER, num_auctions INTEGER, market INTEGER,
                    region_market INTEGER, region_sale INTEGER, sold_per_day REAL, sale_rate REAL,
                    PRIMARY KEY (item, ts)) WITHOUT ROWID;
                CREATE INDEX IF NOT EXISTS prices_ts ON prices(ts);
                CREATE TABLE IF NOT EXISTS scans (ts INTEGER PRIMARY KEY, realm TEXT, recorded INTEGER);
                CREATE TABLE IF NOT EXISTS daily (
                    item INTEGER NOT NULL, day INTEGER NOT NULL,
                    open INTEGER, high INTEGER, low INTEGER, close INTEGER, num_auctions REAL, market INTEGER,
                    region_market INTEGER, region_sale INTEGER, sold_per_day REAL, scans INTEGER,
                    PRIMARY KEY (item, day)) WITHOUT ROWID;
            ''')

    @contextmanager
    def _conn(self):
        """A connection that commits on success and is always closed (sqlite3's own context manager doesn't close)."""
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(self, realm: str, scan_time: int, prices: dict[int, dict]) -> bool:
        """Store a snapshot once per realm scan time. Returns True if it was new."""
        if not scan_time:
            return False
        with self._lock, self._conn() as c:
            if c.execute('SELECT 1 FROM scans WHERE ts=?', (scan_time,)).fetchone():
                return False
            rows = [(scan_time, iid, p.get('minBuyout'), p.get('numAuctions', 0), p.get('marketValue'),
                     p.get('regionMarketValue'), p.get('regionSale'), p.get('regionSoldPerDay'),
                     p.get('regionSalePercent'))
                    for iid, p in prices.items() if p.get('marketValue') or p.get('minBuyout')]
            c.executemany('INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?,?)', rows)
            c.execute('INSERT INTO scans VALUES (?,?,?)', (scan_time, realm, int(time.time())))
        self.compact()
        return True

    def compact(self, now: float | None = None) -> int:
        """Fold snapshots older than FULL_DAYS into daily candles; drop anything older than KEEP_DAYS.

        Returns the number of days folded. Only whole days (UTC) before the cutoff are folded.
        """
        now = int(now or time.time())
        fold_before = (now - FULL_DAYS * DAY) // DAY * DAY
        with self._lock, self._conn() as c:
            days = [d for (d,) in c.execute('SELECT DISTINCT ts / ? FROM prices WHERE ts < ?', (DAY, fold_before))]
            for day in days:
                lo, hi = day * DAY, (day + 1) * DAY
                agg: dict[int, dict] = {}
                # merge into a candle already folded for this day (its scans came first: scans arrive in order)
                for item, o, h, l, cl, n, mv, rm, rs, spd, k in c.execute(
                        'SELECT item, open, high, low, close, num_auctions, market, region_market, region_sale, '
                        'sold_per_day, scans FROM daily WHERE day=?', (day,)):
                    agg[item] = {'open': o, 'high': h, 'low': l, 'close': cl, 'n': [n or 0] * (k or 1),
                                 'mv': mv, 'rm': rm, 'rs': rs, 'spd': spd, 'scans': k or 1}
                for item, ts, mb, n, mv, rm, rs, spd in c.execute(
                        'SELECT item, ts, min_buyout, num_auctions, market, region_market, region_sale, sold_per_day '
                        'FROM prices WHERE ts >= ? AND ts < ? ORDER BY item, ts', (lo, hi)):
                    a = agg.setdefault(item, {'open': None, 'high': None, 'low': None, 'close': None, 'n': [],
                                              'mv': None, 'rm': None, 'rs': None, 'spd': None, 'scans': 0})
                    a['scans'] += 1
                    a['n'].append(n or 0)
                    if mb and mb > 0:
                        a['open'] = a['open'] if a['open'] is not None else mb
                        a['high'] = mb if a['high'] is None else max(a['high'], mb)
                        a['low'] = mb if a['low'] is None else min(a['low'], mb)
                        a['close'] = mb
                    a['mv'], a['rm'], a['rs'], a['spd'] = mv or a['mv'], rm or a['rm'], rs or a['rs'], spd or a['spd']
                c.executemany('INSERT OR REPLACE INTO daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                              [(item, day, a['open'], a['high'], a['low'], a['close'], sum(a['n']) / len(a['n']),
                                a['mv'], a['rm'], a['rs'], a['spd'], a['scans']) for item, a in agg.items()])
                c.execute('DELETE FROM prices WHERE ts >= ? AND ts < ?', (lo, hi))
            keep_after = now - KEEP_DAYS * DAY
            c.execute('DELETE FROM daily WHERE day < ?', (keep_after // DAY,))
            c.execute('DELETE FROM scans WHERE ts < ?', (keep_after,))
            return len(days)

    _seed: dict | None = None

    def seed(self) -> dict:
        if self._seed is None:
            self._seed = load_seed(getattr(self, 'seed_path', None))
        return self._seed

    def series(self, item: int, days: int = KEEP_DAYS) -> list[dict]:
        """Oldest first: starter candles for days before your own history of this item, then daily candles for folded
        days (ts = noon UTC, with open/high/low/close), then snapshots."""
        own = self._series(item, days)
        first_day = own[0]['ts'] // DAY if own else None
        since_day = (int(time.time()) - days * DAY) // DAY
        seed = self.seed()
        starter = [{'ts': r[0] * DAY + DAY // 2, 'min_buyout': r[4], **dict(zip(_CANDLE, r[1:])), 'daily': True,
                    'starter': True}
                   for r in (seed.get('items') or {}).get(str(item), [])
                   if r[0] >= since_day and (first_day is None or r[0] < first_day)]
        return starter + own

    def _series(self, item: int, days: int = KEEP_DAYS) -> list[dict]:
        since = int(time.time()) - days * DAY
        with self._conn() as c:
            out = [{'ts': day * DAY + DAY // 2, 'min_buyout': close, 'num_auctions': n, 'market': mv,
                    'region_market': rm, 'region_sale': rs, 'sold_per_day': spd,
                    'open': o, 'high': h, 'low': lo, 'close': close, 'daily': True}
                   for day, o, h, lo, close, n, mv, rm, rs, spd in c.execute(
                       'SELECT day, open, high, low, close, num_auctions, market, region_market, region_sale, '
                       'sold_per_day FROM daily WHERE item=? AND day >= ? ORDER BY day', (item, since // DAY))]
            cur = c.execute(f'SELECT {", ".join(SERIES_COLS)} FROM prices WHERE item=? AND ts>=? ORDER BY ts',
                            (item, since))
            out += [dict(zip(SERIES_COLS, r)) for r in cur.fetchall()]
            return out

    def export_seed(self, path=None, realm: str = '', days: int = SEED_DAYS, now: float | None = None) -> dict:
        """Write the starter history: one candle per item and day over the last `days` days, from folded days and
        from snapshots grouped by day (UTC). Returns counts."""
        now = int(now or time.time())
        since_day = (now - days * DAY) // DAY
        items: dict[int, dict[int, list]] = {}
        with self._conn() as c:
            for row in c.execute('SELECT item, day, open, high, low, close, num_auctions, market, region_market, '
                                 'region_sale, sold_per_day FROM daily WHERE day >= ?', (since_day,)):
                items.setdefault(row[0], {})[row[1]] = list(row[1:])
            agg: dict[tuple, dict] = {}
            for item, ts, mb, n, mv, rm, rs, spd in c.execute(
                    'SELECT item, ts, min_buyout, num_auctions, market, region_market, region_sale, sold_per_day '
                    'FROM prices WHERE ts >= ? ORDER BY item, ts', (since_day * DAY,)):
                a = agg.setdefault((item, ts // DAY), {'o': None, 'h': None, 'l': None, 'c': None, 'n': [], 'mv': None,
                                                       'rm': None, 'rs': None, 'spd': None})
                if mb and mb > 0:
                    a['o'] = a['o'] if a['o'] is not None else mb
                    a['h'] = mb if a['h'] is None else max(a['h'], mb)
                    a['l'] = mb if a['l'] is None else min(a['l'], mb)
                    a['c'] = mb
                a['n'].append(n or 0)
                a['mv'], a['rm'], a['rs'], a['spd'] = mv or a['mv'], rm or a['rm'], rs or a['rs'], spd or a['spd']
            for (item, day), a in agg.items():
                items.setdefault(item, {})[day] = [day, a['o'], a['h'], a['l'], a['c'],
                                                   round(sum(a['n']) / len(a['n']), 1), a['mv'], a['rm'], a['rs'], a['spd']]
        out = {'about': 'Starter price history for Gold Ever After: daily candles (day = days since 1970 UTC; open, '
                        'high, low, close of the lowest listing; average listings; realm market value; region market '
                        'value; region sale price; region sold a day), used only before your own history begins.',
               'made': time.strftime('%Y-%m-%d', time.gmtime(now)), 'realm': realm,
               'items': {str(i): [d[k] for k in sorted(d)] for i, d in items.items()}}
        with gzip.open(path or SEED, 'wt', encoding='utf-8') as f:
            json.dump(out, f, separators=(',', ':'))
        self._seed = None
        return {'items': len(items), 'candles': sum(len(d) for d in items.values())}

    def previous(self, before_ts: int) -> dict[int, dict]:
        """The snapshot just before the given scan time."""
        with self._conn() as c:
            row = c.execute('SELECT MAX(ts) FROM scans WHERE ts < ?', (before_ts,)).fetchone()
            if not row or not row[0]:
                return {}
            cur = c.execute('SELECT item, min_buyout, num_auctions, market FROM prices WHERE ts=?', (row[0],))
            return {r[0]: {'minBuyout': r[1], 'numAuctions': r[2], 'marketValue': r[3]} for r in cur.fetchall()}

    def sold_out(self) -> list[tuple]:
        """(item, snapshots, snapshots with nothing listed) over the kept scans: how often each item was sold out."""
        with self._lock, self._conn() as c:
            return c.execute('SELECT item, COUNT(*), SUM(CASE WHEN num_auctions IS NULL OR num_auctions = 0 THEN 1 '
                             'ELSE 0 END) FROM prices GROUP BY item').fetchall()

    def scans(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            cur = c.execute('SELECT ts, realm, recorded FROM scans ORDER BY ts DESC LIMIT ?', (limit,))
            return [dict(zip(('ts', 'realm', 'recorded'), r)) for r in cur.fetchall()]


if __name__ == '__main__' and sys.argv[1:2] == ['seed']:
    from .settings import Settings
    print(History().export_seed(realm=Settings().snapshot().get('realm') or ''), '->', SEED)
